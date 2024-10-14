# udp_sender.py

from flask import Flask, request, jsonify
import threading
import time
import socket
import struct

app = Flask(__name__)

test_running = False
test_lock = threading.Lock()
test_metrics = {}

@app.route('/send', methods=['POST'])
def start_test():
    global test_running, test_metrics
    with test_lock:
        if test_running:
            return jsonify({'error': 'Test already running'}), 400
        else:
            data = request.get_json()
            duration = float(data.get('duration'))
            data_rate = float(data.get('rate'))
            packet_size = int(data.get('size'))
            if not packet_size:
                packet_size = 1024

            test_running = True
            test_metrics = {}
            UDP_IP = "10.72.0.2"
            UDP_PORT = 9000
            ACK_PORT = 5006  # Port to receive ACKs

            print(f"Starting test with duration {duration}, rate {data_rate}, size {packet_size}")

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ack_sock.bind(("10.72.0.1", ACK_PORT))
            ack_sock.settimeout(1.0)  # Set timeout for ACK socket

            sequence_number = 0
            send_times = {}
            ack_received = set()
            rtts = []

            total_bytes_sent = 0

            inter_packet_interval = (packet_size * 8) / (data_rate * 1e6)  # seconds per packet

            start_time = time.perf_counter()
            next_send_time = start_time
            end_time = start_time + duration



            def ack_listener(end_time=end_time):
                while time.perf_counter() < end_time+0.3:
                    print(time.perf_counter(), end_time, len(ack_received), sequence_number)
                    try:
                        data, addr = ack_sock.recvfrom(65535)
                        if len(data) < 4:
                            continue
                        ack_seq_num = struct.unpack('!I', data[:4])[0]
                        if ack_seq_num in ack_received:
                            continue
                        ack_received.add(ack_seq_num)
                        send_time = send_times.get(ack_seq_num)
                        if send_time:
                            rtt = time.time() - send_time
                            rtts.append(rtt)
                    except socket.timeout:
                        continue

            ack_thread = threading.Thread(target=ack_listener)
            ack_thread.start()

            print("Starting packet sending")

            while time.perf_counter() < end_time:
                current_time = time.perf_counter()

                if current_time >= next_send_time:
                    # Prepare packet
                    seq_num_bytes = struct.pack('!I', sequence_number)
                    payload = seq_num_bytes + b'\x00' * (packet_size - 4)
                    # Send packet
                    sock.sendto(payload, (UDP_IP, UDP_PORT))
                    send_times[sequence_number] = time.time()
                    total_bytes_sent += packet_size
                    sequence_number += 1
                    # Schedule next packet
                    next_send_time += inter_packet_interval

                else:
                    sleep_time = next_send_time - current_time
                    if sleep_time > 0.01:
                        time.sleep(sleep_time - 0.005)
                    else:
                        # Busy-wait
                        while time.perf_counter() < next_send_time:
                            pass
            print("Finished sending packets")
            elapsed_time = time.perf_counter() - start_time
            ack_thread.join()

            
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

            test_running = False
            return jsonify(test_metrics)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
