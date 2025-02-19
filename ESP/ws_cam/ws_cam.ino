#include <WiFi.h>
#include <WebSocketsServer.h>
#include "esp_camera.h"
/*
#include "BluetoothSerial.h"

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Please run `make menuconfig` to and enable it
#endif

BluetoothSerial SerialBT;*/

const char* ssid = "Amartya";
const char* password = "amartya@@2020";

float touch_1;
float touch_2;
float voltage;

String data_serial;
String ipAddr;

WebSocketsServer webSocketServer(9000); 

camera_config_t config;

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

void setup() {
  Serial.begin(115200);
  //SerialBT.begin("pixelSense");
  pinMode(33, OUTPUT);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {}
  ipAddr = WiFi.localIP().toString();
  Serial.println("Connected to Wi-Fi");
  Serial.print("ws://");
  Serial.print(WiFi.localIP());
  Serial.println(":9000");
  digitalWrite(33, LOW);

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
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  config.frame_size = FRAMESIZE_QXGA; 
  config.jpeg_quality = 10;
  config.fb_count = 2;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  webSocketServer.begin();
  webSocketServer.onEvent(webSocketEvent);
}

void loop() {
  /*if(SerialBT.available() > 0){
      int btData = SerialBT.readStringUntil('\n').toInt();
      if(btData == 1){
        SerialBT.println(ipAddr);
      }
  }*/
  webSocketServer.loop();
  /*
  if (Serial.available() > 0) {
    data_serial = Serial.readStringUntil('\n');
    int numFloats;
    float* floatArray = parseFloats(data_serial, numFloats);
    touch_1 = floatArray[0];
    touch_2 = floatArray[1];
    voltage = floatArray[2];

    if(touch_1 == 1){
      sendImage(data_serial, 1);
    } else if(touch_1 == 2){
      sendImage(data_serial, 1);
    } else if(touch_1 == 3){
      sendImage(data_serial, 0);
    } else if(touch_2 == 1){
      sendImage(data_serial, 1);
    } else if(touch_2 == 2){
      sendImage(data_serial, 0);
    } else if(touch_2 == 3){
      sendImage(data_serial, 1);
    }
  }*/
}

void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_TEXT:
      if (String((char*)payload) == "captureHigh") {
        config.frame_size = FRAMESIZE_QXGA;
        data_serial = '0.00';
        sendImage(data_serial, 1);
      } else if (String((char*)payload) == "captureLow"){
        config.frame_size = FRAMESIZE_VGA;
        data_serial = '0.00';
        sendImage(data_serial, 1);
      }
      break;
    case WStype_DISCONNECTED:
      break;
    default:
      break;
  }
}

void sendImage(String message_to_send, bool image_send) {
  if(image_send){
    camera_fb_t * fb = NULL;

    for (int i = 0; i < 3; i++) {
      fb = esp_camera_fb_get();
      if (fb) {
        esp_camera_fb_return(fb);
      }
      delay(50); 
    }

    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      return;
    } else {
      Serial.println("Image captured");
    }
    webSocketServer.broadcastBIN(fb->buf, fb->len);
    esp_camera_fb_return(fb);
    delay(50);
  }

  webSocketServer.broadcastTXT(message_to_send); 
}

float* parseFloats(String input, int &numFloats) {
  static float floatArray[10];  
  int index = 0;
  char *token;

  char charArray[input.length() + 1];
  input.toCharArray(charArray, input.length() + 1);

  token = strtok(charArray, ",");
  while (token != NULL && index < 10) {  
    floatArray[index] = atof(token);
    token = strtok(NULL, ",");
    index++;
  }
  numFloats = index;
  return floatArray;
}
