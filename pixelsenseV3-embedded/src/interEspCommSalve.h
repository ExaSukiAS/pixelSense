#ifndef INTER_ESP_COMM_SLAVE_H
#define INTER_ESP_COMM_SLAVE_H

#include <Arduino.h>
#include <HardwareSerial.h>
#include <functional> 

class EspSlave {
    private:
        HardwareSerial EspSerial;
        std::function<void(String, String)> _onMessage = nullptr; // type for the callback function

        void splitString(String input, String& head, String& tail) {
            int commaIndex = input.indexOf(',');

            if (commaIndex != -1) {
                head = input.substring(0, commaIndex);
                tail = input.substring(commaIndex + 1);
            } else {
                head = input;
                tail = "";
            }
        }

    public:        
        // initialize EspSerial with UART1 in the constructor initialization list
        EspSlave() : EspSerial(1) {}

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
                String head, tail;
                splitString(msg, head, tail);
                if(_onMessage != nullptr) {
                    _onMessage(head, tail);
                }
            }
        }

        // indications to the Left ESP(master)
        void indicateDualStreamReady(){EspSerial.println("dualImgStreamReady");}
        void indicateFrameSent(){EspSerial.println("imgSent");}

        // sends a message to the Left ESP (master)
        void sendMsg(String head, String tail = ""){
            String message = head;
            if(tail != ""){
                message += "," + tail;
            }
            EspSerial.println(message);
        }
};

#endif