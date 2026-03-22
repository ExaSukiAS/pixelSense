#include <WiFi.h>
#include <WebSocketsServer.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_VL53L0X.h>

// custom
#include "speaker.h"
#include "mic.h"
#include "touchSensor.h"
#include "camera.h"
#include "resourceMonitor.h"

// to disable brownout detector
#include "soc/soc.h" 
#include "soc/rtc_cntl_reg.h" 

// WiFi credentials
const char* ssid = "Amartya";
const char* password = "amartya@@2020";

// laser sensor, speaker, touch sensor, microphone and onboard LED pins
const int laserSensorSDA = 13;
const int laserSensorSCL = 14;
const int onBoardLedPin = 33;
const int touch1Pin = 15;
const int touch2Pin = 4;
const int i2sChannelSelectPin = 12; 
const int i2sClockPin = 2;         
const int i2sSpeakerDataPin = 3; 
const int i2sMicDataPin = 4;  

Camera camera; // OV2640 camera object

// laser sensor object
#define SEALEVELPRESSURE_HPA (1013.25)
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

// touch sensor objects
TouchSensor touch1(touch1Pin);
TouchSensor touch2(touch2Pin);

// mic and speaker objects
Speaker speaker(i2sClockPin, i2sChannelSelectPin, i2sSpeakerDataPin, 1.5);
Microphone mic(i2sClockPin, i2sChannelSelectPin, i2sMicDataPin, 5.0);

// laser distance sensor variables
unsigned long lastRequestTime = 0;
const unsigned long sampleInterval = 50; 
bool waitingForReading = false; // flag to indicate if we're waiting for a sensor reading to be sent before taking another reading
const int alertDistance = 100; // distance threshold in mm for alert
bool distanceSensorBooted = false;
bool wasAlerting = false; // tracks if the buzzer was active
uint16_t dist_mm = 0; // current distance reading from TOF sensor

// Websocket server (port 9000)
const int espWSport = 9000;
WebSocketsServer webSocketServer(espWSport);

// UDP server
const int espUDPport = 9001; // UDP port of esp32
IPAddress computerIP;
const uint16_t computerImgPort = 5005; // port of the server(computer) at which images will be streamed
const uint16_t computerMicPort = 5006; // port of the server(computer) at which audio samples from microphone will be streamed
const uint16_t computerMsgPort = 5007; // port the teh server(computer) at which general messages (distance from TOF sensor and esp32 resource usage)
bool computerDiscovered = false;
const uint32_t imageStreamPktSize = 1400;
WiFiUDP udpServer;

ResourceMonitor resMon;
int generalMsg[6];
const unsigned long udpMsgSendingInterval = 500; 
unsigned long lastUDPmsgTime = 0;

// toggles image streaming state
void toggleImageStreaming(bool toggle){
  if(toggle){
    camera.imageStreamingStarted = true;
  } else {
    camera.imageStreamingStarted = false;
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
    case WStype_CONNECTED:
      // get the IP address of the connected client (the computer)
      computerIP = webSocketServer.remoteIP(num);
      computerDiscovered = true;
      break;
    case WStype_TEXT:
      if (String((char*)payload) == "captureHigh") {
        if(camera.currentRes != 'h'){
          camera.setResolution('h');
        }
        camera.captureStaticImg();
        webSocketServer.broadcastBIN(camera.latestFb->buf, camera.latestFb->len);
        camera.clearFrameBuffer();
      } else if (String((char*)payload) == "captureLow"){
        if(camera.currentRes != 'l'){
          camera.setResolution('l');
        }
        camera.captureStaticImg();
        webSocketServer.broadcastBIN(camera.latestFb->buf, camera.latestFb->len);
        camera.clearFrameBuffer();
      } else if (String((char*)payload) == "startImageStream"){
        if(camera.currentRes != 'l'){
          camera.setResolution('l');
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
      speaker.lastSampleTime = millis();   // update last audio arrival time
    }
  }
}

// sends image stream via UDP
void sendFrameUDP(camera_fb_t *fb){
    static uint16_t frameID = 0;
    frameID++;

    for(uint32_t offset = 0; offset < fb->len; offset += imageStreamPktSize){
        uint16_t chunk = imageStreamPktSize;
        if(offset + chunk > fb->len){
            chunk = fb->len - offset;
        }

        udpServer.beginPacket(computerIP, computerImgPort);
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
        udpServer.beginPacket(computerIP, computerMicPort);
        udpServer.write((uint8_t*)samples, mic.micBufferSize * 2); 
        udpServer.endPacket();
    }
}

// sends general system stats and TOF distance via UDP
void sendGeneralMsgUDP(){
  resMon.getInfo(generalMsg); // fills index 0-4
  generalMsg[5] = dist_mm; // fills index 5 (Distance)

  udpServer.beginPacket(computerIP, computerMsgPort);
  udpServer.write((uint8_t*)generalMsg, sizeof(generalMsg)); 
  udpServer.endPacket();
}

void setup() {
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // Turn-off the brownout detector

    Serial.begin(115200);

    camera.attach();
    
    speaker.attach();

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {}  // wait until connected to wifi
    Serial.println("Connected to Wi-Fi");

    udpServer.begin(espUDPport);

    Serial.println("ESP32 available at: ");
    Serial.print("\t");Serial.print(WiFi.localIP());Serial.print(":");Serial.print(espWSport);Serial.println("   <- Websocket");
    Serial.print("\t");Serial.print(WiFi.localIP());Serial.print(":");Serial.print(espUDPport);Serial.println("   <- UDP");

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

    BaseType_t imageTask = xTaskCreatePinnedToCore(camera.frameCaptureTaskWrapper, "FrameCapture", 4096, &camera, 1, NULL, 0); // pin image streaming task to Core 0
    BaseType_t audioPlaybackTask = xTaskCreatePinnedToCore(speaker.speakerTaskWrapper, "AudioPlayback", 4096, &speaker, 1, NULL, 1); // pin audio playback task to Core 1
    BaseType_t audioCaptureTask = xTaskCreatePinnedToCore(mic.micTaskWrapper, "AudioCapture", 4096, &mic, 1, NULL, 1); // pin audio playback task to Core 1

    digitalWrite(onBoardLedPin, LOW); // turn on onboard LED to indicate ready state (logic is inverted as the onboard LED is active LOW)
    camera.setResolution('h'); // start with high resolution
}

void loop() {
    webSocketServer.loop();
    unsigned long now = millis();

    // request distance reading at regular intervals
    if (!waitingForReading && now - lastRequestTime >= sampleInterval && distanceSensorBooted) {
      if (lox.startRange()) {
        lastRequestTime = now;
        waitingForReading = true;
      }
    }

    if(now - lastUDPmsgTime >= udpMsgSendingInterval){
      sendGeneralMsgUDP();
      lastUDPmsgTime = now;
    }

    // handle image streaming
    if(camera.frameReady){
      sendFrameUDP(camera.latestFb);
      camera.clearFrameBuffer();
      camera.frameReady = false;
    }

    // handle incoming UDP data
    int udpPacketSize = udpServer.parsePacket();
    if (udpPacketSize) {
      if(computerDiscovered && udpPacketSize > 4){
        processUDPAudioData();
      }
    }

    // send audio samples from mic if they are ready
    if(mic.audioSamplesReady){
      sendAudioUDP(mic.micSamples);
      mic.audioSamplesReady = false;
    }

    // check if laser sensor range is ready (non-blocking check)
    if (waitingForReading && lox.isRangeComplete() && distanceSensorBooted) {
      dist_mm = lox.readRangeResult(); // last completed measurement
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