import time
from RealtimeSTT import AudioToTextRecorder

def process_text(text):
    # This remains as your callback for the recognized text
    print(f"Recognized: {text}")

if __name__ == '__main__':
    print("Initializing STT...")
    
    recorder = AudioToTextRecorder(
        model="tiny.en", 
        compute_type="int8", 
        device="cpu",
        language="en"
    )

    print("Say something (Live STT active)...")

    while True:
        # Start the timer right before the transcription call
        start_time = time.time()
        
        # This call blocks until a sentence is finalized
        recorder.text(process_text)
        
        # Calculate the elapsed time
        latency = time.time() - start_time
        print(f"Latency: {latency:.2f} seconds\n")