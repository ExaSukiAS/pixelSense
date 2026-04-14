#ifndef MIC_H
#define MIC_H

#include <Arduino.h>
#include <driver/i2s.h>

class Microphone{
    private:
        // I2S pins
        int wsPin;
        int dataPin;

        #define I2S_PORT I2S_NUM_0 

        const uint32_t samplingRate = 8000;
        float gain = 1;
    public:
        static const uint16_t micBufferSize = 128;
        int16_t micSamples[micBufferSize]; // stores the audio samples to send via UDP

        bool audioStreamingStarted = false; // flag for audio streaming state
        bool audioSamplesReady = false; //  flag to determine whether audio samples are reday to send

        bool attachState = false; // flag to indicate if mic is attached or not

        // constructor
        Microphone(int WSpin, int SDpin, float amplificationGain){
            wsPin = WSpin;
            dataPin = SDpin;

            gain = amplificationGain;
        }
        
        // attaches mic
        void attach(){
            if (attachState) return;

            const i2s_config_t i2s_config = {
                .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM),
                .sample_rate = samplingRate,
                .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
                .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
                .communication_format = I2S_COMM_FORMAT_STAND_I2S,
                .intr_alloc_flags = 0,
                .dma_buf_count = 8,
                .dma_buf_len = 128,
                .use_apll = false
            };
            const i2s_pin_config_t pin_config = {
                .bck_io_num = -1,
                .ws_io_num = wsPin,
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

#endif