import pyaudio
import struct
import sys

# Configuration
FORMAT = pyaudio.paInt16  # 16-bit
CHANNELS = 1              # Mono
RATE = 8000               # 8kHz
CHUNK = 1024              # Samples per buffer

p = pyaudio.PyAudio()

# Optional: List devices to find your Loopback/Stereo Mix index
# for i in range(p.get_device_count()):
#     print(i, p.get_device_info_by_index(i)['name'])

try:
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("--- Capturing Audio (Press Ctrl+C to Stop) ---")

    while True:
        # Read raw binary data from the stream
        data = stream.read(CHUNK, exception_on_overflow=False)
        
        # Convert binary data to a tuple of 16-bit integers
        # 'h' represents a signed short (16-bit) in Python's struct
        count = len(data) // 2
        format_string = f"{count}h"
        samples = struct.unpack(format_string, data)
        
        # Print samples to the console
        for s in samples:
            print(s)

except KeyboardInterrupt:
    print("\n--- Stopping ---")

finally:
    stream.stop_stream()
    stream.close()
    p.terminate()