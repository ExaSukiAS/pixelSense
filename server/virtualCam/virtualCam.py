import cv2
import pyvirtualcam
import numpy as np
import socket
import struct
from termcolor import colored
import time

HOST = 'localhost'
PORT = 8002

IMGWIDTH, IMGHEIGHT = 640, 480

# Create a TCP server socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)
print(colored(f"\nListening on {HOST}:{PORT}", "green", attrs=["bold"]))

# Accept a connection from the Node.js server
conn, addr = server.accept()
print(f"Connected by {addr}")

with pyvirtualcam.Camera(width=640, height=480, fps=30) as cam:
    while True:
        try:
            # 1. Read the 4-byte header
            header = conn.recv(4)
            if not header: break
            
            # Unpack the 4 bytes into an integer (Big Endian)
            image_size = struct.unpack('>I', header)[0]
            
            # 2. Read exactly image_size bytes
            image_data = b""
            while len(image_data) < image_size:
                packet = conn.recv(image_size - len(image_data))
                if not packet: break
                image_data += packet
            
            # 3. Process image
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is not None:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                cam.send(img_rgb)
                cam.sleep_until_next_frame()
                conn.sendall(b"success\n")

        except Exception as e:
            print(f"Error: {e}")
            break