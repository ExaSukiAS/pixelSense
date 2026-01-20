#include <WiFi.h>
#include <WebSocketsServer.h>
#include "esp_camera.h"
#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include "fb_gfx.h"
// Optional, to disable brownout detector
#include "soc/soc.h" 
#include "soc/rtc_cntl_reg.h" 

// Wifi credentials
const char* ssid = "Amartya";
const char* password = "amartya@@2020";

// defining camera pins
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM       5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Laser sensor, speaker, touch sensor and onboard LED pins
int laserSensorSDA = 13;
int laserSensorSCL = 14;
int speakerPin = 2;
int onBoardLedPin = 33;
int touch1Pin = 15;
int touch2Pin = 4;

// Camera parameters
#define FRAME_SIZE_LOW  FRAMESIZE_VGA
#define FRAME_SIZE_HIGH FRAMESIZE_SXGA
#define JPEG_QUALITY    20
#define FB_COUNT        2  

// Laser sensor object
#define SEALEVELPRESSURE_HPA (1013.25)
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

// Websocket server (port 9000)
int wsPort = 9000;
WebSocketsServer webSocketServer(wsPort);

bool isStreamingStarted = false; // flag for image streaming state

// speaker variables
bool prevToggle = false;
int prevFreq = 0;

// distance sensor variables
unsigned long lastDistanceReadTime = 0;

camera_config_t config; // global camera configuration
camera_fb_t *latestFb = NULL; // latest frame buffer for streaming
bool frameReady = false; // flag to indicate a new frame is ready
char currentRes = 'l'; // current resolution setting

// Camera init with safe XCLK + params
void setupCamera() {
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk      = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;

  // SAFE XCLK: 20 MHz with CLKRC doubling tweak
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  config.frame_size = FRAME_SIZE_LOW;
  config.jpeg_quality = JPEG_QUALITY;
  config.fb_count = FB_COUNT;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed!");
    ESP.restart();
  }

  // Set sensor parameters and apply OV2640 register tweak (CLKRC)
  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    s->set_framesize(s, FRAME_SIZE_LOW);
    s->set_quality(s, JPEG_QUALITY);
  }
}

// sends a single image via websocket
void sendImage() {
  camera_fb_t *fb = NULL;
  fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    return;
  } else {
    Serial.println("Image captured");
  }
  webSocketServer.broadcastBIN(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// changes resolution
void setResolution(char res){
  sensor_t *s = esp_camera_sensor_get();
  if(res == 'l'){
    s->set_framesize(s, FRAME_SIZE_LOW);
  } else {
    s->set_framesize(s, FRAME_SIZE_HIGH);
  }

  // Discard first few dark frames
  for (int i = 0; i < 3; i++) {
    camera_fb_t *tmp = esp_camera_fb_get();
    if (tmp) esp_camera_fb_return(tmp);
    delay(50);
  }
  currentRes = res;
}

// toggles image streaming state
void toggleStreaming(bool toggle){
  if(toggle){
    isStreamingStarted = true;
    Serial.println("Streaming started");
  } else {
    isStreamingStarted = false;
    Serial.println("Streaming stopped");
  }
}


// handles incoming data through websocket
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_TEXT:
      if (String((char*)payload) == "captureHigh") {
        if(currentRes != 'h'){
          setResolution('h');
        }
        sendImage();
      } else if (String((char*)payload) == "captureLow"){
        if(currentRes != 'l'){
          setResolution('l');
        }
        sendImage();
      } else if (String((char*)payload) == "startStream"){
        if(currentRes != 'l'){
          setResolution('l');
        }
        toggleStreaming(true);
      } else if (String((char*)payload) == "stopStream"){
        toggleStreaming(false);
      }
      break;
    case WStype_DISCONNECTED:
      break;
    default:
      break;
  }
}

// captures frames continuously and saves to latestFb
void frameCaptureTask(void *pv){
  for(;;){
    if(!isStreamingStarted){
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


// plays tone with speaker
void playTone(int freq, bool toggle){
  if((prevToggle == toggle) && (prevFreq == freq)){
    return;
  }
  if(toggle){
    ledcWriteTone(speakerPin, freq);
  } else {
    ledcWrite(speakerPin, 0);
  }
  prevToggle = toggle; 
  prevFreq = freq;
}

// Reads touch sensors with debounce
bool readTouch(int pin) {
    const int numReadings = 5;  
    int totalScore = 0;     
    for (int i = 0; i < numReadings; i++) {
        totalScore += digitalRead(pin);
    }
    float score = 1 - (totalScore / (float)numReadings);  

    return (score > 0.5); // Return true if the score is above threshold (considered pressed)
}

void setup() {
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // Turn-off the brownout detector
    Serial.begin(115200);

    // Attact GPIOs
    ledcSetup(0, 50, 8);
    ledcAttachPin(speakerPin, 0); // speaker pin
    pinMode(onBoardLedPin, OUTPUT);
    pinMode(touch1Pin, INPUT);
    pinMode(touch2Pin, INPUT);
    Wire.begin(laserSensorSDA, laserSensorSCL); // attach laser sensor

    setupCamera(); // initialize camera

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {}  // wait until connected to wifi
    Serial.println("Connected to Wi-Fi");
    Serial.print("ws://");Serial.print(WiFi.localIP());Serial.print(":");Serial.println(wsPort);

    // initialize laser distance sensor
    if(!lox.begin()){
        Serial.println("Failed to boot VL53L0X");
        while(1);
    }

    webSocketServer.begin();
    webSocketServer.onEvent(webSocketEvent);

    // create streaming task pinned to Core 0
    BaseType_t res = xTaskCreatePinnedToCore(frameCaptureTask, "FrameCapture", 8192, NULL, 1, NULL, 0);
    if (res != pdPASS) {
        Serial.println("Failed to create FrameCapture task!");
    }

    digitalWrite(onBoardLedPin, LOW); // turn on onboard LED to indicate ready state (logic is inverted as the onboard LED is active LOW)
}

void loop() {
    // handle websocket events
    webSocketServer.loop();
    if(frameReady){
        webSocketServer.broadcastBIN(latestFb->buf, latestFb->len);
        esp_camera_fb_return(latestFb);
        frameReady = false;
    }

    VL53L0X_RangingMeasurementData_t measure;
    lox.rangingTest(&measure, false);
    if (measure.RangeStatus != 4) { // phase failures have incorrect data
        int distance =  measure.RangeMilliMeter; 
        if(distance < 100){
          playTone(4000, true); 
        } else {
          playTone(4000, false);
        }
    } else {
        playTone(4000, false);
    }

    if(readTouch(touch1Pin) == true){
        webSocketServer.broadcastTXT("$#TXT#$touch1_single");
        playTone(500, true);delay(100);playTone(2000, true);delay(100);playTone(500, false);//play tone
        delay(500); // ensures no accident press happens
    } else if(readTouch(touch2Pin) == true){
        webSocketServer.broadcastTXT("$#TXT#$touch2_single");
        playTone(2000, true);delay(100);playTone(500, true);delay(100);playTone(500, false);//play tone
        delay(500); // ensures no accident press happens
    }
}