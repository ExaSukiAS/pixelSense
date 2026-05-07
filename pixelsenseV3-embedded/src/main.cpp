#include <WiFi.h>
#include <WebSocketsServer.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include <HardwareSerial.h>

/* 
two esp32 s3 boards will share the same core logics of code
but pin layout and some parameters will be different based on the board
'L' for left board and 'R' for right board (as per the orientation in the PCB design files)
'L' board acts as the Master and 'R' board acts as the Slave during Synced Dual Image Streaming
change the value of BOARD_TYPE to switch between the two boards before uploading the code
*/
#define BOARD_TYPE 'L'

// custom
#include "speaker.h"
#include "mic.h"
#include "touchSensor.h"
#include "camera.h"
#include "deviceMonitor.h"
#if BOARD_TYPE == 'L'
  #include "interEspCommMaster.h"
  EspMaster EspSerial;
#else
  #include "interEspCommSalve.h"
  EspSlave EspSerial;
#endif

// WiFi credentials
const char* ssid = "EXA_desktop";
const char* password = "amartya@@2020";

// static pins (same on left and right boards)
#define ONBOARD_LED_PIN      21
#define MIC_WS_PIN           42    
#define MIC_DATA_PIN         41 

// conditional pins (board dependent)
#if BOARD_TYPE == 'L'
    #define SPEAKER_WS_PIN   2
    #define SPEAKER_CLK_PIN  1
    #define SPEAKER_DATA_PIN 9
    #define LASER_SDA_PIN    43
    #define LASER_SCL_PIN    6
    #define TOUCH_PIN        44
    #define BATTERY_PIN      3
    #define INTERCOMM_TX     4
    #define INTERCOMM_RX     5
#else
    #define SPEAKER_WS_PIN   43
    #define SPEAKER_CLK_PIN  6
    #define SPEAKER_DATA_PIN 5
    #define LASER_SDA_PIN    7
    #define LASER_SCL_PIN    44
    #define TOUCH_PIN        9
    #define BATTERY_PIN      8
    #define INTERCOMM_TX     4
    #define INTERCOMM_RX     3
#endif

Camera camera; // OV3660 camera object
uint16_t imgFrameID = 0; // holds the imgFrame id for a streaming session
bool dualImgStreamStarted = false;
volatile bool rightEspCaptureDone = false;

// laser sensor object
#define SEALEVELPRESSURE_HPA (1013.25)
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

// touch sensor objects
TouchSensor touch(TOUCH_PIN);

// mic and speaker objects
Speaker speaker(SPEAKER_CLK_PIN, SPEAKER_WS_PIN, SPEAKER_DATA_PIN, 2.0);
Microphone mic(MIC_WS_PIN, MIC_DATA_PIN, 5.0);

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
const uint16_t computerImgPort = BOARD_TYPE == 'L' ? 5005 : 5008; // port of the server(computer) at which images will be streamed
const uint16_t computerMicPort = BOARD_TYPE == 'L' ? 5006 : 5009; // port of the server(computer) at which audio samples from microphone will be streamed
const uint16_t computerMsgPort = BOARD_TYPE == 'L' ? 5007 : 5010; // port the teh server(computer) at which device stats
bool computerDiscovered = false;
const uint32_t imageStreamPktSize = 1400;
WiFiUDP udpServer;

// device stats monitoring
DeviceMonitor devMonitor(BATTERY_PIN);
int deviceStats[8];
const unsigned long deviceStatsSendingInterval = 500; 
unsigned long lastDevuceStatsSendTime = 0;

// toggles image streaming state
void toggleSingleImgStream(bool toggle){
  camera.imageStreamingStarted = toggle;
}
// toggles dual image streaming
void toggleDualImgStream(bool toggle){
  dualImgStreamStarted = toggle;
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
    
    speaker.attach();
    speaker.lockI2Sport = false; // allow the speaker to automatically re-attach when needed
  }
}

// handles incoming data through websocket
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:{
      // get the IP address of the connected client (the computer)
      computerIP = webSocketServer.remoteIP(num);
      computerDiscovered = true;
      break;
    }
    case WStype_TEXT:{
      String msg((char*)payload, length);

      if (msg == "captureHigh") {
        if(camera.currentRes != 'h'){
          camera.setResolution('h');
        }
        if (camera.captureStaticImg() && camera.latestFb != NULL) {
            webSocketServer.broadcastBIN(camera.latestFb->buf, camera.latestFb->len);
            camera.clearFrameBuffer();
        }
      } else if (msg == "captureLow"){
        if(camera.currentRes != 'l'){
          camera.setResolution('l');
        }
        if (camera.captureStaticImg() && camera.latestFb != NULL) {
            webSocketServer.broadcastBIN(camera.latestFb->buf, camera.latestFb->len);
            camera.clearFrameBuffer();
        }
      } else if (msg == "strtSingleImgStream"){
        imgFrameID = 0; // reset imgFrame id to prevent overflow over long term streams
        if(camera.currentRes != 'l'){
          camera.setResolution('l');
        }
        toggleSingleImgStream(true);
      } else if (msg == "stpSingleImgStream"){
        toggleSingleImgStream(false);
      } else if (msg == "strtMicStream"){
        toggleMicAudioStreaming(true);
      } else if (msg == "stpMicStream"){
        toggleMicAudioStreaming(false);
      }
      // these condition only executes in left esp: 
      #if BOARD_TYPE == 'L'
        if (msg == "strtDualImgStream"){
            Serial.println("Starting Dual Stream...");
            imgFrameID = 0; // reset imgFrame id to prevent overflow over long term streams
            // stop single streaming
            if(camera.imageStreamingStarted){
              toggleSingleImgStream(false);
            }

            camera.setResolution('l'); 
            EspSerial.requestDualStream(); // tell right esp to initialize dual stream
          
        } else if (msg == "stpDualImgStream"){
            toggleDualImgStream(false);
        }
      #endif
      break;
    }
    case WStype_DISCONNECTED:{
      break;
    }
    default:{
      break;
    }
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
      speaker.lastSampleTime = millis(); // update last audio arrival time
    }
  }
}

// sends image via UDP
void sendImgFrameUDP(camera_fb_t *fb, uint16_t dist_cm, uint8_t imgFrameType, uint16_t imgFrameID){
    for(uint32_t offset = 0; offset < fb->len; offset += imageStreamPktSize){
      uint16_t chunk = imageStreamPktSize;
      if(offset + chunk > fb->len){
          chunk = fb->len - offset;
      }

      udpServer.beginPacket(computerIP, computerImgPort);
      udpServer.write((uint8_t*)&imgFrameID, 2);      // 2-byte imgFrame id
      udpServer.write((uint8_t*)&offset, 4);          // 4-byte payload offset
      udpServer.write((uint8_t*)&imgFrameType, 1);    // 1-byte stream type (0 for single stream and 1 for dual stream)
      udpServer.write((uint8_t*)&dist_cm, 2);         // 2-byte TOF distance
      udpServer.write(fb->buf + offset, chunk);       // actual payload
      udpServer.endPacket();

      vTaskDelay(pdMS_TO_TICKS(10)); // small delay between packets to give esp32 some breathing space
    }
}

// sends audio stream from mic via UDP
void sendAudioUDP(int16_t* samples){
    if (computerIP) { 
        udpServer.beginPacket(computerIP, computerMicPort);
        udpServer.write((uint8_t*)samples, mic.micBufferSize * 2); 
        udpServer.endPacket();
    }
}

// sends device stats via UDP
void sendDeviceStats(){
  devMonitor.getInfo(deviceStats); // fills index 0-5
  deviceStats[6] = dist_mm;     // TOF distance
  deviceStats[7] = WiFi.RSSI(); // wifi signal strength

  udpServer.beginPacket(computerIP, computerMsgPort);
  udpServer.write((uint8_t*)deviceStats, sizeof(deviceStats)); 
  udpServer.endPacket();
}

#if BOARD_TYPE == 'L'
  void dualImgFrameCaptureTask(void *params){
    for(;;){
      if(!dualImgStreamStarted){
        vTaskDelay(pdMS_TO_TICKS(5));
        continue;
      }

      imgFrameID++;
      rightEspCaptureDone = false;
      EspSerial.requestCapture(imgFrameID); // request Right ESP (slave) to capture and send image with the same imgFrame id

      // capture and send image to server(computer)
      if (camera.captureStaticImg() && camera.latestFb != NULL) {
        const uint16_t dist_cm = dist_mm/10;
        sendImgFrameUDP(camera.latestFb, dist_cm, 1, imgFrameID);
        camera.clearFrameBuffer();
      }

      // wait for Right ESP to finish capturung and sending the image
      uint32_t timeout = millis();
      while(!rightEspCaptureDone){
        vTaskDelay(pdMS_TO_TICKS(5));
        
        // safety: timeout after 2 seconds so the master doesn't hang forever
        if(millis() - timeout > 2000) {
          Serial.println("Slave Timeout!");
          break; 
        }
      }
    }
  }
#endif

// this function fires whenever the Left ESP or Right ESP receives a message through the Inter-ESP-UART
void onEspMessage(String head, String tail){
  #if BOARD_TYPE == 'L' // logic for Left Esp board (master)
    if(head == "dualImgStreamReady"){
      Serial.println("Slave is ready for dual streaming!");
      imgFrameID = 0;
      toggleDualImgStream(true);
    } else if(head == "imgSent"){
      rightEspCaptureDone = true;
    }
  #else // logic for Right Esp board(slave) 
    if(head == "strtDualImgStream"){
      // stop single streaming
      if(camera.imageStreamingStarted){
        toggleSingleImgStream(false);
      }
      camera.setResolution('l');
      EspSerial.indicateDualStreamReady(); // reply to Left ESP (master) that Right ESP(slave) is ready for dual streaming
    } else if(head == "captureImg"){
      uint16_t syncedImgFrameID = tail.toInt(); // same imgFrame id as Left ESP(master) 

      // capture and send image to server(computer)
      if (camera.captureStaticImg() && camera.latestFb != NULL) {
        const uint16_t dist_cm = dist_mm/10;
        sendImgFrameUDP(camera.latestFb, dist_cm, 1, syncedImgFrameID);
        camera.clearFrameBuffer();
      }

      EspSerial.indicateFrameSent(); // indicate Left ESP (master) that the image was sent 
    }
  #endif
}

void setup() {
    Serial.begin(115200);
    EspSerial.begin(INTERCOMM_RX, INTERCOMM_TX, onEspMessage);
    
    camera.attach();
    speaker.attach();

    // set unique hostnames for the two boards so that they can be easily identified on the network
    #if BOARD_TYPE == 'L'
      WiFi.setHostname("ESP32S3-Left");
    #else
      WiFi.setHostname("ESP32S3-Right");
    #endif

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {}  // wait until connected to wifi

    udpServer.begin(espUDPport);

    Serial.println("ESP32 available at: ");
    Serial.print("\t");Serial.print(WiFi.localIP());Serial.print(":");Serial.print(espWSport);Serial.println("   <- Websocket");
    Serial.print("\t");Serial.print(WiFi.localIP());Serial.print(":");Serial.print(espUDPport);Serial.println("   <- UDP");

    // Attact GPIOs
    pinMode(ONBOARD_LED_PIN, OUTPUT);
    Wire.begin(LASER_SDA_PIN, LASER_SCL_PIN); // attach laser sensor

    // initialize laser distance sensor
    if(lox.begin()){
      distanceSensorBooted = true;
    } else {
      speaker.playTone(Speaker::ERROR); // play error tone to indicate sensor failure
    }

    webSocketServer.begin();
    webSocketServer.onEvent(webSocketEvent);

    xTaskCreatePinnedToCore(camera.frameCaptureTaskWrapper, "ImgFrameCapture", 4096, &camera, 1, NULL, 0); // pin single image streaming task to Core 0
    xTaskCreatePinnedToCore(speaker.speakerTaskWrapper, "AudioPlayback", 4096, &speaker, 1, NULL, 1); // pin audio playback task to Core 1
    xTaskCreatePinnedToCore(mic.micTaskWrapper, "AudioCapture", 4096, &mic, 1, NULL, 1); // pin audio playback task to Core 1

    #if BOARD_TYPE == 'L'
      xTaskCreatePinnedToCore(dualImgFrameCaptureTask, "DualImgFrameCapture", 4096, &camera, 1, NULL, 0); // pin dual image streaming task to Core 0
    #endif

    digitalWrite(ONBOARD_LED_PIN, LOW); // turn on onboard LED to indicate ready state
    camera.setResolution('h'); // start with high resolution
}

void loop() {
    webSocketServer.loop();
    EspSerial.listenToMsg();

    unsigned long now = millis();

    // request distance reading at regular intervals
    if (!waitingForReading && now - lastRequestTime >= sampleInterval && distanceSensorBooted) {
      if (lox.startRange()) {
        lastRequestTime = now;
        waitingForReading = true;
      }
    }

    // send device stats to server at regular intervals
    if(now - lastDevuceStatsSendTime >= deviceStatsSendingInterval){
      if(computerDiscovered){
        sendDeviceStats();
      }
      lastDevuceStatsSendTime = now;
    }

    // handle single image streaming
    if(camera.frameReady){
      const uint16_t dist_cm = dist_mm/10;
      imgFrameID++;
      sendImgFrameUDP(camera.latestFb, dist_cm, 0, imgFrameID);
      camera.clearFrameBuffer();
      camera.frameReady = false;
    }

    // handle incoming UDP data
    int udpPacketSize = udpServer.parsePacket();
    if (udpPacketSize) {
      if(udpPacketSize > 4){
        if(!computerDiscovered) {
          computerIP = udpServer.remoteIP();
          computerDiscovered = true; 
        }
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
            wasAlerting = false; // reset the state
        }
      }
    }

    // read touch sensors and emit events
    int touchState = touch.getTouchState();
    switch(touchState){
      case 1: // single tap
        webSocketServer.broadcastTXT("$#TXT#$touchSingle");
        speaker.playTone(Speaker::TOUCH_SINGLE);
        delay(500); // debounce delay
        break;
      case 2: // double tap
        webSocketServer.broadcastTXT("$#TXT#$touchDouble");
        speaker.playTone(Speaker::TOUCH_DOUBLE);
        delay(500); // debounce delay
        break;
      case 3: // hold
        webSocketServer.broadcastTXT("$#TXT#$touchHold");
        speaker.playTone(Speaker::TOUCH_HOLD);
        delay(500); // debounce delay
        break;
    }

    vTaskDelay(pdMS_TO_TICKS(5)); // gives esp32 some breathing space
}