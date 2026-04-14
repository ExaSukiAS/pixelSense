import pyaudio
from piper import PiperVoice
import threading
import queue
import numpy as np
from scipy import signal

class TTS:
    def __init__(self, onAudioSamples=None, onSynthComplete=None):
        self.onAudioSamples = onAudioSamples
        self.onSynthComplete = onSynthComplete

        self.playAudio = True

        self.voice = PiperVoice.load("AImodels/en_US-lessac-low.onnx")
        self.pa = pyaudio.PyAudio()
        self.stream = None

        # thread-safe queue for incoming text
        self.textQueue = queue.Queue()
        
        # start the background thread
        self.workerThread = threading.Thread(target=self._worker, daemon=True)
        self.workerThread.start()

        self.samplingRate = 12000 

    def queueTextForSynth(self, textChunk: str):
        self.textQueue.put(textChunk)

    def _worker(self):
        # background loop that waits for text and processes it.
        while True:
            text = self.textQueue.get()
            if text is None: break 
            
            self._processSynthesis(text)
            
            self.textQueue.task_done()
            
            # check if queue is empty to trigger completion callback
            if self.textQueue.empty() and self.onSynthComplete:
                self.onSynthComplete()

    def _processSynthesis(self, text):        
        for chunk in self.voice.synthesize(text):
            audioData = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
            
            numSamples = int(len(audioData) * self.samplingRate / chunk.sample_rate)
            resampledAudio = signal.resample(audioData, numSamples).astype(np.int16)
            
            resampled_bytes = resampledAudio.tobytes()

            if self.onAudioSamples:
                self.onAudioSamples(resampled_bytes)

            if self.playAudio:
                if self.stream is None:
                    self.stream = self.pa.open(
                        format=self.pa.get_format_from_width(chunk.sample_width),
                        channels=chunk.sample_channels,
                        rate=self.samplingRate, 
                        output=True
                    )
                self.stream.write(resampled_bytes)