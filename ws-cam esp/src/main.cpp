#include <WiFi.h>
#include <WebSocketsServer.h>
#include <WiFiUdp.h>
#include "esp_camera.h"
#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include "peripherals.h"

// to disable brownout detector
#include "soc/soc.h" 
#include "soc/rtc_cntl_reg.h" 

// Wifi credentials
const char* ssid = "Amartya";
const char* password = "amartya@@2020";

// camera pins
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

// Laser sensor, speaker, touch sensor, microphone and onboard LED pins
const int laserSensorSDA = 13;
const int laserSensorSCL = 14;
const int onBoardLedPin = 33;
const int touch1Pin = 15;
const int touch2Pin = 4;
const int i2sChannelSelectPin = 12; 
const int i2sClockPin = 2;         
const int i2sSpeakerDataPin = 3; 
const int i2sMicDataPin = 4;  

// Camera parameters
#define FRAME_SIZE_LOW  FRAMESIZE_VGA
#define FRAME_SIZE_HIGH FRAMESIZE_SXGA
#define JPEG_QUALITY    20
#define FB_COUNT        2  

// Laser sensor object
#define SEALEVELPRESSURE_HPA (1013.25)
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

// laser distance sensor variables
unsigned long lastRequestTime = 0;
const unsigned long sampleInterval = 50; 
bool waitingForReading = false; // flag to indicate if we're waiting for a sensor reading to be sent before taking another reading
const int alertDistance = 100; // distance threshold in mm for alert
bool distanceSensorBooted = false;
bool wasAlerting = false; // tracks if the buzzer was active

// Websocket server (port 9000)
const int wsPort = 9000;
WebSocketsServer webSocketServer(wsPort);

// UDP server
const int udpPort = 9001; // UDP port of esp32
IPAddress computerIP;
const uint16_t imageStreamingPort = 5005; // port of the server(computer) at which images will be streamed and handshake will be executed
const uint16_t micAudioStreamingPort = 5006; // port of the server(computer) at which audio samples from microphone will be streamed
bool computerDiscovered = false;
const uint32_t udpStreamPacketSize = 1400;
WiFiUDP udpServer;

bool imageStreamingStarted = false; // flag for image streaming state
bool audioStreamingStarted = false; // flag for audio streaming state

const int initialFrameDropCount = 3; // number of initial frames to drop after resolution change to allow camera to stabilize
camera_config_t config; // global camera configuration
camera_fb_t *latestFb = NULL; // latest frame buffer for streaming
bool frameReady = false; // flag to indicate a new frame is ready
char currentRes = 'l'; // current resolution setting

// touch sensor objects
TouchSensor touch1(touch1Pin);
TouchSensor touch2(touch2Pin);

// mic and speaker objects
Speaker speaker(i2sClockPin, i2sChannelSelectPin, i2sSpeakerDataPin, 1.5);
Microphone mic(i2sClockPin, i2sChannelSelectPin, i2sMicDataPin, 5.0);

// camera init with safe XCLK + params
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

// sends a static-single image via websocket
void sendImage() {
  camera_fb_t *fb = NULL;
  fb = esp_camera_fb_get();

  if (!fb) { // camera capture failure
    return;
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
  for (int i = 0; i < initialFrameDropCount; i++) {
    camera_fb_t *tmp = esp_camera_fb_get();
    if (tmp) esp_camera_fb_return(tmp);
    delay(50);
  }
  currentRes = res;
}

// toggles image streaming state
void toggleImageStreaming(bool toggle){
  if(toggle){
    imageStreamingStarted = true;
  } else {
    imageStreamingStarted = false;
  }
}

// toggles audio streaming state
void toggleMicAudioStreaming(bool toggle){
  if(toggle){
    speaker.lockI2Sport = true;  // stop the speaker task from trying to attach
    speaker.detach();
    
    mic.attach(); 
    mic.audioStreamingStarted = true;
  } else {
    mic.audioStreamingStarted = false; 
    mic.detach();           
    
    speaker.attach();
    speaker.lockI2Sport = false; // allow the speaker to automatically re-attach when needed
  }
}

// handles incoming data through websocket
// commands: captureHigh, captureLow, startImageStream, stopImageStream, startAudioStream, stopAudioStream
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
      } else if (String((char*)payload) == "startImageStream"){
        if(currentRes != 'l'){
          setResolution('l');
        }
        toggleImageStreaming(true);
      } else if (String((char*)payload) == "stopImageStream"){
        toggleImageStreaming(false);
      } else if (String((char*)payload) == "startAudioStream"){
        toggleMicAudioStreaming(true);
      } else if (String((char*)payload) == "stopAudioStream"){
        toggleMicAudioStreaming(false);
      }
      break;
    case WStype_DISCONNECTED:
      break;
    default:
      break;
  }
}

// handle handshake with computer via UDP
void handleUDPhandshake(){
    // fetch the computer's IP 
    computerIP = udpServer.remoteIP();

    // consume the handshake payload to clear the buffer completely
    while (udpServer.available()) {
        udpServer.read();
    }

    // send a response back to the detected IP
    udpServer.beginPacket(computerIP, imageStreamingPort);
    udpServer.print("receivedPacket");
    udpServer.endPacket();
    computerDiscovered = true;
}

// stores audio samples got from server(computer) via UDP in the speaker.jitterBuffer
void processUDPAudioData() {
  uint8_t pkt[1024]; // received packet
  int len = udpServer.read(pkt, sizeof(pkt));
  
  // take only the samples by removing the 4-byte header(packet id)
  for (int i = 4; i < len - 1; i += 2) {
    int16_t sample = (pkt[i + 1] << 8) | pkt[i]; // each byte(8bit) of the pkt is only half of a full 16bit sample, so we glue the high and low bytes
    int nextHead = (speaker.head + 1) % speaker.jitterBufferSize;
    if (nextHead != speaker.tail) { 
      speaker.jitterBuffer[speaker.head] = sample;
      speaker.head = nextHead;
    }
  }
}

// sends image stream via UDP
void sendFrameUDP(camera_fb_t *fb){
    static uint16_t frameID = 0;
    frameID++;

    for(uint32_t offset = 0; offset < fb->len; offset += udpStreamPacketSize){
        uint16_t chunk = udpStreamPacketSize;
        if(offset + chunk > fb->len){
            chunk = fb->len - offset;
        }

        udpServer.beginPacket(computerIP, imageStreamingPort);
        udpServer.write((uint8_t*)&frameID, 2);
        udpServer.write((uint8_t*)&offset, 4);
        udpServer.write(fb->buf + offset, chunk);
        udpServer.endPacket();
    }
    delayMicroseconds(200);
}

// sends audio stream from mic via UDP
void sendAudioUDP(int16_t* samples){
    if (computerIP) { 
        udpServer.beginPacket(computerIP, micAudioStreamingPort);
        udpServer.write((uint8_t*)samples, mic.micBufferSize * 2); 
        udpServer.endPacket();
    }
}

// captures frames continuously and saves to latestFb
void frameCaptureTask(void *pv){
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

void setup() {
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // Turn-off the brownout detector

    Serial.begin(115200);

    setupCamera(); // initialize camera
    speaker.attach();

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {}  // wait until connected to wifi
    Serial.println("Connected to Wi-Fi");

    udpServer.begin(udpPort);

    Serial.println("ESP32 available at: ");
    Serial.print("\t");Serial.print(WiFi.localIP());Serial.print(":");Serial.print(wsPort);Serial.println("   <- Websocket");
    Serial.print("\t");Serial.print(WiFi.localIP());Serial.print(":");Serial.print(udpPort);Serial.println("   <- UDP");

    // Attact GPIOs
    pinMode(onBoardLedPin, OUTPUT);
    Wire.begin(laserSensorSDA, laserSensorSCL); // attach laser sensor

    // initialize laser distance sensor
    if(lox.begin()){
      distanceSensorBooted = true;
    } else {
      speaker.playTone(Speaker::ERROR); // play error tone to indicate sensor failure
    }

    webSocketServer.begin();
    webSocketServer.onEvent(webSocketEvent);

    BaseType_t imageTask = xTaskCreatePinnedToCore(frameCaptureTask, "FrameCapture", 4096, NULL, 1, NULL, 0); // pin streaming task to Core 0
    BaseType_t audioPlaybackTask = xTaskCreatePinnedToCore(speaker.speakerTaskWrapper, "AudioPlayback", 4096, &speaker, 1, NULL, 1); // pin audio playback task to Core 1
    BaseType_t audioCaptureTask = xTaskCreatePinnedToCore(mic.micTaskWrapper, "AudioCapture", 4096, &mic, 1, NULL, 1); // pin audio playback task to Core 1

    digitalWrite(onBoardLedPin, LOW); // turn on onboard LED to indicate ready state (logic is inverted as the onboard LED is active LOW)
    setResolution('h'); // start with high resolution
}

void loop() {
    // request distance reading at regular intervals
    unsigned long now = millis();
    if(now > 8000 && now < 8050){
      toggleMicAudioStreaming(true);
      Serial.println("audio stream started");
    }
    if (!waitingForReading && now - lastRequestTime >= sampleInterval && distanceSensorBooted) {
      if (lox.startRange()) { // non-blocking start
        lastRequestTime = now;
        waitingForReading = true;
      }
    }

    // handle websocket events
    webSocketServer.loop();
    if(frameReady){
      sendFrameUDP(latestFb);
      esp_camera_fb_return(latestFb);
      frameReady = false;
    }

    // handle incoming UDP data
    int udpPacketSize = udpServer.parsePacket();
    if (udpPacketSize) {
      if(!computerDiscovered){
        handleUDPhandshake();
      } else {
        if(udpPacketSize > 4){
          processUDPAudioData();
        }
      }
    }

    // send audio samples from mic if they are ready
    if(mic.audioSamplesReady){
      sendAudioUDP(mic.micSamples);
      mic.audioSamplesReady = false;
    }

    // check if laser sensor range is ready (non-blocking check)
    if (waitingForReading && lox.isRangeComplete() && distanceSensorBooted) {
      uint16_t dist_mm = lox.readRangeResult(); // last completed measurement
      waitingForReading = false;

      if (dist_mm > 0 && dist_mm < alertDistance) {
        wasAlerting = true; // mark that we are currently alerting
        int freq;
        switch(dist_mm) {
          case 0 ... 40:
            freq = 4000;
            break;
          case 41 ... 60:
            freq = 2000;
            break;
          case 61 ... 80:
            freq = 1000;
            break;
          default:
            freq = 500;
        }
        speaker.playFreq(freq, true);
      } else {
        // only clear the buffer if we were previously alerting
        if (wasAlerting) {
            speaker.playFreq(4000, false);
            wasAlerting = false; // reset the state
        }
      }
    }

    // read touch sensors and emit events
    int touch1State = touch1.getTouchState();
    int touch2State = touch2.getTouchState();

    // temporarily disabling touch sensors for testing
    touch1State = 0;
    touch2State = 0;

    switch(touch1State){
      case 1: // single tap
        webSocketServer.broadcastTXT("$#TXT#$touch1_single");
        speaker.playTone(Speaker::TOUCH1_SINGLE);
        delay(500); // debounce delay
        break;
      case 2: // double tap
        webSocketServer.broadcastTXT("$#TXT#$touch1_double");
        speaker.playTone(Speaker::TOUCH1_DOUBLE);
        delay(500); // debounce delay
        break;
      case 3: // hold
        webSocketServer.broadcastTXT("$#TXT#$touch1_hold");
        speaker.playTone(Speaker::TOUCH1_HOLD);
        delay(500); // debounce delay
        break;
    }

    switch(touch2State){
      case 1: // single tap
        webSocketServer.broadcastTXT("$#TXT#$touch2_single");
        speaker.playTone(Speaker::TOUCH2_SINGLE);
        delay(500); // debounce delay
        break;
      case 2: // double tap
        webSocketServer.broadcastTXT("$#TXT#$touch2_double");
        speaker.playTone(Speaker::TOUCH2_DOUBLE);
        delay(500); // debounce delay
        break;
      case 3: // hold
        webSocketServer.broadcastTXT("$#TXT#$touch2_hold");
        speaker.playTone(Speaker::TOUCH2_HOLD);
        delay(500); // debounce delay
        break;
    }

    vTaskDelay(1 / portTICK_PERIOD_MS); // gives esp32 some breathing space
}