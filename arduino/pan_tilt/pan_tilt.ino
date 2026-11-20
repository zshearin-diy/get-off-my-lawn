// Pan/tilt servo driver for get-off-my-lawn.
//
// Reads commands from USB serial, one per line. Each reply is sent only once
// the action has FINISHED, so the host can wait for it before looking again:
//     P090T090\n     -> sweep pan/tilt to 90/90, settle   -> "moved 90 90"
//     F\n            -> pulse the solenoid for FIRE_MS    -> "fired"
// A command may end in "#<id>"; the reply then ends in the same "#<id>", so the
// host can tell its reply apart from a stale one:
//     P120T060#7\n   -> "moved 120 60 #7"
// On power-up / reset the board prints "ready".
//
// Hobby servos give no position feedback, so the board cannot *measure* when a
// move is done. Instead it sweeps the servo itself at DEG_PER_SEC, which is set
// below the servo's real speed: the shaft keeps up with the commanded angle,
// and when the sweep ends the shaft is there. Swapping motors means changing
// only the "Motor tuning" constants.
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

// ---- Motor tuning: the only values that depend on which servos are fitted ----
// Sweep speed. Must stay BELOW the servo's speed under load, or the commanded
// angle runs ahead of the shaft and "moved" is reported early. MG996R is about
// 0.17s/60deg (~350 deg/s) unloaded at 5V; 120 leaves margin for the camera.
const float DEG_PER_SEC = 120.0;
// Pause after the sweep for the shaft to stop and the rig to stop wobbling,
// so the next camera frame is sharp and shows the final aim.
const unsigned long SETTLE_MS = 150;
// -----------------------------------------------------------------------------

// How long one shot lasts. The board times this itself so a host crash or an
// unplugged USB cable cannot leave the coil energised.
const unsigned long FIRE_MS = 400;

const unsigned long STEP_MS = 10;  // sweep update interval

struct Axis {
  Servo servo;
  float position;  // angle currently commanded, mid-sweep
  int target;      // angle the sweep is heading for
};

Axis pan;
Axis tilt;

// Motion: SWEEPING -> SETTLING -> IDLE (reply sent on reaching IDLE).
enum Motion { IDLE, SWEEPING, SETTLING };
Motion motion = IDLE;
unsigned long lastStep = 0;
unsigned long settleUntil = 0;
long moveId = -1;  // -1: the command carried no "#<id>"

// Firing is independent of motion, so the pulse always ends on time.
bool firing = false;
unsigned long fireUntil = 0;
long fireId = -1;

char buffer[24];
byte length = 0;

void printId(long id) {
  if (id >= 0) {
    Serial.print(" #");
    Serial.print(id);
  }
  Serial.println();
}

// Move one axis up to maxStep degrees toward its target; true once there.
bool stepAxis(Axis &axis, float maxStep) {
  float remaining = axis.target - axis.position;
  if (fabs(remaining) <= maxStep) {
    axis.position = axis.target;
  } else {
    axis.position += remaining > 0 ? maxStep : -maxStep;
  }
  axis.servo.write((int)round(axis.position));
  return axis.position == axis.target;
}

void startMove(int p, int t, long id) {
  // A new move replaces one in progress; the old one is never reported.
  pan.target = constrain(p, 0, 180);
  tilt.target = constrain(t, 0, 180);
  moveId = id;
  motion = SWEEPING;
  lastStep = millis();
}

void startFire(long id) {
  digitalWrite(FIRE_PIN, HIGH);
  firing = true;
  fireUntil = millis() + FIRE_MS;
  fireId = id;
}

void handleLine(char *line) {
  long id = -1;
  char *hash = strchr(line, '#');
  if (hash != NULL) {
    id = atol(hash + 1);
    *hash = '\0';
  }

  int p, t;
  if (line[0] == 'F') {
    startFire(id);
  } else if (sscanf(line, "P%dT%d", &p, &t) == 2) {
    startMove(p, t, id);
  } else {
    Serial.print("error ");
    Serial.println(line);
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      buffer[length] = '\0';
      if (length > 0) {
        handleLine(buffer);
      }
      length = 0;
    } else if (length < sizeof(buffer) - 1) {
      buffer[length++] = c;
    }
  }
}

void setup() {
  pinMode(FIRE_PIN, OUTPUT);
  digitalWrite(FIRE_PIN, LOW);  // before anything else, so it cannot fire on reset
  Serial.begin(115200);
  pan.servo.attach(PAN_PIN);
  tilt.servo.attach(TILT_PIN);
  pan.position = pan.target = HOME_ANGLE;
  tilt.position = tilt.target = HOME_ANGLE;
  pan.servo.write(HOME_ANGLE);
  tilt.servo.write(HOME_ANGLE);
  Serial.println("ready");
}

void loop() {
  unsigned long now = millis();

  // Done with millis() rather than delay() so commands keep being read and the
  // solenoid keeps being timed while the servos sweep.
  if (firing && (long)(now - fireUntil) >= 0) {
    digitalWrite(FIRE_PIN, LOW);
    firing = false;
    Serial.print("fired");
    printId(fireId);
  }

  if (motion == SWEEPING && now - lastStep >= STEP_MS) {
    float maxStep = DEG_PER_SEC * (now - lastStep) / 1000.0;
    lastStep = now;
    bool panThere = stepAxis(pan, maxStep);
    bool tiltThere = stepAxis(tilt, maxStep);
    if (panThere && tiltThere) {
      motion = SETTLING;
      settleUntil = now + SETTLE_MS;
    }
  }

  if (motion == SETTLING && (long)(now - settleUntil) >= 0) {
    motion = IDLE;
    Serial.print("moved ");
    Serial.print(pan.target);
    Serial.print(" ");
    Serial.print(tilt.target);
    printId(moveId);
  }

  readSerial();
}
