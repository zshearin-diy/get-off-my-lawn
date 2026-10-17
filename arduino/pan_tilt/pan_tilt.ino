// Pan/tilt servo driver for get-off-my-lawn.
//
// Reads absolute angle commands from USB serial, one per line:
//     P090T090\n     -> pan to 90 degrees, tilt to 90 degrees
// and replies "ok <pan> <tilt>" so the host can confirm the board is alive.
//
// Wiring:
//   pan servo  signal -> pin 9     (both are PWM-capable pins)
//   tilt servo signal -> pin 10
//   servo power       -> EXTERNAL 5V supply, not the board's 5V pin
//   servo ground      -> supply ground AND a board GND pin (common ground, or
//                        the signal has no reference and the servos jitter)

#include <Servo.h>

const int PAN_PIN = 9;
const int TILT_PIN = 10;
const int HOME_ANGLE = 90;

Servo pan;
Servo tilt;

char buffer[16];
byte length = 0;

void setup() {
  Serial.begin(115200);
  pan.attach(PAN_PIN);
  tilt.attach(TILT_PIN);
  pan.write(HOME_ANGLE);
  tilt.write(HOME_ANGLE);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      buffer[length] = '\0';
      int p, t;
      if (sscanf(buffer, "P%dT%d", &p, &t) == 2) {
        p = constrain(p, 0, 180);
        t = constrain(t, 0, 180);
        pan.write(p);
        tilt.write(t);
        Serial.print("ok ");
        Serial.print(p);
        Serial.print(" ");
        Serial.println(t);
      }
      length = 0;
    } else if (length < sizeof(buffer) - 1) {
      buffer[length++] = c;
    }
  }
}
