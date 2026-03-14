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

        #define I2S_PORT I2S_NUM_0 

        const int samplingRate = 12000; // 12khz audio
        int amplificationNumerator = 1;
        int amplificationDenominator = 1;

        // converts the float amplification coefficient defined by the user into fraction
        // outputs two integers, the numerator and denominator of the fraction
        void floatToFraction(float value, int &numerator, int &denominator, int maxDen = 100) {
            int sign = (value < 0) ? -1 : 1;
            value = abs(value);

            int a = (int)value;
            float frac = value - a;

            if (frac < 1e-6) { 
                numerator = sign * a;
                denominator = 1;
                return;
            }

            int h1 = 1, h2 = 0;
            int k1 = 0, k2 = 1;

            float b = value;

            do {
                int a_i = (int)b;

                int h = a_i * h1 + h2;
                int k = a_i * k1 + k2;

                if (k > maxDen) break;

                h2 = h1;
                h1 = h;
                k2 = k1;
                k1 = k;

                float remainder = b - a_i;
                if (remainder < 1e-6) break;

                b = 1.0 / remainder;

            } while (true);

            numerator = sign * h1;
            denominator = k1;
        }
    public:
        // buffer settings
        #define JITTER_BUFFER_SIZE 30000 
        int16_t jitterBuffer[JITTER_BUFFER_SIZE]; // circular buffer to store audio samples
        volatile int head = 0; // index pointer for storing sample to jitterBuffer
        volatile int tail = 0; // index pointer for playing sample from jitterBuffer
        volatile bool isBuffering = true; // flag to determine whether to play audio or store samples in jitterBuffer
        const int prefillThresh = 2400; // ~200ms of audio (audio starts playing when jitterBuffer has atleast prefillThresh amount of samples)

        Speaker(int BCLKpin, int LRCpin, int DINpin, float amplification){
            channelPin = LRCpin;
            clockPin = BCLKpin;
            dataPin = DINpin;

            floatToFraction(amplification, amplificationNumerator, amplificationDenominator);
        }

        // attaches speaker
        void attachSpeaker() {
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
        } 

        // detaches speaker so that the clock and channel select pin can be used by an another I2S device
        void detachSpeaker(){
            i2s_stop(I2S_PORT);
            i2s_driver_uninstall(I2S_PORT);
        }

        // used so that we can run audioPlayingTask() as a saperate task
        static void audioTaskWrapper(void *param) {
            Speaker* self = (Speaker*)param;
            self->audioPlayingTask();
        }

        // plays audio samples from the jitter buffer
        void audioPlayingTask(){
            for (;;) {
                int available = (head - tail + JITTER_BUFFER_SIZE) % JITTER_BUFFER_SIZE; // number of available samples

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
                    int32_t amplified = (jitterBuffer[tail] * amplificationNumerator) / amplificationDenominator; // amplification (using integers instead of float to enhance processing speed)
                    
                    // clamping
                    if(amplified > 32767) amplified = 32767;
                    if(amplified < -32768) amplified = -32768;
                    
                    pcmOut[i] = (int16_t)amplified;
                    tail = (tail + 1) % JITTER_BUFFER_SIZE;
                }

                // play the audio samples
                size_t bytes_written;
                i2s_write(I2S_PORT, pcmOut, toPlay * sizeof(int16_t), &bytes_written, portMAX_DELAY);
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

class Buzzer{
    private:
        bool prevToggle = false;
        int prevFreq = 0;
        int pin;
    public:
        enum ToneType {
            TOUCH1_SINGLE,
            TOUCH1_DOUBLE,
            TOUCH1_HOLD,
            TOUCH2_SINGLE,
            TOUCH2_DOUBLE,
            TOUCH2_HOLD,
            ERROR
        };

        // constructor
        Buzzer(int buzzerPin){
            pin = buzzerPin;
            ledcSetup(0, 50, 8);
            ledcAttachPin(pin, 0);
        }

        // plays tone with buzzer
        void playFreq(int freq, bool toggle){
            if((prevToggle == toggle) && (prevFreq == freq)){
                return;
            }
            if(toggle){
                ledcWriteTone(0, freq);
            } else {
                ledcWrite(0, 0);
            }
            prevToggle = toggle; 
            prevFreq = freq;
        }

        void playTone(ToneType tone){
            switch(tone){
                case TOUCH1_SINGLE:
                    playFreq(500, true); delay(100);
                    playFreq(2000, true); delay(100);
                    playFreq(500, false);
                    break;

                case TOUCH1_DOUBLE:
                    playFreq(1000, true); delay(100);
                    playFreq(3000, true); delay(100);
                    playFreq(1000, false);
                    break;

                case TOUCH1_HOLD:
                    playFreq(1500, true); delay(300);
                    playFreq(1500, false);
                    break;

                case TOUCH2_SINGLE:
                    playFreq(2000, true); delay(100);
                    playFreq(500, true); delay(100);
                    playFreq(500, false);
                    break;

                case TOUCH2_DOUBLE:
                    playFreq(3000, true); delay(100);
                    playFreq(1000, true); delay(100);
                    playFreq(1000, false);
                    break;

                case TOUCH2_HOLD:
                    playFreq(2500, true); delay(300);
                    playFreq(2500, false);
                    break;
                
                case ERROR:
                    playFreq(2000, true); delay(600);
                    playFreq(2000, false); delay(600);
                    playFreq(2000, true); delay(600);
                    playFreq(2000, false); 
                    break;
            }
        }
};

#endif