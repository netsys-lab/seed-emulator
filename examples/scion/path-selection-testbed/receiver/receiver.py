from flask import Flask, jsonify
import socket
import threading
import struct
import numpy as np
import time
import json 

app = Flask(__name__)

streams_data = {}

@app.route('/stats', methods=['GET'])
def get_stats():
    global streams_data
    stats = {}

    for id in streams_data:
        streams_data[id]['duration'] = streams_data[id]['receive_times'][-1] - streams_data[id]['receive_times'][0] if streams_data[id]['receive_times'] else 0
        streams_data[id]['goodput_mbps'] = streams_data[id]['received_bytes'] / streams_data[id]['duration'] if streams_data[id]['duration'] else 0
        streams_data[id]['avg_delay_ms'] = np.mean(streams_data[id]['one_way_delays']) * 1000 if streams_data[id]['one_way_delays'] else 0
        streams_data[id]['median_delay_ms'] = np.median(streams_data[id]['one_way_delays']) * 1000 if streams_data[id]['one_way_delays'] else 0
        streams_data[id]['std_dev_delay_ms'] = np.std(streams_data[id]['one_way_delays']) * 1000 if streams_data[id]['one_way_delays'] else 0
        streams_data[id]['packet_loss'] = 0.0
        if streams_data[id]['sequence_numbers'] and streams_data[id]['sequence_numbers'][-1] != 0:
            streams_data[id]['packet_loss'] = 1.0 - len(set(streams_data[id]['sequence_numbers'])) / streams_data[id]['sequence_numbers'][-1]
        if streams_data[id]['packet_loss'] < 0:
            streams_data[id]['packet_loss'] = 0.0
        
        stats[id] = {}
        stats[id]['duration'] = streams_data[id]['duration']
        stats[id]['goodput_mbps'] = (streams_data[id]['goodput_mbps']*8)/1000000
        stats[id]['avg_delay_ms'] = streams_data[id]['avg_delay_ms']
        stats[id]['median_delay_ms'] = streams_data[id]['median_delay_ms']
        stats[id]['std_dev_delay_ms'] = streams_data[id]['std_dev_delay_ms']
        stats[id]['packet_loss'] = streams_data[id]['packet_loss']
        stats[id]['received_packets'] = streams_data[id]['received_packets']
        stats[id]['received_bytes'] = streams_data[id]['received_bytes']

        # clear streams data stats
        streams_data[id]['received_bytes'] = 0
        streams_data[id]['received_packets'] = 0
        streams_data[id]['one_way_delays'].clear()
        streams_data[id]['receive_times'].clear()
        streams_data[id]['sequence_numbers'].clear()     

    return jsonify(stats)

def udp_server(host, port, stream_id):
    # global streams_data
    port = streams_data[stream_id]['dstPort']
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((host, port))
    print("UDP server listening on port", port)

    while True:
        data, _ = server_socket.recvfrom(2042)
        receive_time = time.perf_counter()
        streams_data[stream_id]['receive_times'].append(receive_time)
        send_time, sequence_number = struct.unpack('dI', data[:12])
        streams_data[stream_id]['one_way_delays'].append(receive_time - send_time)
        streams_data[stream_id]['sequence_numbers'].append(sequence_number)
        streams_data[stream_id]['received_bytes'] += len(data)
        streams_data[stream_id]['received_packets'] += 1

if __name__ == "__main__":
    topo = json.load(open("/topo/topo.json"))
    for stream in topo['streams']:
        streams_data[stream['id']] = {}
        streams_data[stream['id']]['dstPort'] = stream['dstPort']
        streams_data[stream['id']]['goodput_mbps'] = 0
        streams_data[stream['id']]['bytes_sent'] = 0
        streams_data[stream['id']]['received_bytes'] = 0
        streams_data[stream['id']]['received_packets'] = 0
        streams_data[stream['id']]['duration'] = 0
        streams_data[stream['id']]['avg_delay_ms'] = 0
        streams_data[stream['id']]['median_delay_ms'] = 0
        streams_data[stream['id']]['std_dev_delay_ms'] = 0
        streams_data[stream['id']]['packet_loss'] = 0
        streams_data[stream['id']]['one_way_delays'] = []
        streams_data[stream['id']]['receive_times'] = []
        streams_data[stream['id']]['sequence_numbers'] = []
        
        udp_thread = threading.Thread(target=udp_server, args=('10.72.0.2', stream['dstPort'], stream['id']))
        udp_thread.start()

    app.run(host='0.0.0.0', port=5002)
