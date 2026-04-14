#ifndef TOUCHSENSOR_H
#define TOUCHSENSOR_H

#include <Arduino.h>

class TouchSensor{
  private:
    int pin;
    unsigned long lastChangeTime = 0;
    unsigned long touchStart = 0;
    unsigned long lastTapTime = 0;      // time of last release
    unsigned long pendingTapTime = 0;   // time we started waiting for a possible double-tap
    bool lastTouched = false;
    bool pendingSingleTap = false;

    const unsigned long doubleTapWindow = 300; 
    const unsigned long holdWindow = 500;     
  public:
    // constructor to initialize touch sensor pin
    TouchSensor(int touchPin) {
      pinMode(touchPin, INPUT);
      pin = touchPin;
    }

    // Reads touch sensors
    bool readTouch() {
        // Read the touch sensor multiple times to get a more stable reading
        const int numReadings = 5;  
        int totalScore = 0;     
        for (int i = 0; i < numReadings; i++) {
            totalScore += digitalRead(pin);
        }
        float score = (totalScore / (float)numReadings);  

        return (score > 0.7); // Return true if the score is above threshold (considered pressed)
    }

    // returns:
    // 0 = no event
    // 1 = single tap (emitted after doubleTapWindow expires without second tap)
    // 2 = double tap
    // 3 = hold (touch lasted >= holdWindow)
    int getTouchState() {
      unsigned long now = millis();
      bool touched = readTouch();

      // detect state changes
      if (touched != lastTouched) {
        lastChangeTime = now;
        if (touched) {
          touchStart = now; // touch started
        } else {
          if (pendingSingleTap && (now - pendingTapTime) <= doubleTapWindow) { // double tap detection
            pendingSingleTap = false;
            lastTouched = touched;
            return 2;
          } else {
            pendingSingleTap = true;
            pendingTapTime = now;
          }
        }
      } else if (touched && (now - touchStart) >= holdWindow) { // hold detection
        lastTouched = false;
        pendingSingleTap = false;
        return 3;
      }

      if (pendingSingleTap && (now - pendingTapTime) > doubleTapWindow) { // single tap detection
        pendingSingleTap = false;
        lastTouched = touched;
        return 1;
      }

      lastTouched = touched;
      return 0;
    }
};

#endif