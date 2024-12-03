from flask import Flask, request, jsonify
import threading
import time
import socket
import struct
import subprocess

app = Flask(__name__)

# Globals
test_running = False
test_lock = threading.Lock()
test_metrics = {}

ACK_IP = ""
UDP_IP = "10.72.0.2"
UDP_PORT = 9000
TCP_ACK_PORT = 5006

BUFFER_SIZE = 65535
ACK_TIMEOUT = 1


def exec_command(command):
    process = subprocess.run(command, stdout=subprocess.PIPE, shell=True, text=True)
    return process.stdout.strip()


@app.route('/send', methods=['POST'])
def start_test():
    global test_running, test_metrics

    with test_lock:
        if test_running:
            return jsonify({'error': 'Test already running'}), 400

        data = request.get_json()
        duration = float(data.get('duration', 10))
        data_rate = float(data.get('rate', 1))  # Mbps
        packet_size = data.get('size', 1024)

        test_running = True
        test_metrics = {}

        print(f"Starting test with duration={duration}s, rate={data_rate}Mbps, size={packet_size} bytes")

        try:
            # Create UDP socket for data sending
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Connect to receiver's TCP ACK socket
            ack_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ack_sock.connect((ACK_IP, TCP_ACK_PORT))
            ack_sock.settimeout(ACK_TIMEOUT)

            sequence_number = 0
            send_times = {}
            ack_received = set()
            rtts = []
            total_bytes_sent = 0
            inter_packet_interval = (packet_size * 8) / (data_rate * 1e6)  # seconds per packet

            start_time = time.perf_counter()
            end_time = start_time + duration

            # ACK listener thread
            def ack_listener():
                while time.perf_counter() < end_time + ACK_TIMEOUT:
                    try:
                        ack_data = ack_sock.recv(BUFFER_SIZE)
                        while ack_data:
                            seq_num = struct.unpack('!I', ack_data[:4])[0]
                            ack_data = ack_data[4:]  # Move to the next ACK in the buffer

                            if seq_num not in ack_received:
                                ack_received.add(seq_num)
                                send_time = send_times.pop(seq_num, None)
                                if send_time:
                                    rtt = time.perf_counter() - send_time
                                    rtts.append(rtt)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"ACK listener error: {e}")
                        break

            ack_thread = threading.Thread(target=ack_listener, daemon=True)
            ack_thread.start()

            print("Sending packets...")
            next_send_time = start_time

            while time.perf_counter() < end_time:
                current_time = time.perf_counter()
                if current_time >= next_send_time:
                    # Prepare and send UDP packet
                    seq_num_bytes = struct.pack('!I', sequence_number)
                    payload = seq_num_bytes + b'\x00' * (packet_size - 4)
                    udp_sock.sendto(payload, (UDP_IP, UDP_PORT))

                    send_times[sequence_number] = time.perf_counter()
                    total_bytes_sent += packet_size
                    sequence_number += 1

                    # Calculate the next send time
                    next_send_time += inter_packet_interval

                # Busy-wait for the next interval
                while time.perf_counter() < next_send_time:
                    pass

            print("Finished sending packets.")
            print("Waiting for ACKs...")
            elapsed_time = time.perf_counter() - start_time
            ack_thread.join()
            print("Received {} ACKs".format(len(ack_received)))

            # Calculate metrics
            goodput_sent = (total_bytes_sent * 8) / (elapsed_time * 1e6)  # Mbps
            total_bytes_received = len(ack_received) * packet_size
            goodput_received = (total_bytes_received * 8) / (elapsed_time * 1e6)  # Mbps
            packet_loss = (sequence_number - len(ack_received)) / sequence_number
            average_delay = sum(rtts) / len(rtts) if rtts else None

            test_metrics = {
                'total_bytes_sent': total_bytes_sent,
                'goodput_sent_mbps': goodput_sent,
                'goodput_received_mbps': goodput_received,
                'elapsed_time': elapsed_time,
                'total_bytes_received': total_bytes_received,
                'packet_loss': packet_loss,
                'average_delay': average_delay,
            }

        except Exception as e:
            print(f"Error during test: {e}")
            test_metrics = {'error': str(e)}
        finally:
            test_running = False
            udp_sock.close()
            ack_sock.close()

        return jsonify(test_metrics)


if __name__ == '__main__':
    command = "ip route | grep net0 | awk '/src/ {print $9}'"
    ip = exec_command(command)
    parts = ip.split(".")
    parts[-1] = "1"
    ACK_IP = ".".join(parts)
    app.run(host='0.0.0.0', port=5000)
