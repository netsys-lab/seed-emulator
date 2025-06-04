import paho.mqtt.client as mqtt
import psutil
import time
import subprocess

def init_tc(interfaces):
    """
    Initialize traffic control (tc) settings for all specified interfaces.

    Args:
        interfaces (dict): A dictionary where the keys are interface names
                           and values are parameters like bandwidth, latency, jitter, and loss.
    """
    for interface, params in interfaces.items():
        try:
            # Clear existing qdisc rules
            subprocess.run(["tc", "qdisc", "del", "dev", interface, "root"], stderr=subprocess.DEVNULL)

            # Apply new qdisc rules
            cmd = [
                "tc", "qdisc", "add", "dev", interface, "root", "netem",
                "rate", params['bw'],
                "delay", f"{params['latency']}", f"{params['jitter']}",
                "loss", params['loss']
            ]
            subprocess.run(cmd, check=True)
            print(f"Initialized tc settings for {interface}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to initialize tc for {interface}: {e}")

def control_bandwidth_and_latency(interface, params):
    """
    Update the traffic control (tc) settings for a specific interface.

    Args:
        interface (str): The network interface to update (e.g., "eth0").
        params (dict): Parameters including bandwidth, latency, jitter, and loss.
    """
    try:
        cmd = [
            "tc", "qdisc", "change", "dev", interface, "root", "netem",
            "rate", params['bw'],
            "delay", f"{params['latency']}", f"{params['jitter']}",
            "loss", params['loss']
        ]
        subprocess.run(cmd, check=True)
        print(f"Updated tc settings for {interface}")
    except subprocess.CalledProcessError as e:
        print(f"Error updating tc for {interface}: {e}")

def on_connect(client, userdata, flags, rc):
    """
    Callback for MQTT connection.

    Args:
        client: The MQTT client instance.
        userdata: User data passed during MQTT initialization.
        flags: MQTT connection flags.
        rc: Return code for connection.
    """
    print("Connected with result code " + str(rc))
    client.subscribe(f"{userdata['node_name']}/control/#")

def on_message(client, userdata, msg):
    """
    Callback for receiving MQTT messages.

    Args:
        client: The MQTT client instance.
        userdata: User data passed during MQTT initialization.
        msg: The MQTT message object.
    """
    print(f"Received message on {msg.topic}: {msg.payload.decode()}")
    topic_parts = msg.topic.split("/")
    if len(topic_parts) != 4:
        print("Invalid topic format")
        return

    _, _, interface, parameter = topic_parts
    if interface in userdata['interfaces'] and parameter in userdata['interfaces'][interface]:
        userdata['interfaces'][interface][parameter] = msg.payload.decode()
        control_bandwidth_and_latency(interface, userdata['interfaces'][interface])
    else:
        print("Unknown interface or parameter")

def exec_command(command):
    """
    Execute a shell command and return its output.

    Args:
        command (str): The shell command to execute.

    Returns:
        str: Output of the command.
    """
    process = subprocess.run(command, stdout=subprocess.PIPE, shell=True, text=True)
    return process.stdout.strip()

def get_network_bytes(interface):
    """
    Get the number of bytes sent and received for a network interface.

    Args:
        interface (str): The network interface name.

    Returns:
        tuple: Bytes sent and received as (bytes_sent, bytes_recv).
    """
    net_io = psutil.net_io_counters(pernic=True)
    if interface in net_io:
        return net_io[interface].bytes_sent, net_io[interface].bytes_recv
    return 0, 0

def main():
    """
    Main function to initialize and run the script.
    """
    # Get broker IP
    command = "ip route | grep net0 | awk '/src/ {print $9}'"
    broker_ip = exec_command(command)
    if not broker_ip:
        print("IP find failed")
        exit(1)
    parts = broker_ip.split(".")
    asn = parts[1]
    parts[-1] = "1"
    broker_ip = ".".join(parts)
    node_name = f'AS{asn}'
    print("Broker IP:", broker_ip)
    print("Node Name:", node_name)

    # Initialize interfaces
    interfaces = {
        interface: {'bw': '50mbit', 'latency': '5ms', 'loss': '0%', 'jitter': '0ms'}
        for interface in psutil.net_if_addrs() if 'ix' in interface
    }
    print("Interfaces:", interfaces)

    # Initialize tc settings
    init_tc(interfaces)

    # Initialize MQTT client
    client = mqtt.Client(userdata={'node_name': node_name, 'interfaces': interfaces})
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker_ip, 1883, 60)
        print("Connected to broker")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        exit(1)

    client.loop_start()
    time.sleep(1)  # Wait for MQTT connection to establish

    # Initialize previous byte counts
    prev_bytes = {interface: get_network_bytes(interface) for interface in interfaces}

    try:
        while True:
            for interface in interfaces:
                bytes_sent, bytes_recv = get_network_bytes(interface)
                prev_sent, prev_recv = prev_bytes[interface]
                bps_sent = bytes_sent - prev_sent
                bps_recv = bytes_recv - prev_recv
                total_bps = bps_sent + bps_recv
                client.publish(f"node/{node_name}/bandwidth/{interface}", total_bps)
                prev_bytes[interface] = (bytes_sent, bytes_recv)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping the script...")
    finally:
        client.loop_stop()

if __name__ == "__main__":
    main()
