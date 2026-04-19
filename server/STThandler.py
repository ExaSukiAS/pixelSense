import numpy as np
import threading
from RealtimeSTT import AudioToTextRecorder
from termcolor import colored

class STT:
    def __init__(self, onTranscription):
        self.onTranscription = onTranscription
        self.recorder = None
        self.isListening = False

        self.recorder = AudioToTextRecorder(
            model="tiny.en", 
            compute_type="int8", 
            device="cpu",
            language="en",
            use_microphone=False,
            spinner=False
        )
        print(colored("STT initialized!", "light_green"))

    def _sttWorker(self):
        if self.recorder:
            text = self.recorder.text()
            
            if text and text.strip() != "" and self.onTranscription:
                self.onTranscription(text)
        
        # after one sentence is caught, reset the listening state
        self.isListening = False
        print("STT stopped automatically.")

    def startRecording(self):
        # triggers a single-shot recording session
        if not self.isListening:
            self.isListening = True
            print("STT: Listening for one sentence...")
            # Start a single-run thread
            threading.Thread(target=self._sttWorker, daemon=True).start()
        else:
            print("STT is already waiting for a sentence.")
    
    def feedAudioSamples(self, samples):
        self.recorder.feed_audio(samples)