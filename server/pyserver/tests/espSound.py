import numpy as np
import socket
import pyaudio
import struct
import time
import audioop

espIP = "192.168.68.105"
espUDPport = 9001
sendingPort = 5005
receivingPort = 5006

# initialize PyAudio
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=8000, output=True, frames_per_buffer=128)

# initialize Socket
speakerUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
speakerUDP.bind(("0.0.0.0", sendingPort))

micUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
micUDP.bind(("0.0.0.0", receivingPort))

print(f"Sending handshake to {espIP}...")
speakerUDP.sendto(b'handshakeMessage', (espIP, espUDPport))

espConnected = False

def streamSystemAudio(gain):
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        print(f"Index {i}: {dev['name']}")

    inputRate = 48000
    targetRate = 12000
    packetSize = 1000
    
    # state for the rate converter (required by audioop.ratecv)
    state = None

    stream = p.open(format=pyaudio.paInt16,
                    channels=2,
                    rate=inputRate,
                    input=True,
                    input_device_index=11,
                    frames_per_buffer=packetSize)

    print(f"Capturing at {inputRate}Hz, Downsampling to {targetRate}Hz...")
    
    packet_id = 0
    try:
        while True:
            pcm_data = stream.read(packetSize, exception_on_overflow=False) # raw PCM from Windows (Stereo, 48kHz)
            mono_data = audioop.tomono(pcm_data, 2, 1, 0) # convert stereo to mono
            
            # downsample from 48000 to 12000
            downsampled_data, state = audioop.ratecv(
                mono_data, 2, 1, inputRate, targetRate, state
            )
        
            amplified_data = audioop.mul(downsampled_data, 2, gain) # apply gain
            
            # package and send
            header = struct.pack("<I", packet_id)
            data = header + amplified_data
            
            speakerUDP.sendto(data, (espIP, espUDPport))
            
            packet_id += 1

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        stream.stop_stream()
        stream.close()

while True:
    data, addr = speakerUDP.recvfrom(512)
    if data == b'receivedPacket':
        if not espConnected:
            print("esp connected!")
            espConnected = True
            break

streamSystemAudio(1.0)

while True:
    data, addr = micUDP.recvfrom(512)
    stream.write(data)
