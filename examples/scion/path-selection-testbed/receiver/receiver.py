import socket
import struct
import subprocess
import threading

UDP_IP = "0.0.0.0"
UDP_PORT = 9000
TCP_ACK_PORT = 5006
ACK_IP = ""

received_sequences = set()
sequence_lock = threading.Lock()

def exec_command(command):
    process = subprocess.run(command, stdout=subprocess.PIPE, shell=True, text=True)
    return process.stdout.strip()

def udp_receiver():
    global received_sequences
    # Create the main socket for receiving packets
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.bind((UDP_IP, UDP_PORT))
    print(f"UDP Receiver listening on port {UDP_PORT}")

    while True:
        data, addr = recv_sock.recvfrom(65535)  # Buffer size is 65535 bytes
        if len(data) < 4:
            print(f"Received packet too small from {addr}")
            continue
        # Extract sequence number
        seq_num = struct.unpack('!I', data[:4])[0]  # First 4 bytes as unsigned int
        with sequence_lock:
            received_sequences.add(seq_num)

def handle_client(conn, addr):
    global received_sequences
    print(f"Handling new TCP client from {addr}")
    received_num = 0
    try:
        while True:
            ack_data = None
            with sequence_lock:
                if len(received_sequences) > 0:
                    ack_data = [
                        struct.pack('!I', seq_num)
                        for seq_num in list(received_sequences)
                    ]
                    received_sequences.clear()  # Clear sent sequences
            if ack_data:
                for ack in ack_data:
                    conn.sendall(ack)
            if ack_data:
                received_num += len(ack_data)
    except (ConnectionResetError, BrokenPipeError):
        print(f"Connection with {addr} closed")
    finally:
        print(f"Total ACKs sent to {addr}: {received_num}")
        conn.close()

def tcp_ack_server():
    # Create TCP socket for ACKs
    ack_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ack_sock.bind((UDP_IP, TCP_ACK_PORT))
    ack_sock.listen(1)  # Allow up to 5 simultaneous connections
    print(f"TCP ACK server listening on port {TCP_ACK_PORT}")

    while True:
        conn, addr = ack_sock.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.start()

if __name__ == "__main__":
    udp_thread = threading.Thread(target=udp_receiver, daemon=True)
    tcp_thread = threading.Thread(target=tcp_ack_server, daemon=True)

    udp_thread.start()
    tcp_thread.start()

    udp_thread.join()
    tcp_thread.join()
