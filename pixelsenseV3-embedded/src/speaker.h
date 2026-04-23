#ifndef SPEAKER_H
#define SPEAKER_H

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

        uint32_t lastSampleTime = 0;
        const uint32_t streamTimeout = 300;

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
                    vTaskDelay(pdMS_TO_TICKS(10));
                    continue;
                }

                if ((millis() - lastSampleTime) > streamTimeout) {
                    // no audio stream for 300ms
                    i2s_zero_dma_buffer(I2S_PORT);

                    isBuffering = true;
                    head = tail;   // clear software buffer

                    vTaskDelay(pdMS_TO_TICKS(10));
                    continue;
                }

                int available = (head - tail + jitterBufferSize) % jitterBufferSize; // number of available samples

                // determine whether to play the audio or wait for enough samples
                if (isBuffering) {
                    if (available >= prefillThresh) {
                        isBuffering = false;
                    } else {
                        vTaskDelay(pdMS_TO_TICKS(10));
                        continue; 
                    }
                }
                if (available < 256) {
                    if (available == 0) isBuffering = true; 
                    vTaskDelay(pdMS_TO_TICKS(2));
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

                lastSampleTime = millis();   // update last audio arrival time
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

#endif