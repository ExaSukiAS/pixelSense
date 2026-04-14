from pydub import AudioSegment
import socket 
import time
import struct

ESPIP = "192.168.68.106"
PORT = 9001

def getPCMsamples(filePath, samplingRate):
    print(f"Loading {filePath}...")
    audio = AudioSegment.from_file(filePath, format="wav")
    
    # Force mono, 12000Hz, and 16-bit (2 bytes per sample)
    audio = audio.set_channels(1).set_frame_rate(samplingRate).set_sample_width(2)
    
    # Dynamically get the length instead of hardcoding
    audioTrackLength = audio.duration_seconds
    rawPCM = audio.raw_data
    
    totalSize = len(rawPCM)
    sizeRate = totalSize / audioTrackLength if audioTrackLength > 0 else 0

    print(f"Track duration: {audioTrackLength:.2f} seconds")
    print(f"Raw PCM size: {totalSize} Bytes")
    print(f"Packet sending rate: {sizeRate:.2f} Bytes/s")
    return rawPCM

def sendSamples(rawPCM, samplingRate):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 1000 bytes = 500 samples
    packetSize = 1000 
    
    # calculate exactly how much audio time is in one packet
    # 500 samples / 12000 samples per second = ~0.04166 seconds
    packet_duration = (packetSize / 2) / samplingRate 
    
    print(f"Starting stream. Packet duration: {packet_duration*1000:.2f}ms")
    
    packet_id = 0
    startTime = time.time()

    for i in range(0, len(rawPCM), packetSize):
        packet = rawPCM[i:i+packetSize]
        
        # create the 4-byte header
        data = struct.pack("I", packet_id) + packet
        sock.sendto(data, (ESPIP, PORT))
        packet_id += 1
        
        expectedTime = startTime + (packet_id * packet_duration)
        sleepTime = expectedTime - time.time()
        
        # nnly sleep if we are actually ahead of schedule
        if sleepTime > 0:
            time.sleep(sleepTime)

    print("Finished sending audio stream.")

rawPCM = getPCMsamples("18sec.wav", 12000)
sendSamples(rawPCM, 12000)