import pygame
import struct
import socket
import time

# open the serial port and exit if it fails
try:
    # Set up UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('10.72.0.2', 9006))
except:
    print("Error opening UDP socket")
    exit()


sendAddr = ('10.72.0.1',9006)

# Initialize the pygame module
pygame.init()

# Ensure joystick availability
if pygame.joystick.get_count() < 1:
    # No joysticks!
    print("Error, I didn't find any joysticks.")
else:
    # Use the first joystick
    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    # Function to read joystick values
    def read_joystick():
        pygame.event.pump()

        # Get joystick axes and buttons
        axes = [joystick.get_axis(i) for i in range(6)] # changed from 6 to 8
        buttons = [joystick.get_button(j) for j in range(2)]

        # Scale 10-bit axes values (-511 to 511)
        axes = [int(a * 511) for a in axes]

        return axes, buttons

    while True:
        start = time.time()

        # Read values from joystick
        axes, buttons = read_joystick()

        #print axes, buttons        
        print(axes[0], axes[1], axes[2], axes[3], axes[4], axes[5], buttons[0], buttons[1])

        # Pack data
        data = struct.pack('<6h2b', axes[0], axes[1], axes[2], axes[3], axes[4], axes[5], buttons[0], buttons[1]) 

        sock.sendto(data, sendAddr)

        time.sleep(0.01)