import numpy as np
import pyaudio
import threading

class DepthToAudio:
    def __init__(self):
        # Audio configuration
        self.nativeSamplingRate = 44100 
        self.espSamplingRate = 12000
        self.audioBit = 16
        self.baseFreq = 130
        self.startTickDuration = 0.02
        
        self.playingAudio = False # tracks if audio is already being played to avoid overlapping processes

        self.startTickSamples = self._getStartTickSamples(self.startTickDuration)

    # Generates a soft, natural 'tick' (like a sonar ping) to indicate the left edge
    def _getStartTickSamples(self, duration):
        t = np.linspace(0, duration, int(self.nativeSamplingRate * duration), endpoint=False)
        envelope = np.exp(-t * 150) 
        # use a pure sine tone instead of white noise for a cleaner, less harsh tick
        ping = np.sin(2 * np.pi * 1000 * t) * envelope * 0.5
        return ping
    
    """
    Generates frequencies based on a Pentatonic scale. 
    This prevents dissonant, clashing frequencies and reduces ear fatigue.
    """
    def _getPentatonicScale(self, numNotes):
        intervals = [0, 2, 4, 7, 9] # Semitone intervals for major pentatonic
        scale = []
        for i in range(numNotes):
            octave = i // 5
            note_index = i % 5
            semitones = (octave * 12) + intervals[note_index]
            freq = self.baseFreq * (2 ** (semitones / 12.0))
            # Cap frequencies to prevent distortion
            if freq > 3000: 
                freq = 3000
            scale.append(freq)
        return np.array(scale)[::-1] # Reverse so high pitches represent the top of the image
    

    # helper function to play the audio based on the depth matrix
    def _processAndPlay(self, depthMatrix, duration, maxDistance):
        h, w = depthMatrix.shape
        
        # Group the rows into 20 distinct frequency bands
        target_bands = 20
        row_group_size = max(1, h // target_bands)
        
        pooled_depth = []
        for i in range(0, h, row_group_size):
            band = depthMatrix[i:i+row_group_size, :]
            pooled_depth.append(np.mean(band, axis=0))
        pooled_depth = np.array(pooled_depth)
        h_pooled = pooled_depth.shape[0]
        
        total_samples = int(self.nativeSamplingRate * duration)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        
        # EQUAL POWER PANNING
        pan_progress = np.linspace(0, 1, total_samples)

        # S-curve mimics how human ears perceive spatial movement
        s_curve_pan = 0.5 * (1 - np.cos(np.pi * pan_progress)) 
        pan_L = np.sqrt(1.0 - s_curve_pan) 
        pan_R = np.sqrt(s_curve_pan)
        
        # MUSICAL FREQUENCY ASSIGNMENT
        freqs = self._getPentatonicScale(h_pooled)
        
        audio_L = np.zeros(total_samples)
        audio_R = np.zeros(total_samples)
        x_original = np.linspace(0, 1, w)

        for y in range(h_pooled):
            # EXPONENTIAL PROXIMITY SCALING
            normalized_depth = np.clip(1.0 - (pooled_depth[y, :] / maxDistance), 0.0, 1.0)
            row_volumes = normalized_depth ** 4 
            
            volume_envelope = np.interp(pan_progress, x_original, row_volumes)
            
            # NATURAL TIMBRE (Harmonic Layering)
            f = freqs[y]
            sine_wave = (
                np.sin(2 * np.pi * f * t) + 
                0.4 * np.sin(2 * np.pi * (f * 1.5) * t) + # Perfect fifth
                0.2 * np.sin(2 * np.pi * (f * 2.0) * t)   # Octave
            )
            
            row_audio = sine_wave * volume_envelope
            
            audio_L += row_audio * pan_L
            audio_R += row_audio * pan_R

        # Add Scanning Tick
        audio_L[:len(self.startTickSamples)] += self.startTickSamples
        audio_R[:len(self.startTickSamples)] += self.startTickSamples * 0.1 

        # Force perfectly interleaved 1D array layout [L, R, L, R...] for PyAudio
        stereo_audio = np.empty(total_samples * 2, dtype=np.float32)
        stereo_audio[0::2] = audio_L
        stereo_audio[1::2] = audio_R

        # Normalize Audio
        max_peak = np.max(np.abs(stereo_audio))
        if max_peak > 0:
            stereo_audio = (stereo_audio / max_peak) * 0.85 

        # PyAudio Playback
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32,
                        channels=2,
                        rate=self.nativeSamplingRate,
                        output=True)
        
        stream.write(stereo_audio.tobytes())
        stream.stop_stream()
        stream.close()
        p.terminate()

        self.playingAudio = False

    """ 
    exposed function to play the audio based on the depth map
    Depth map must be in 160x120 size
    """
    def playDepthAudio(self, depthMap, duration, maxDistance):
        if self.playingAudio == True:
            return

        self.playingAudio = True

        depthMatrix = np.array(depthMap, dtype=float)
        
        thread = threading.Thread(
            target=self._processAndPlay,
            args=(depthMatrix, duration, maxDistance),
            daemon=True
        )
        thread.start()