// handles touch sensors, buzzer, speaker and microphone

#ifndef PERIPHERALS_H
#define PERIPHERALS_H

#include <Arduino.h>
#include <math.h>
#include <driver/i2s.h>

class Speaker{
    private:
        // I2S pins
        int channelPin;
        int clockPin;
        int dataPin;

        #define I2S_PORT I2S_NUM_1 

        const uint32_t samplingRate = 12000; // 12khz audio
        float gain = 1;
    public:
        // buffer settings
        static const uint16_t jitterBufferSize = 30000;
        int16_t jitterBuffer[jitterBufferSize]; // circular buffer to store audio samples
        volatile int head = 0; // index pointer for storing sample to jitterBuffer
        volatile int tail = 0; // index pointer for playing sample from jitterBuffer
        volatile bool isBuffering = true; // flag to determine whether to play audio or store samples in jitterBuffer
        const int prefillThresh = 2400; // ~200ms of audio (audio starts playing when jitterBuffer has atleast prefillThresh amount of samples)

        bool attachState = false; // flag to indicate if speaker is attached or not

        volatile bool lockI2Sport = false; // locks teh speaker I2S port so that there's no conflict when using the mic

        enum ToneType {
            TOUCH1_SINGLE, TOUCH1_DOUBLE, TOUCH1_HOLD,
            TOUCH2_SINGLE, TOUCH2_DOUBLE, TOUCH2_HOLD, ERROR
        };

        // constructor
        Speaker(int BCLKpin, int LRCpin, int DINpin, float amplificationGain){
            channelPin = LRCpin;
            clockPin = BCLKpin;
            dataPin = DINpin;
            
            gain = amplificationGain;
        }

        // attaches speaker
        void attach() {
            if (attachState) return;

            const i2s_config_t i2s_config = { 
                .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
                .sample_rate = samplingRate,
                .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
                .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
                .communication_format = I2S_COMM_FORMAT_STAND_I2S,
                .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
                .dma_buf_count = 8,
                .dma_buf_len = 256,
                .use_apll = false
            };

            i2s_pin_config_t pin_config = {
                .bck_io_num = clockPin,
                .ws_io_num = channelPin,
                .data_out_num = dataPin,
                .data_in_num = -1
            };

            i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
            i2s_set_pin(I2S_PORT, &pin_config);
            i2s_start(I2S_PORT);
            attachState = true;
        } 

        // detaches speaker so that the clock and channel select pin can be used by an another I2S device
        void detach(){
            if (!attachState) return;

            i2s_stop(I2S_PORT);
            i2s_driver_uninstall(I2S_PORT);
            attachState = false;
        }

        // used so that we can run audioPlayingTask() as a saperate task
        static void speakerTaskWrapper(void *param) {
            Speaker* self = (Speaker*)param;
            self->audioPlayingTask();
        }

        // plays audio samples from the jitter buffer
        void audioPlayingTask(){
            for (;;) {
                if (lockI2Sport) {
                    vTaskDelay(10 / portTICK_PERIOD_MS);
                    continue;
                }

                int available = (head - tail + jitterBufferSize) % jitterBufferSize; // number of available samples

                // determine whether to play the audio or wait for enough samples
                if (isBuffering) {
                    if (available >= prefillThresh) {
                        isBuffering = false;
                    } else {
                        vTaskDelay(10 / portTICK_PERIOD_MS);
                        continue; 
                    }
                }
                if (available < 256) {
                    if (available == 0) isBuffering = true; 
                    vTaskDelay(2 / portTICK_PERIOD_MS);
                    continue;
                }

                int toPlay = 128;
                int16_t pcmOut[128];

                // fill the pcmOut array with amplified audio samples
                for (int i = 0; i < toPlay; i++) {
                    int32_t amplified = jitterBuffer[tail] * gain; // amplification
                    
                    // clamping
                    if(amplified > 32767) amplified = 32767;
                    if(amplified < -32768) amplified = -32768;
                    
                    pcmOut[i] = (int16_t)amplified;
                    tail = (tail + 1) % jitterBufferSize;
                }

                if(!attachState) attach();

                // play the audio samples
                size_t bytes_written;
                i2s_write(I2S_PORT, pcmOut, toPlay * sizeof(int16_t), &bytes_written, portMAX_DELAY);
            }
        } 
        
        // plays frequency based on duration (params: int, int)
        void playFreq(int freq, int durationMs) {
            if (freq <= 0) {
                // treat as silence
                int silenceSamples = (samplingRate * durationMs) / 1000;
                for (int i = 0; i < silenceSamples; i++) {
                    jitterBuffer[head] = 0;
                    head = (head + 1) % jitterBufferSize;
                }
                return;
            }

            int numSamples = (samplingRate * durationMs) / 1000;
            for (int i = 0; i < numSamples; i++) {
                // sine wave: amplitude * sin(2 * PI * freq * time)
                // using 1000 as a base amplitude before user amplification
                float t = (float)i / (float)samplingRate;
                int16_t sample = (int16_t)(1000 * sin(2 * PI * freq * t));
                
                jitterBuffer[head] = sample;
                head = (head + 1) % jitterBufferSize;
            }
        }

        // plays frequency based on toggle (params: int, bool)
        void playFreq(int freq, bool toggle) {
            if (toggle) {
                playFreq(freq, 50); 
            } else {
                // Stop/Silence
                isBuffering = true; // force a buffer reset/pause 
                head = tail; // clear software buffer
                i2s_zero_dma_buffer(I2S_PORT); // clear the hardware DMA buffer to stop the repeating tone
            }
        }

        // plays a certain tone
        void playTone(ToneType tone) {
            switch(tone) {
                case TOUCH1_SINGLE:
                    playFreq(500, 100);
                    playFreq(2000, 100);
                    break;
                case TOUCH1_DOUBLE:
                    playFreq(1000, 100);
                    playFreq(3000, 100);
                    break;
                case TOUCH1_HOLD:
                    playFreq(1500, 300);
                    break;
                case TOUCH2_SINGLE:
                    playFreq(2000, 100);
                    playFreq(500, 100);
                    break;
                case TOUCH2_DOUBLE:
                    playFreq(3000, 100);
                    playFreq(1000, 100);
                    break;
                case TOUCH2_HOLD:
                    playFreq(2500, 300);
                    break;
                case ERROR:
                    for(int i=0; i<2; i++) {
                        playFreq(2000, 600);
                        playFreq(0, 600);
                    }
                    break;
            }
        }
};

class Microphone{
    private:
        // I2S pins
        int channelPin;
        int clockPin;
        int dataPin;

        #define I2S_PORT I2S_NUM_1 

        const uint32_t samplingRate = 8000;
        float gain = 1;
    public:
        static const uint16_t micBufferSize = 128;
        int16_t micSamples[micBufferSize]; // stores the audio samples to send via UDP

        bool audioStreamingStarted = false; // flag for audio streaming state
        bool audioSamplesReady = false; //  flag to determine whether audio samples are reday to send

        bool attachState = false; // flag to indicate if mic is attached or not

        // constructor
        Microphone(int SCKpin, int WSpin, int SDpin, float amplificationGain){
            channelPin = WSpin;
            clockPin = SCKpin;
            dataPin = SDpin;

            gain = amplificationGain;
        }
        
        // attaches mic
        void attach(){
            if (attachState) return;

            const i2s_config_t i2s_config = {
                .mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_RX),
                .sample_rate = samplingRate,
                .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
                .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
                .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_STAND_I2S),
                .intr_alloc_flags = 0,
                .dma_buf_count = 8,
                .dma_buf_len = 128,
                .use_apll = false
            };
            const i2s_pin_config_t pin_config = {
                .bck_io_num = clockPin,
                .ws_io_num = channelPin,
                .data_out_num = -1,
                .data_in_num = dataPin
            };
            
            i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
            i2s_set_pin(I2S_PORT, &pin_config);
            i2s_start(I2S_PORT);
            delay(50);
            attachState = true;
        }

        // detaches mic so that the clock and channel select pin can be used by an another I2S device
        void detach(){
            if(!attachState) return;

            i2s_stop(I2S_PORT);
            i2s_driver_uninstall(I2S_PORT);
            attachState = false;
        }

        // used so that we can run audioCaptureTask() as a saperate task
        static void micTaskWrapper(void *param) {
            Microphone* self = (Microphone*)param;
            self->audioCaptureTask();
        }

        // captures audio samples from teh microphone
        void audioCaptureTask(){
            int sampleCount = 0;
            float filteredValue = 0;
            int16_t lastRaw = 0;

            for(;;){
                if(!audioStreamingStarted){
                    sampleCount = 0;
                    vTaskDelay(10);
                    continue;
                }
                if(audioSamplesReady){
                    vTaskDelay(1);
                    continue;
                }

                if(!attachState) attach();

                size_t bytesIn = 0;
                int16_t rawBuffer[64]; 
                esp_err_t result = i2s_read(I2S_PORT, &rawBuffer, sizeof(rawBuffer), &bytesIn, portMAX_DELAY);

                if (result == ESP_OK && bytesIn > 0) {
                    int samplesRead = bytesIn / 2; 

                    for (int i = 0; i < samplesRead; i++) {
                        filteredValue = 0.99 * (filteredValue + (float)rawBuffer[i] - (float)lastRaw); // high-pass filter to remove DC offset
                        float boostedValue = filteredValue * gain; // amplify

                        // clamp
                        if (boostedValue > 32767) boostedValue = 32767;
                        if (boostedValue < -32768) boostedValue = -32768;
                        lastRaw = rawBuffer[i];

                        micSamples[sampleCount] = (int16_t)boostedValue;
                        
                        sampleCount++;

                        if (sampleCount >= micBufferSize) {
                            audioSamplesReady = true;
                            sampleCount = 0; 
                            break; 
                        }
                    }
                }
            }
        }
};

// Touch sensor class with single tap, double tap and hold detection
class TouchSensor{
  private:
    int pin;
    unsigned long lastChangeTime = 0;
    unsigned long touchStart = 0;
    unsigned long lastTapTime = 0;      // time of last release
    unsigned long pendingTapTime = 0;   // time we started waiting for a possible double-tap
    bool lastTouched = false;
    bool pendingSingleTap = false;

    const unsigned long doubleTapWindow = 300; 
    const unsigned long holdWindow = 500;     
  public:
    // constructor to initialize touch sensor pin
    TouchSensor(int touchPin) {
      pinMode(touchPin, INPUT_PULLUP);
      pin = touchPin;
    }

    // Reads touch sensors
    bool readTouch() {
        // Read the touch sensor multiple times to get a more stable reading
        const int numReadings = 5;  
        int totalScore = 0;     
        for (int i = 0; i < numReadings; i++) {
            totalScore += digitalRead(pin);
        }
        float score = 1 - (totalScore / (float)numReadings);  

        return (score > 0.7); // Return true if the score is above threshold (considered pressed)
    }

    // Call frequently from loop(). Returns:
    // 0 = no event
    // 1 = single tap (emitted after doubleTapWindow expires without second tap)
    // 2 = double tap
    // 3 = hold (touch lasted >= holdWindow)
    int getTouchState() {
      unsigned long now = millis();
      bool touched = readTouch();

      // detect state changes
      if (touched != lastTouched) {
        lastChangeTime = now;
        if (touched) {
          touchStart = now; // touch started
        } else {
          if (pendingSingleTap && (now - pendingTapTime) <= doubleTapWindow) { // double tap detection
            pendingSingleTap = false;
            lastTouched = touched;
            return 2;
          } else {
            pendingSingleTap = true;
            pendingTapTime = now;
          }
        }
      } else if (touched && (now - touchStart) >= holdWindow) { // hold detection
        lastTouched = false;
        pendingSingleTap = false;
        return 3;
      }

      if (pendingSingleTap && (now - pendingTapTime) > doubleTapWindow) { // single tap detection
        pendingSingleTap = false;
        lastTouched = touched;
        return 1;
      }

      lastTouched = touched;
      return 0;
    }
};

#endif