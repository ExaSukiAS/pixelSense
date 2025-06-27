#include <WiFi.h>
#include <WebSocketsServer.h>
#include "esp_camera.h"
#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include "fb_gfx.h"

// For brownout detector problems
#include "soc/soc.h" 
#include "soc/rtc_cntl_reg.h" 

// Wifi credentials
const char* ssid = "Amartya";
const char* password = "amartya@@2020";

camera_config_t config; // stores camera configuration

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

int wsPort = 9000;

WebSocketsServer webSocketServer(wsPort);   // sebsocket server at port 9000

bool isStreamingStarted = false;

#define SEALEVELPRESSURE_HPA (1013.25)
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

int laserSensorSDA = 13;
int laserSensorSCL = 14;
int speakerPin = 2;
int onBoardLedPin = 33;

int touch1Pin = 15;
int touch2Pin = 4;

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // Turn-off the brownout detector
  Wire.begin(laserSensorSDA, laserSensorSCL); // attach laser sensor
  Serial.begin(115200);

  // Attact GPIOs
  ledcAttach(speakerPin, 50, 8);
  pinMode(onBoardLedPin, OUTPUT);
  pinMode(touch1Pin, INPUT);
  pinMode(touch2Pin, INPUT);
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  // additional camera configuration
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_UXGA; 
  config.jpeg_quality = 20;
  config.fb_count = 2;
  config.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x, Restarting...", err);
    ESP.restart();
  }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {}  // wait until connected to wifi
  Serial.println("Connected to Wi-Fi");
  Serial.print("ws://");Serial.print(WiFi.localIP());Serial.print(":");Serial.println(wsPort);

  // act if there's some problem with laser sensor
  if (!lox.begin()) {
    while(1){
      playTone(5000, true);
      delay(400);
      playTone(5000, false);
      delay(400);
    }
  }

  webSocketServer.begin();
  webSocketServer.onEvent(webSocketEvent);

  digitalWrite(onBoardLedPin, LOW);
}

void loop() {
  VL53L0X_RangingMeasurementData_t measure;
  lox.rangingTest(&measure, false);

  if (measure.RangeStatus != 4) { // phase failures have incorrect data
    int distance =  measure.RangeMilliMeter; 

    if(distance < 80){
      playTone(4000, true);
    } else {
      playTone(4000, false);
    }
  } else {
    playTone(4000, false);
  }

  webSocketServer.loop();
}

// handles incoming data through websocket
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_TEXT:
      if (String((char*)payload) == "captureHigh") {
        config.frame_size = FRAMESIZE_UXGA;
        delay(20);
        sendImage();
      } else if (String((char*)payload) == "captureLow"){
        config.frame_size = FRAMESIZE_VGA;
        delay(20);
        sendImage();
      } else if (String((char*)payload) == "startStream"){
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

// sends the image via websocket
void sendImage() {
  camera_fb_t * fb = NULL;
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

// toggles streaming state
void toggleStreaming(bool toggle){
  if(toggle){
    isStreamingStarted = true;
    Serial.println("Streaming started");
    streamImage();
  } else {
    isStreamingStarted = false;
    Serial.println("Streaming stopped");
  }
}

// streams images
void streamImage(){
  config.frame_size = FRAMESIZE_VGA;  // set to VGA for higher framerate
  webSocketServer.broadcastTXT("$#TXT#$streamingStarted");
  delay(20);
  camera_fb_t * fb = NULL;
  while(isStreamingStarted){
    if(readTouchDebounced(touch2Pin) == true){
      toggleStreaming(false);
      webSocketServer.broadcastTXT("$#TXT#$streamingStopped");
      playTone(1000, true);
      delay(200);
      playTone(1000, false);
      return;
    }
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      fb = NULL;
    } else {
      webSocketServer.broadcastBIN(fb->buf, fb->len);
      esp_camera_fb_return(fb);
      fb = NULL;
    }
  }
  return;
}

bool prevToggle = false;
int prevFreq = 0;
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

// Reads touch pin with debounce
bool readTouchDebounced(int pin) {
  const int numReadings = 5;  
  int totalScore = 0;     
  for (int i = 0; i < numReadings; i++) {
    totalScore += digitalRead(pin);
    delay(1);  
  }
  float score = 1 - (totalScore / (float)numReadings);  
  
  return (score > 0.5); // Return true if the score is above threshold (considered pressed)
}