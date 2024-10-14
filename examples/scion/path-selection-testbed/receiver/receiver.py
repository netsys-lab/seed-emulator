# udp_receiver.py

import socket
import struct

UDP_IP = "0.0.0.0"
UDP_PORT = 9000
ACK_PORT = 5006  # The port to send ACKs back to the sender

def receiver():
    # Create the main socket for receiving packets
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.bind((UDP_IP, UDP_PORT))
    ack_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"Receiver listening on port {UDP_PORT}")

    received_sequences = set()

    while True:
        data, addr = recv_sock.recvfrom(65535)  # Buffer size is 65535 bytes
        if len(data) < 4:
            print(f"Received packet too small from {addr}")
            continue

        # Extract sequence number
        seq_num = struct.unpack('!I', data[:4])[0]  # First 4 bytes as unsigned int
        received_sequences.add(seq_num)

        # Send ACK back using the same socket
        ack_data = struct.pack('!I', seq_num)
        ack_sock.sendto(ack_data, (addr[0], ACK_PORT))

if __name__ == "__main__":
    receiver()
