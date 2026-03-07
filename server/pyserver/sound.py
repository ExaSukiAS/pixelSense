import audioop
from pydub import AudioSegment
import sounddevice as sd
import numpy as np
import socket 
import time
import struct

SAMPLING_RATE = 8000 
audioTrackLength = 18

def get_compressed_samples(file_path):
    audio = AudioSegment.from_file(file_path, format="wav")
    audio = audio.set_channels(1).set_frame_rate(SAMPLING_RATE).set_sample_width(2)
    
    # Get raw 16-bit PCM bytes
    raw_pcm = audio.raw_data
    
    # Convert 16-bit PCM to 8-bit Mu-law
    # '2' means 2 bytes per sample (16-bit) input
    mu_law_data = audioop.lin2ulaw(raw_pcm, 2)
    
    # Now each sample is only 1 byte (0-255)
    samples = list(mu_law_data)
    
    totalSize = len(samples) # total data
    sizeRate = totalSize/audioTrackLength # data/second

    print(f"Compressed size: {totalSize} B")
    print(f"{sizeRate} B/s")
    return samples

def test_playback(mu_law_samples):
    mu_law_bytes = bytes(mu_law_samples)
    
    # Decompress back to 16-bit PCM
    pcm_data = audioop.ulaw2lin(mu_law_bytes, 2)
    
    # Convert to a format sounddevice understands (numpy array)
    audio_array = np.frombuffer(pcm_data, dtype=np.int16)
    
    sd.play(audio_array, SAMPLING_RATE)
    sd.wait() # Wait until finished
    print("Playback finished.")

def sendSamples(samples):
    ESPIP = "192.168.68.107"
    PORT = 5005
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    packetSize = 600
    packet_id = 0

    for i in range(0, len(samples), packetSize):
        packet = samples[i:i+packetSize]
        data = struct.pack("I", packet_id) + bytes(packet)
        sock.sendto(data, (ESPIP, PORT))
        packet_id += 1
        time.sleep(0.09)

# Run it
samples = get_compressed_samples("18sec.wav")
sendSamples(samples)

