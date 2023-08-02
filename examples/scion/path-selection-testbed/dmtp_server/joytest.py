import pygame
import struct
import serial
import time

# open the serial port and exit if it fails
try:
    ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=.5)
except:
    print("Error, I didn't find any serial port.")
    exit()

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

        # Compute CRC
        # crc = binascii.crc32(data)

        # Serialize data with CRC
        # serialized_data = struct.pack('<6h2bI', axes[0], axes[1], axes[2], axes[3], axes[4], axes[5], buttons[0], buttons[1], crc) 
        # print(serialized_data)

   
        # ser.write(data)

        # read text from the serial port
        # text = ser.readline().decode('utf-8')
        # print(text)

        # Limit loop to 100Hz
        # time.sleep(max(0, 0.01 - (time.time() - start)))
        time.sleep(0.01)  