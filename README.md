# get-off-my-lawn

Webcam object detection and tracking with YOLO11. Reads from the default camera,
prints the bottom-edge y-position of each detected object, and flags when a
target class (currently `couch`) comes into view.

## Setup

Requires **Python 3.12**. See [Platform notes](#platform-notes) — on Intel Macs
this is a hard requirement, not a preference.

```sh
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Running

The dependencies live in the virtualenv, so you must either activate it or call
its interpreter by path. Running `python3 main.py` will **not** work — that's
your system Python, which has none of the packages installed:

```
ModuleNotFoundError: No module named 'cv2'
```

**Option 1 — activate the venv** (then `python` means the venv's Python for the
rest of the shell session; your prompt shows `(.venv)`, and `deactivate` exits):

```sh
source .venv/bin/activate
python main.py
```

**Option 2 — call the interpreter directly**, no activation needed:

```sh
./.venv/bin/python main.py
```

A virtualenv is never picked up automatically. If you get the `cv2` error again,
this is almost always why.

### Notes

- On first run macOS prompts for camera access for your terminal app. Grant it,
  or the capture device will fail to open.
- **Camera.** `CAMERA_INDEX` in `config.py`, or override per-run:
  `python main.py 0`. On this Mac index 1 is the built-in FaceTime camera. The
  USB camera (320x240 @ 15fps only) cannot be opened by `cv2` on macOS at all --
  its AVFoundation backend requests a higher resolution and framerate than the
  device offers, and every index, backend, explicit format and opencv-python
  version from 4.8 to 4.10 fails identically. On Linux it goes through V4L2
  instead, where it is expected to work normally.
- Annotated video is written to `runs/track.mp4` (gitignored).
- Model weights (`yolo11n.pt`) download automatically on first use and are
  gitignored — no need to commit them.

## Pan/tilt control

The camera is mounted on the pan/tilt rig, so a detection's offset from the
centre of frame *is* the error signal: the rig steers until the target is
centred, then fires. Each move covers a fraction (`GAIN`) of the remaining
error.

The program runs look -> decide -> act strictly in turn:

| Module | Job |
|---|---|
| `main.py` | the loop that wires the others together |
| `config.py` | every tunable value |
| `camera.py` | reads frames on a background thread; hands out only frames captured after a given moment |
| `detector.py` | YOLO tracking, reduced to `{track id: Box}` |
| `controller.py` | which target to chase, where to point, when to fire (pure logic) |
| `rig.py` | serial link to the board; `move()` / `fire()` return once the action is done |

**Detection pauses while the rig moves.** `rig.move()` blocks until the board
reports the move finished (servos stopped and settled), and the next decision is
made only from a frame captured after that. Acting on frames taken mid-move is
what made the rig overshoot: they still showed the target off-centre, so it kept
steering after it had already arrived. The video window freezes briefly during
each move as a result.

Moves are sent as **absolute** angles. Servos are position devices, and sending
only deltas lets a dropped command become permanent drift.

Three things need calibrating on the real hardware:

- `FOV_PAN_DEG` / `FOV_TILT_DEG` -- the camera's field of view. Centre something
  in frame, pan until it sits at the frame edge, double the angle travelled.
- `PAN_SIGN` / `TILT_SIGN` -- flip to `-1` if the rig steers *away* from the
  target. Which sign is correct depends on how the servos are mounted.
- `GAIN` -- raise for faster convergence (each move starts from a settled frame,
  so 0.8-1.0 is reasonable), lower if the rig overshoots. Start at 0.9.

`DEADZONE` is what stops the rig hunting forever: inside it the target counts as
centred, so a small residual offset (a couple of degrees) is expected and
desirable. `MAX_STEP` caps degrees per update so a single bad detection cannot
slam the servos.

Only one target is chased at a time. `Controller._pick_target()` locks onto the largest
(nearest) box and keeps it, tolerating `LOST_FRAMES` of dropout before
re-locking -- without that the rig oscillates between two people instead of
centring either.

## Solenoid

`rig.fire()` sends `F` over the same serial link once a target is centred, and the
sketch pulses pin 7 for `FIRE_MS` (400ms by default), replying `fired` when the
pulse ends.

The board owns the pulse length deliberately. If the host held the solenoid on
and then crashed, lost USB, or was killed mid-pulse, the coil would stay
energised and overheat. Asking for one shot and letting the board time it means
the worst case is a single pulse, not a stuck-on coil. The sketch also drives
pin 7 LOW in `setup()` before anything else, so a board reset cannot fire it.

Pin 7 drives a MOSFET gate or relay input -- never the coil directly -- and the
coil needs a flyback diode across it. See [HARDWARE.md](HARDWARE.md) and the
wiring diagram for both.

With no board connected, `rig.fire()` prints `no board, solenoid not fired` and the
vision half keeps running.

## Servo hardware

The Mac (or Pi) runs vision and sends angles; a microcontroller turns them into
PWM. A Pi *can* drive servos from its own GPIO, but its general-purpose PWM is
software-timed and jitters under exactly the load a neural net creates, so a
separate board is the more reliable arrangement.

```
host (YOLO)  --USB serial-->  Arduino  --PWM-->  pan + tilt servos
             "P090T090#7"      Servo.h
             <- "moved 90 90 #7"
```

Flash `arduino/pan_tilt/pan_tilt.ino`. It reads one absolute command per line
and replies only once the action has **finished**: `moved <pan> <tilt>` after a
move, `fired` after a shot. The optional `#<id>` suffix is echoed back so the host
can match a reply to its command.

Hobby servos report no position, so the sketch makes "finished" knowable by
sweeping the servos itself at `DEG_PER_SEC`, set below the servo's real speed
so the shaft keeps up, then waiting `SETTLE_MS` for the rig to stop wobbling.
**Those two constants are the only motor-specific values** -- change them, and
nothing else, when swapping servos. Any board that speaks this protocol and
replies once its motors have stopped works with the Python side unchanged. **[HARDWARE.md](HARDWARE.md) has step-by-step
setup instructions** written for someone new to Arduino; the two rules that
cause the most grief:

- **Power servos from an external 5V supply**, not the board's 5V pin. Stall
  current browns the board out and resets it mid-run.
- **Common ground.** Servo ground must reach both the supply ground and a board
  GND pin, or the signal has no reference and the servos jitter.

`rig.py` autodetects the port (`usbmodem`/`usbserial`/`ttyACM`/`ttyUSB`), or set
`SERIAL_PORT` to pin it. With no board, no port, or no `pyserial`, it prints
angles and keeps running -- so the vision half stays testable on its own.

Bring it up in this order, so a failure has one possible cause:

1. Flash the sketch and confirm the servos centre on power-up.
2. Open the Arduino serial monitor at 115200 and type `P120T060` by hand. The
   servos should sweep and the board should answer `moved 120 60`.
3. Run `python main.py` and watch for `[board] connected on ...`.

If the rig steers *away* from the target and runs to its limit, flip `PAN_SIGN`
or `TILT_SIGN` -- that is what a mirrored mount looks like.

## Platform notes

Dependencies are platform-sensitive, so `requirements.txt` uses environment
markers and resolves correctly on each:

| Platform | Resolves to |
| --- | --- |
| Intel macOS (x86_64) | torch 2.2.2, numpy<2, opencv<4.11 |
| Apple Silicon / Linux / Windows | torch>=2.4, numpy>=2, opencv>=4.11 |

**Intel macOS:** PyTorch's last published macOS x86_64 wheel is 2.2.2, which
supports Python up to 3.12 — there is no installable `torch` on Python 3.13, so
the venv must be built with 3.12. That build is also compiled against NumPy 1.x
and breaks at import under NumPy 2.

`requirements-lock-macos-x86_64.txt` holds exact pins for bit-identical rebuilds
on an Intel Mac:

```sh
./.venv/bin/pip install -r requirements-lock-macos-x86_64.txt
```

If you test on Apple Silicon, you'll get a substantially newer torch. The code
should be fine, but verify there rather than assuming.

## Docker

Not useful while the input is the local webcam. `main.py` reads the local
camera and opens a GUI window, and a Linux container on macOS can
reach neither — Docker Desktop runs in a VM with no camera or display
passthrough. Containerizing becomes worthwhile once the input is a video file,
an RTSP/IP stream, or the program runs headless on Linux.
