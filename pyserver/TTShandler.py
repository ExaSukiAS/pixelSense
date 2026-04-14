import pyaudio
from piper import PiperVoice
import threading
import queue

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

    def queueTextForSynth(self, textChunk: str):
        self.textQueue.put(textChunk)

    def _worker(self):
        # background loop that waits for text and processes it.
        while True:
            text = self.textQueue.get()
            if text is None: break 
            
            self._processSynthesis(text)
            
            # signal that this item is done
            self.textQueue.task_done()
            
            # check if queue is empty to trigger completion callback
            if self.textQueue.empty() and self.onSynthComplete:
                self.onSynthComplete()

    def _processSynthesis(self, text):
        for chunk in self.voice.synthesize(text):
            if self.onAudioSamples:
                self.onAudioSamples(chunk.audio_int16_bytes)

            if self.playAudio:
                if self.stream is None:
                    self.stream = self.pa.open(
                        format=self.pa.get_format_from_width(chunk.sample_width),
                        channels=chunk.sample_channels,
                        rate=chunk.sample_rate,
                        output=True
                    )
                self.stream.write(chunk.audio_int16_bytes)