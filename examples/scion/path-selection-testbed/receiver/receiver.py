from flask import Flask, jsonify
import socket
import threading
import struct
import numpy as np
import time

app = Flask(__name__)

received_bytes = 0
received_packets = 0
one_way_delays = []
receive_times = []
sequence_numbers = []
results = []

@app.route('/stats', methods=['GET'])
def get_stats():
    global received_bytes, received_packets, one_way_delays
    global receive_times, sequence_numbers

    # Calculate statistics
    duration = receive_times[-1] - receive_times[0] if receive_times else 0
    goodput = received_bytes / duration if duration else 0
    avg_delay = np.mean(one_way_delays) * 1000 if one_way_delays else 0
    median_delay = np.median(one_way_delays) * 1000 if one_way_delays else 0
    std_dev_delay = np.std(one_way_delays) * 1000 if one_way_delays else 0
    
    # calculate packet loss from sequence numbers list
    loss = 0.0
    if sequence_numbers and sequence_numbers[-1] != 0:
        loss = 1.0 - len(set(sequence_numbers)) / sequence_numbers[-1]   
    if loss < 0:
        loss = 0.0     

    _received_bytes = received_bytes
    _received_packets = received_packets

    # Clear stats
    received_bytes = 0
    received_packets = 0
    one_way_delays.clear()
    receive_times.clear()
    sequence_numbers.clear()

    goodput = goodput * 8 / 1000000
    results.append({
        'goodput_mbps': goodput,
        'avg_delay_ms': avg_delay,
        'median_delay_ms': median_delay,
        'std_dev_delay_ms': std_dev_delay,
        'packet_loss': loss,
        'received_packets': _received_packets,
        'received_bytes': _received_bytes,
        'duration': duration
    })

    return jsonify(results)

def udp_server(host, port):
    global received_bytes, received_packets, one_way_delays
    global receive_times, sequence_numbers

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((host, port))

    while True:
        data, _ = server_socket.recvfrom(2042)
        receive_time = time.perf_counter()
        receive_times.append(receive_time)
        send_time, sequence_number = struct.unpack('dI', data[:12])
        one_way_delays.append(receive_time - send_time)
        sequence_numbers.append(sequence_number)
        received_bytes += len(data)
        received_packets += 1

if __name__ == "__main__":
    udp_thread = threading.Thread(target=udp_server, args=('10.72.0.2', 9000))
    udp_thread.start()
    app.run(host='0.0.0.0', port=5002)
