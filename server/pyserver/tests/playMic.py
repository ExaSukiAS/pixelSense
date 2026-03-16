import numpy as np
import socket
import pyaudio

# Configuration
SAMPLING_RATE = 8000
CHUNK_SIZE = 128 # Matches your udpStreamPacketSize
espIP = "192.168.68.105"
udpPort = 9001

# Initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLING_RATE,
                output=True,
                frames_per_buffer=CHUNK_SIZE)

# Initialize Socket
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind(("0.0.0.0", 5005))

print(f"Sending handshake to {espIP}...")
udp.sendto(b'handshakeMessage', (espIP, udpPort))

espConnected = False

try:
    while True:
        data, addr = udp.recvfrom(512) # Larger buffer to ensure we don't drop packets

        if data == b'receivedPacket':
            if not espConnected:
                espConnected = True
                print("ESP32 Connected! Streaming audio...")
            continue

        if espConnected:
            # 1. Play the raw bytes immediately for real-time sound
            stream.write(data)

            # 2. (Optional) Visual analysis
            audio_array = np.frombuffer(data, dtype=np.int16)
            volume = np.mean(np.abs(audio_array))
            print(f"Volume: {volume:6.2f} | Peak: {np.max(np.abs(audio_array)):3d}")
            
except KeyboardInterrupt:
    print("\nStopping stream...")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    udp.close()