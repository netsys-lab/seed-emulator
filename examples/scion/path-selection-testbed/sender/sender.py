from flask import Flask, request, jsonify
import socket
import struct
import time
import threading

app = Flask(__name__)

sequence_number = 0  # Initialize sequence number
stat = {}

@app.route('/stats', methods=['GET'])
def get_stats():
    global stat
    return jsonify(stat)


@app.route('/send', methods=['POST'])
def send_data():
    global sequence_number
    sequence_number = 0  # Reset sequence number
    data = request.json
    if 'size' in data:
        size = data['size']
    else:
        size = 0
    if 'duration' in data:
        duration = data['duration']
    else:
        duration = 0
    if 'rate' in data:
        rate = data['rate'] # in Mbps
    else:
        rate = 0
    if rate !=0:
        rate = (rate * 1000000)/8
    if size == 0 and duration == 0:
        return jsonify({'status': 'error', 'message': 'size or duration must be specified'})
    mtu = 1400
    header_size = 12  # 8 bytes for send_time and 4 bytes for sequence_number
    payload_size = mtu - header_size  # Calculate payload size considering header and MTU
    payload = b'0' * payload_size  # Create payload with zeros
    def udp_send():
        global sequence_number

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        start_time = time.perf_counter()
        bytes_sent = 0
        next_send_time = time.perf_counter()
        send_interval = mtu / rate if rate > 0 else 0

        while True:
            current_time = time.perf_counter()  
            elapsed_time = current_time - start_time

            # Stop sending if size is reached
            if size != 0 and bytes_sent > size:
                break

            if duration != 0 and elapsed_time >= duration:
                break

            if rate > 0 and current_time < next_send_time:
                continue

            # Prepend sequence number and send time to data packet
            header = struct.pack('dI', current_time, sequence_number)
            packet = header + payload
            client_socket.sendto(packet, ("10.72.0.2", 9000))
            bytes_sent += len(packet)    
            sequence_number += 1  # Increment sequence number for each packet
            next_send_time += send_interval

            if rate > 0:
                packet_proc_time = time.perf_counter() - current_time
                time_to_wait = (len(packet) / rate) - packet_proc_time                
                if time_to_wait > 0.05:
                    time.sleep(time_to_wait)


        print("Finished sending")
        print("Bytes sent: {}".format(bytes_sent))
        print("Elapsed time: {}".format(elapsed_time))
        goodput = bytes_sent*8 / elapsed_time / 1000000
        print("Goodput_mbps: {}".format(goodput))
        stat['goodput_mbps'] = goodput
        stat['bytes_sent'] = bytes_sent
        stat['elapsed_time'] = elapsed_time

    # Start UDP sending in a new thread
    threading.Thread(target=udp_send).start()

    return jsonify({'status': 'sending'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
