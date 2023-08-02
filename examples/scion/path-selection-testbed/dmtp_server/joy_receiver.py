import socket
import struct
import serial

# Open the serial port
ser = serial.Serial('/dev/ttyUSB0', 115200)

# Set up UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('10.72.0.1', 9006))

while True:
    data, addr = sock.recvfrom(1024)
    ser.write(data)

    values = struct.unpack('<6h2B', data)
    print(values)