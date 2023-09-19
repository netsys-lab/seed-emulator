from flask import Flask, request, jsonify
import socket
import struct
import time
import threading
import json

app = Flask(__name__)

sequence_number = 0  # Initialize sequence number
streams_data = {}
mtu = 1300

@app.route('/stats', methods=['GET'])
def get_stats():
    global streams_data
    return jsonify(streams_data)


def udp_send(stream_id, duration, rate):
        sequence_number = 0
        
        header_size = 12  # 8 bytes for send_time and 4 bytes for sequence_number
        payload_size = mtu - header_size - 28 # Calculate payload size considering header and MTU
        payload = b'0' * payload_size  # Create payload with zeros

        rate = (rate * 1000000)/8
        send_port = streams_data[stream_id]['dstPort']
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        start_time = time.perf_counter()
        bytes_sent = 0
        next_send_time = time.perf_counter()
        send_interval = mtu / rate if rate > 0 else 0

        print("Sending packets to port", send_port)


        while True:
            current_time = time.perf_counter()  
            elapsed_time = current_time - start_time

            if duration != 0 and elapsed_time >= duration:
                break

            if rate > 0 and current_time < next_send_time:
                continue

            # Prepend sequence number and send time to data packet
            header = struct.pack('dI', current_time, sequence_number)
            packet = header + payload
            client_socket.sendto(packet, ("10.72.0.2", send_port))
            bytes_sent += len(packet)    
            sequence_number += 1  # Increment sequence number for each packet
            next_send_time += send_interval

            if rate > 0:
                packet_proc_time = time.perf_counter() - current_time
                time_to_wait = (len(packet) / rate) - packet_proc_time                
                if time_to_wait > 0.05:
                    time.sleep(time_to_wait)

        client_socket.close()

        elapsed_time = time.perf_counter() - start_time
        goodput = bytes_sent*8 / elapsed_time / 1000000
        streams_data[stream_id]['goodput_mbps'] = goodput
        streams_data[stream_id]['bytes_sent'] = bytes_sent
        streams_data[stream_id]['elapsed_time'] = elapsed_time
        streams_data[stream_id]['seq'] = sequence_number

        print(stream_id, streams_data[stream_id])

        


        


@app.route('/send', methods=['POST'])
def send_data():
    data = request.json
    for stream in data:
        stream_id = stream['id']
        if stream_id not in streams_data:
            return jsonify({'status': 'error', 'message': 'stream id {} not found'.format(stream_id)})
        if 'duration' in stream:
            duration = stream['duration']
        else:
            duration = 5
        if 'rate' in stream:
            rate = stream['rate']
        else:
            rate = streams_data[stream_id]['bandwidth']
        
        streams_data[stream_id]['rate'] = rate
        streams_data[stream_id]['duration'] = duration
        streams_data[stream_id]['seq'] = 0
        streams_data[stream_id]['goodput_mbps'] = 0
        streams_data[stream_id]['bytes_sent'] = 0
        streams_data[stream_id]['elapsed_time'] = 0

        threading.Thread(target=udp_send, args=(stream_id, duration, rate)).start()

    return jsonify({'status': 'sending'})

if __name__ == '__main__':
    topo = json.load(open("/topo/topo.json"))
    for stream in topo['streams']:
        streams_data[stream['id']] = {}
        streams_data[stream['id']]['goodput_mbps'] = 0
        streams_data[stream['id']]['bytes_sent'] = 0
        streams_data[stream['id']]['elapsed_time'] = 0
        streams_data[stream['id']]['rate'] = 0
        streams_data[stream['id']]['duration'] = 0
        streams_data[stream['id']]['dstPort'] = stream['dstPort']
        streams_data[stream['id']]['deadline'] = stream['deadline']
        streams_data[stream['id']]['bandwidth'] = stream['bandwidth']
        
        streams_data[stream['id']]['seq'] = 0

    
    app.run(host='0.0.0.0', port=5000)
