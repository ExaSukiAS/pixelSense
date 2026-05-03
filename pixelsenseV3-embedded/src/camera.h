#ifndef CAMERA_H
#define CAMERA_H

#include "esp_camera.h"
#include <Arduino.h>

class Camera{
    private:
        // camera resolution macros
        #define FRAME_SIZE_LOW  FRAMESIZE_VGA
        #define FRAME_SIZE_HIGH FRAMESIZE_SXGA
    public:
        const int initialFrameDropCount = 3; // number of initial frames to drop after resolution change to allow camera to stabilize
        camera_config_t config; // global camera configuration
        camera_fb_t* latestFb = NULL; // latest frame buffer for streaming
        volatile bool frameReady = false; // flag to indicate a new frame is ready
        char currentRes = 'l'; // current resolution setting

        bool imageStreamingStarted = false; // flag for image streaming state

        Camera(){} // void constructor 

        // camera init with safe XCLK + params
        void attach(){
            config.ledc_channel = LEDC_CHANNEL_0;
            config.ledc_timer = LEDC_TIMER_0;

            config.pin_d0 = 15;   // Y2_GPIO_NUM
            config.pin_d1 = 17;   // Y3_GPIO_NUM
            config.pin_d2 = 18;   // Y4_GPIO_NUM
            config.pin_d3 = 16;   // Y5_GPIO_NUM
            config.pin_d4 = 14;   // Y6_GPIO_NUM
            config.pin_d5 = 12;   // Y7_GPIO_NUM
            config.pin_d6 = 11;   // Y8_GPIO_NUM
            config.pin_d7 = 48;   // Y9_GPIO_NUM

            config.pin_xclk = 10; 
            config.pin_pclk = 13;
            config.pin_vsync = 38;
            config.pin_href = 47;

            config.pin_sccb_sda = 40;
            config.pin_sccb_scl = 39;

            config.pin_pwdn = -1;
            config.pin_reset = -1;

            config.xclk_freq_hz = 20000000; // 20MHz safe XCLK
            config.pixel_format = PIXFORMAT_JPEG;

            config.frame_size = FRAME_SIZE_LOW;
            config.jpeg_quality = 10;
            config.fb_count = 2;
            config.grab_mode = CAMERA_GRAB_LATEST;
            config.fb_location = CAMERA_FB_IN_PSRAM;

            if (esp_camera_init(&config) != ESP_OK) {
                Serial.println("Camera init failed!");
                ESP.restart();
            }

            // set sensor parameters and apply OV3660 register tweak (CLKRC)
            sensor_t *s = esp_camera_sensor_get();
            if (s) {
                s->set_framesize(s, FRAME_SIZE_LOW);
                s->set_quality(s, 10); // (0-63, lower means higher quality)
            }
        }

        // changes camera resolution
        void setResolution(char res){
            sensor_t *s = esp_camera_sensor_get();
            
            if(!s) return;

            if(res == 'l'){
                s->set_framesize(s, FRAME_SIZE_LOW);
            } else {
                s->set_framesize(s, FRAME_SIZE_HIGH);
            }

            // Discard first few dark frames
            for (int i = 0; i < initialFrameDropCount; i++) {
                camera_fb_t *tmp = esp_camera_fb_get();
                if (tmp) esp_camera_fb_return(tmp);
                delay(100);
            }
            currentRes = res;
        }

        // used so that we can run frameCaptureTask() as a saperate task
        static void frameCaptureTaskWrapper(void *param) {
            Camera* self = (Camera*)param;
            self->frameCaptureTask();
        }

        // captures frames continuously and saves to latestFb
        void frameCaptureTask(){
            for(;;){
                if(!imageStreamingStarted){
                    vTaskDelay(pdMS_TO_TICKS(5));
                    continue;
                }

                //  wait until previous frame is sent
                if(frameReady){
                    vTaskDelay(pdMS_TO_TICKS(5));
                    continue;
                }

                camera_fb_t *fb = esp_camera_fb_get();
                if(!fb){
                    vTaskDelay(pdMS_TO_TICKS(5));
                    continue;
                }
                latestFb = fb;
                frameReady = true;
            }
        }

        // captures a static image and puts it in latestFb
        bool captureStaticImg() {
            camera_fb_t *fb = esp_camera_fb_get();
            if(!fb){
                return false;
            }
            latestFb = fb;
            return true;
        }

        // clears frame buffer (latestFb)
        void clearFrameBuffer(){
            esp_camera_fb_return(latestFb);
            return;
        }
};

#endif