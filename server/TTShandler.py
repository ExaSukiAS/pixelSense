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
        self.stopEvent = threading.Event() # flag to signal interruption

        self.voice = PiperVoice.load("AImodels/en_US-lessac-low.onnx")
        self.pa = pyaudio.PyAudio()
        self.stream = None
        
        # Lock to prevent thread collisions on the PyAudio stream
        self.audioLock = threading.Lock()

        # thread-safe queue for incoming text
        self.textQueue = queue.Queue()
        
        # start the background thread
        self.workerThread = threading.Thread(target=self._worker, daemon=True)
        self.workerThread.start()

        self.samplingRate = 12000 

    def queueTextForSynth(self, textChunk: str):
        self.textQueue.put(textChunk)

    # Interrupts current synthesis and clears the queue
    def stopRunningSynth(self):
        self.stopEvent.set()
        
        # clear all pending text in the queue
        with self.textQueue.mutex:
            self.textQueue.queue.clear()
            
        # Safely stop and close the audio stream buffer with a lock
        with self.audioLock:
            if self.stream is not None:
                try:
                    if self.stream.is_active():
                        self.stream.stop_stream()
                    self.stream.close()
                except Exception as e:
                    print(f"Error closing TTS stream: {e}")
                
                # Set to None so the worker thread recreates it cleanly later
                self.stream = None

    def _worker(self):
        # background loop that waits for text and processes it.
        while True:
            text = self.textQueue.get()
            if text is None: break 

            self.stopEvent.clear()
            
            self._processSynthesis(text)
            
            self.textQueue.task_done()
            
            # check if queue is empty to trigger completion callback
            if self.textQueue.empty() and self.onSynthComplete:
                self.onSynthComplete()

    def _processSynthesis(self, text):        
        for chunk in self.voice.synthesize(text):
            # check if we were told to stop mid-synthesis
            if self.stopEvent.is_set():
                break

            audioData = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16)
            
            numSamples = int(len(audioData) * self.samplingRate / chunk.sample_rate)
            resampledAudio = signal.resample(audioData, numSamples).astype(np.int16)
            
            resampled_bytes = resampledAudio.tobytes()

            if self.onAudioSamples:
                self.onAudioSamples(resampled_bytes)

            if self.playAudio:
                # Wrap PyAudio interactions in the thread lock
                with self.audioLock:
                    # Double-check stop event before writing to avoid lag-spikes
                    if self.stopEvent.is_set():
                        break
                        
                    if self.stream is None:
                        try:
                            self.stream = self.pa.open(
                                format=self.pa.get_format_from_width(chunk.sample_width),
                                channels=chunk.sample_channels,
                                rate=self.samplingRate, 
                                output=True
                            )
                        except Exception as e:
                            print(f"PyAudio TTS Open Error: {e}")
                            continue
                            
                    try:
                        self.stream.write(resampled_bytes)
                    except Exception as e:
                        print(f"PyAudio TTS Write Error: {e}")