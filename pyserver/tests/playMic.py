import numpy as np
import socket
import pyaudio
import websocket # Import the websocket library

# Configuration
SAMPLING_RATE = 8000
CHUNK_SIZE = 128
espIP = "192.168.68.106"
udpPort = 9001
tcpPort = 9000 # This is the WebSocket port
computerPort = 5006

# Initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLING_RATE,
                output=True,
                frames_per_buffer=CHUNK_SIZE)

# Initialize UDP Socket (for receiving the audio stream later)
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind(("0.0.0.0", computerPort))

# Connect to the ESP32 via WebSocket
print(f"Connecting to WebSocket at ws://{espIP}:{tcpPort}...")
ws_url = f"ws://{espIP}:{tcpPort}"
try:
    ws = websocket.create_connection(ws_url)
    print("WebSocket connected!")
    
    # Send the command over WebSocket
    print("Sending mic stream request...")
    ws.send("startAudioStream") # Sends proper WS text frame
    
except Exception as e:
    print(f"WebSocket connection failed: {e}")
    exit()

# Now listen for the UDP audio packets coming back
print(f"Listening for UDP audio on port {computerPort}...")
while True:
    data, addr = udp.recvfrom(512) 

    # 1. Play the raw bytes immediately for real-time sound
    stream.write(data)

    # 2. (Optional) Visual analysis
    audio_array = np.frombuffer(data, dtype=np.int16)
    volume = np.mean(np.abs(audio_array))
    print(f"Volume: {volume:6.2f} | Peak: {np.max(np.abs(audio_array)):3d}")