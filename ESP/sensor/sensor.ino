/*
15 - touch1
4 - touch2
36 - IR sensor
32 - Voltage sensor
18 - speaker out

{t1_state, t2_state, voltage}

single click = 1
double click = 2
hold = 3
nothing = 0
*/

int touch1_pin = 32;
int touch2_pin = 33;
int speaker_pin = 26;
int IR_pin = 36;
int battery_pin = 15;

int touch1;
int touch2;
int IR_val;
int least_touch1 = 9999;
int least_touch2 = 9999;
int highest_IR = 0;

const int touch_threshold = 20;
const int IR_threshold = 200;
const int calibration_iteration = 1000;
const unsigned long double_click_threshold = 300;
const unsigned long hold_threshold = 500;

bool t1_holded = false;
bool t1_pressed = false;
unsigned long t1_touch_time;
unsigned long t1_last_click_time = 0;
int t1_click_count = 0;

bool t2_holded = false;
bool t2_pressed = false;
unsigned long t2_touch_time;
unsigned long t2_last_click_time = 0;
int t2_click_count = 0;

int voltage;

String formatted;
String data_serial;

void setup() {
  Serial.begin(115200);
  ledcSetup(0, 5000, 8);
  ledcAttachPin(speaker_pin, 0);

  for (int i = 0; i <= calibration_iteration; i++) {
    touch1 = touchRead(touch1_pin);
    touch2 = touchRead(touch2_pin);
    if (touch1 < least_touch1) {
      least_touch1 = touch1;
    }
    if (touch2 < least_touch2) {
      least_touch2 = touch2;
    }
  }

  for (int i = 0; i <= calibration_iteration; i++) {
    IR_val = analogRead(IR_pin);
    if (IR_val > highest_IR) {
      highest_IR = IR_val;
    }
  }
}

void loop() {
  voltage = analogRead(battery_pin);
  touch1 = touchRead(touch1_pin);
  touch2 = touchRead(touch2_pin);

  if (Serial.available() > 0) {
    data_serial = Serial.readStringUntil('\n');
    if (data_serial == "fetch_voltage") {
      Serial.println(voltage);
    }
  }

  if (analogRead(IR_pin) > highest_IR + IR_threshold) {
    //wake up
    ledcWriteTone(0, 5000);
    delay(50);
  } else {
    ledcWriteTone(0, 0);
  }

  //touch sensor 1
  if (touch1 < least_touch1 - touch_threshold) {
    if (!t1_pressed) {
      t1_pressed = true;
      t1_touch_time = millis();
      t1_holded = false;
    } else {
      unsigned long elapsed_time = millis() - t1_touch_time;
      if (elapsed_time > hold_threshold && !t1_holded) {
        //wake up
        formatted = "3,0," + voltage;
        Serial.println(formatted);
        t1_holded = true;
        ledcWriteTone(0, 500);
        delay(200);
        ledcWriteTone(0, 0);
      }
    }
  } else {
    if (t1_pressed) {
      unsigned long elapsed_time = millis() - t1_touch_time;
      t1_pressed = false;
      if (!t1_holded) {
        if (elapsed_time <= hold_threshold) {
          t1_click_count++;
          if (t1_click_count == 1) {
            t1_last_click_time = millis();
          } else if (t1_click_count == 2 && millis() - t1_last_click_time < double_click_threshold) {
            //wake up
            formatted = "2,0," + voltage;
            Serial.println(formatted);
            t1_click_count = 0;
            ledcWriteTone(0, 500);
            delay(200);
            ledcWriteTone(0, 0);
          }
        }
      }
    }
  }
  if (t1_click_count == 1 && millis() - t1_last_click_time > double_click_threshold) {
    //wake up
    formatted = "1,0," + voltage;
    Serial.println(formatted);
    t1_click_count = 0;
    ledcWriteTone(0, 500);
    delay(200);
    ledcWriteTone(0, 0);
  }

  //touch sensor 2
  if (touch2 < least_touch2 - touch_threshold) {
    if (!t2_pressed) {
      t2_pressed = true;
      t2_touch_time = millis();
      t2_holded = false;
    } else {
      unsigned long elapsed_time = millis() - t2_touch_time;
      if (elapsed_time > hold_threshold && !t2_holded) {
        //wake up
        formatted = "0,3," + voltage;
        Serial.println(formatted);
        t2_holded = true;
        ledcWriteTone(0, 500);
        delay(200);
        ledcWriteTone(0, 0);
      }
    }
  } else {
    if (t2_pressed) {
      unsigned long elapsed_time = millis() - t2_touch_time;
      t2_pressed = false;
      if (!t2_holded) {
        if (elapsed_time <= hold_threshold) {
          t2_click_count++;
          if (t2_click_count == 1) {
            t2_last_click_time = millis();
          } else if (t2_click_count == 2 && millis() - t2_last_click_time < double_click_threshold) {
            //wake up
            formatted = "0,2," + voltage;
            Serial.println(formatted);
            ledcWriteTone(0, 500);
            delay(200);
            ledcWriteTone(0, 0);
          }
        }
      }
    }
  }
  if (t2_click_count == 1 && millis() - t2_last_click_time > double_click_threshold) {
    //wake up
    formatted = "0,1," + voltage;
    Serial.println(formatted);
    t2_click_count = 0;
    ledcWriteTone(0, 500);
    delay(200);
    ledcWriteTone(0, 0);
  }
}
