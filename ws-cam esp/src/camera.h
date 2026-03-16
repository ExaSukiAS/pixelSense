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
            config.ledc_timer   = LEDC_TIMER_0;

            config.pin_d0       = 5;   // Y2
            config.pin_d1       = 18;  // Y3
            config.pin_d2       = 19;  // Y4
            config.pin_d3       = 21;  // Y5
            config.pin_d4       = 36;  // Y6
            config.pin_d5       = 39;  // Y7
            config.pin_d6       = 34;  // Y8
            config.pin_d7       = 35;  // Y9

            config.pin_xclk     = 0;

            config.pin_pclk     = 22;
            config.pin_vsync    = 25;
            config.pin_href     = 23;

            config.pin_sccb_sda = 26;
            config.pin_sccb_scl = 27;

            config.pin_pwdn     = 32;
            config.pin_reset    = -1;

            config.xclk_freq_hz = 20000000; // 20MHz safe XCLK
            config.pixel_format = PIXFORMAT_JPEG;

            config.frame_size = FRAME_SIZE_LOW;
            config.jpeg_quality = 20;
            config.fb_count = 2;
            config.grab_mode = CAMERA_GRAB_LATEST;
            config.fb_location = CAMERA_FB_IN_PSRAM;

            if (esp_camera_init(&config) != ESP_OK) {
                Serial.println("Camera init failed!");
                ESP.restart();
            }

            // set sensor parameters and apply OV2640 register tweak (CLKRC)
            sensor_t *s = esp_camera_sensor_get();
            if (s) {
                s->set_framesize(s, FRAME_SIZE_LOW);
                s->set_quality(s, 20);
            }
        }

        // changes camera resolution
        void setResolution(char res){
            sensor_t *s = esp_camera_sensor_get();
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
                    vTaskDelay(50 / portTICK_PERIOD_MS);
                    continue;
                }

                //  wait until previous frame is sent
                if(frameReady){
                    vTaskDelay(1);
                    continue;
                }

                camera_fb_t *fb = esp_camera_fb_get();
                if(!fb){
                    vTaskDelay(5);
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