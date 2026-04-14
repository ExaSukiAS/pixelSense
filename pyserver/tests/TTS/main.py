import time
import pyaudio
from piper import PiperVoice

# Load voice
voice = PiperVoice.load("en_US-lessac-low.onnx")

p = pyaudio.PyAudio()
stream = None
text = input("Enter text to synthesize: ")

# Latency tracking variables
start_time = time.perf_counter()
first_chunk_time = None
total_audio_duration = 0.0

# Stream the audio
for chunk in voice.synthesize(text):
    if first_chunk_time is None:
        first_chunk_time = time.perf_counter()
        
        # Open stream on first chunk
        stream = p.open(
            format=p.get_format_from_width(chunk.sample_width),
            channels=chunk.sample_channels,
            rate=chunk.sample_rate,
            output=True
        )

    # Calculate duration of this chunk: (num_samples) / (sample_rate)
    # len(chunk.audio_int16_bytes) / 2 because each sample is 2 bytes (int16)
    chunk_duration = (len(chunk.audio_int16_bytes) / 2) / chunk.sample_rate
    total_audio_duration += chunk_duration
    
    stream.write(chunk.audio_int16_bytes)

# Total processing time
end_time = time.perf_counter()
total_process_time = end_time - start_time
ttfb = (first_chunk_time - start_time) * 1000  # Convert to ms
rtf = total_process_time / total_audio_duration if total_audio_duration > 0 else 0

# --- Latency Report ---
print("-" * 30)
print(f"Time to First Byte (TTFB): {ttfb:.2f} ms")
print(f"Total Audio Duration:      {total_audio_duration:.2f} s")
print(f"Total Processing Time:     {total_process_time:.2f} s")
print(f"Real-Time Factor (RTF):    {rtf:.4f}")
print("-" * 30)
# Note: RTF < 1.0 means it synthesizes faster than real-time.

if stream:
    stream.stop_stream()
    stream.close()
p.terminate()