// Pan/tilt servo driver for get-off-my-lawn.
//
// Reads commands from USB serial, one per line:
//     P090T090\n     -> pan to 90 degrees, tilt to 90 degrees  ("ok 90 90")
//     F\n            -> fire the solenoid for FIRE_MS           ("ok fire")
//
// Wiring:
//   pan servo  signal -> pin 9     (both are PWM-capable pins)
//   tilt servo signal -> pin 10
//   servo power       -> EXTERNAL 5V supply, not the board's 5V pin
//   servo ground      -> supply ground AND a board GND pin (common ground, or
//                        the signal has no reference and the servos jitter)
//   solenoid driver   -> pin 7 drives a MOSFET gate or relay input; the
//                        solenoid itself runs from its own supply and MUST
//                        have a flyback diode across it. Never wire a solenoid
//                        straight to a pin -- it draws far more than a pin can
//                        source, and the coil kicks back a damaging spike when
//                        it switches off.

#include <Servo.h>

const int PAN_PIN = 9;
const int TILT_PIN = 10;
const int FIRE_PIN = 7;
const int HOME_ANGLE = 90;

// How long one shot lasts. The board times this itself so a host crash or an
// unplugged USB cable cannot leave the coil energised.
const unsigned long FIRE_MS = 400;

bool firing = false;
unsigned long fireUntil = 0;

Servo pan;
Servo tilt;

char buffer[16];
byte length = 0;

void setup() {
  Serial.begin(115200);
  pinMode(FIRE_PIN, OUTPUT);
  digitalWrite(FIRE_PIN, LOW);   // before anything else, so it cannot fire on reset
  pan.attach(PAN_PIN);
  tilt.attach(TILT_PIN);
  pan.write(HOME_ANGLE);
  tilt.write(HOME_ANGLE);
}

void loop() {
  // Release the solenoid once its pulse has elapsed. Done with millis() rather
  // than delay() so servo commands keep being handled while it is energised.
  if (firing && millis() >= fireUntil) {
    digitalWrite(FIRE_PIN, LOW);
    firing = false;
  }

  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      buffer[length] = '\0';
      int p, t;
      if (buffer[0] == 'F') {
        digitalWrite(FIRE_PIN, HIGH);
        firing = true;
        fireUntil = millis() + FIRE_MS;
        Serial.println("ok fire");
      } else if (sscanf(buffer, "P%dT%d", &p, &t) == 2) {
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
