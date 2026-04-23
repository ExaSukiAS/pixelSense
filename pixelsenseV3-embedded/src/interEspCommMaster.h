#ifndef INTER_ESP_COMM_MASTER_H
#define INTER_ESP_COMM_MASTER_H

#include <Arduino.h>
#include <HardwareSerial.h>
#include <functional> 

class EspMaster {
    private:
        HardwareSerial EspSerial;
        std::function<void(String, String)> _onMessage = nullptr; // type for the callback function

    public:    
        // initialize EspSerial with UART1 in the constructor initialization list    
        EspMaster() : EspSerial(1) {}

        // starts the communication channel
        void begin(int rxPin, int txPin, std::function<void(String, String)> onMessage) {
            _onMessage = onMessage;
            EspSerial.begin(115200, SERIAL_8N1, rxPin, txPin);
        }

        // listens to any incoming message from Right ESP and calls a callback function (must be used in void loop())
        void listenToMsg(){
            if(EspSerial.available() > 0){
                String msg = EspSerial.readStringUntil('\n');
                msg.trim();
                String tail = "";
                if(_onMessage != nullptr) {
                    _onMessage(msg, tail);
                }
            }
        }

        // requests Right ESP to initialize dual stream
        void requestDualStream(){
            EspSerial.println("strtDualImgStream");
        }

        // requests Right ESP to capture a frame and send it to server with th eprovided frame id
        void requestCapture(uint16_t frameID){
            String message = "captureImg,"+String(frameID);
            EspSerial.println(message);
        }

        // sends a message to the Right ESP (slave)
        void sendMsg(String head, String tail = ""){
            String message = head;
            if(tail != ""){
                message += "," + tail;
            }
            EspSerial.println(message);
        }
};

#endif