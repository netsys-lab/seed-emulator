import paho.mqtt.client as mqtt
import psutil
import time
import subprocess
import os
import re

def init_tc ():
    for interface in interfaces.keys():
        # Clear all rules
        subprocess.run(["tc", "qdisc", "del", "dev", interface, "root"])
        # Init bandwidth, latency and loss
        subprocess.run(["tc", "qdisc", "add", "dev", interface, "root", "netem", "rate", "100mbit", "delay", "1ms", "loss", "0%"])

def control_bandwidth_and_latency(interface):
    # Using 'tc' to control bandwidth and latency
    bandwidth = interfaces[interface]['bandwidth']
    latency = interfaces[interface]['latency']
    loss = interfaces[interface]['loss']
    jitter = interfaces[interface]['jitter']
    res = subprocess.run(["tc", "qdisc", "change", "dev", interface, "root", "netem", "rate", bandwidth, "delay", latency, jitter,'loss', loss])
    print(res)

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe(f"{node_name}/control/#")

def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))
    interface = msg.topic.split("/")[2]
    print(interface)
    if interface in interfaces.keys():
        if 'bandwidth' in msg.topic:
            print(msg.payload.decode('utf-8'))
            interfaces[interface]['bandwidth'] = msg.payload.decode('utf-8')
        elif 'latency' in msg.topic:
            interfaces[interface]['latency'] = msg.payload.decode('utf-8')
        elif 'loss' in msg.topic:
            interfaces[interface]['loss'] = msg.payload.decode('utf-8')
        elif 'jitter' in msg.topic:
            interfaces[interface]['jitter'] = msg.payload.decode('utf-8')
        else:
            print("Unknown topic")
            return
        control_bandwidth_and_latency(interface)


def exec_command(command):
    process = subprocess.run(command, stdout=subprocess.PIPE, shell=True, text=True)
    output = process.stdout.strip()
    return output


time.sleep(1)
ix_interfaces = {}
def get_network_bytes_sent(interface):
    net_io = psutil.net_io_counters(pernic=True)
    return net_io[interface].bytes_sent
def get_network_bytes_recv(interface):
    net_io = psutil.net_io_counters(pernic=True)
    return net_io[interface].bytes_recv

# get node name from environment variable

# get default gateway ip
command = "ip route | grep net0 | awk '/src/ {print $9}' | sed 's/\([0-9]\+\.[0-9]\+\.[0-9]\+\.\)[0-9]\+/\11/'"
command = "ip route | grep net0 | awk '/src/ {print $9}'"
broker_ip = exec_command(command)
parts = broker_ip.split(".")
parts[-1] = "1"
broker_ip = ".".join(parts)
if broker_ip == '':
    print("IP find failed") 
    exit(1)
else:
    print("Broker IP: ", broker_ip)
asn = broker_ip.split(".")[1]
node_name = f'AS{asn}'

interfaces = {interface:{'bandwidth': '100mbit', 'latency': '2ms', 'loss': '0%', 'jitter': '0ms' } for interface in psutil.net_if_addrs() if 'ix' in interface}
print(interfaces)
prev_bytes_sent = {interface: get_network_bytes_sent(interface) for interface in interfaces.keys()}
prev_bytes_recv = {interface: get_network_bytes_recv(interface) for interface in interfaces.keys()}

init_tc()

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(broker_ip, 1883, 60)
print("Connected to broker")
client.loop_start() #start the loop
print(f"Subscribing to {node_name}")
# client.subscribe("/{node_name}/#")
time.sleep(1)

while True:
    for interface in prev_bytes_sent.keys():
        bytes_sent = get_network_bytes_sent(interface)
        bytes_recv = get_network_bytes_recv(interface)
        bps_sent = (bytes_sent - prev_bytes_sent[interface])
        bps_recv = (bytes_recv - prev_bytes_recv[interface])
        client.publish(f"node/{node_name}/bandwidth/{interface}", bps_sent+bps_recv)
        prev_bytes_sent[interface] = bytes_sent
        prev_bytes_recv[interface] = bytes_recv
    time.sleep(1)
