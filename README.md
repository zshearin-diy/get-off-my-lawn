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
- **Camera.** `CAMERA_INDEX` at the top of `main.py`, or override per-run:
  `python main.py 0`. On this Mac index 1 is the built-in FaceTime camera. The
  USB camera (320x240 @ 15fps only) cannot be opened by `cv2` on macOS at all --
  its AVFoundation backend requests a higher resolution and framerate than the
  device offers, and every index, backend, explicit format and opencv-python
  version from 4.8 to 4.10 fails identically. On Linux it goes through V4L2
  instead, where it is expected to work normally.
- `save=True` in `main.py` writes annotated video to `runs/` (gitignored).
- Model weights (`yolo11n.pt`) download automatically on first use and are
  gitignored — no need to commit them.

## Pan/tilt control

The camera is mounted on the pan/tilt rig, so a detection's offset from the
centre of frame *is* the error signal: the rig steers until the target is
centred, then `fire()` sends the separate signal. Each update moves a fraction
(`GAIN`) of the remaining error, so corrections converge over a few frames
instead of overshooting.

`send_angles()` emits **absolute** angles plus the delta. Absolute is the source
of truth -- servos are position devices, and sending only deltas lets a dropped
command become permanent drift -- while the delta is there for a stepper or
continuous-rotation servo.

Three things need calibrating on the real hardware:

- `FOV_PAN_DEG` / `FOV_TILT_DEG` -- the camera's field of view. Centre something
  in frame, pan until it sits at the frame edge, double the angle travelled.
- `PAN_SIGN` / `TILT_SIGN` -- flip to `-1` if the rig steers *away* from the
  target. Which sign is correct depends on how the servos are mounted.
- `GAIN` -- raise for faster convergence, lower if the rig oscillates around
  centre. Start at 0.6.

`DEADZONE` is what stops the rig hunting forever: inside it the target counts as
centred, so a small residual offset (a couple of degrees) is expected and
desirable. `MAX_STEP` caps degrees per update so a single bad detection cannot
slam the servos.

Only one target is chased at a time. `pick_target()` locks onto the largest
(nearest) box and keeps it, tolerating `LOST_FRAMES` of dropout before
re-locking -- without that the rig oscillates between two people instead of
centring either.

## Sound

`fire()` calls `play_sound()`, which shells out to the OS player -- `afplay` on
macOS, `aplay` on Linux and the Pi -- via `Popen` so playback does not block
detection. `SOUND_FILE` is a WAV deliberately: `aplay` plays it with no extra
packages, where mp3 would need `mpg123` or similar installed.

`alert.wav` in the repo is a generated 0.3s chirp, there so this is testable
before you pick a real sound. Replace it with any mono/stereo 16-bit WAV.

A missing file or missing player prints a warning and continues rather than
raising -- losing audio should not stop the rig. Overlapping playback is not a
concern because `COOLDOWN_SECONDS` already spaces firings further apart than any
sensible clip.

## Servo hardware

The Mac (or Pi) runs vision and sends angles; a microcontroller turns them into
PWM. A Pi *can* drive servos from its own GPIO, but its general-purpose PWM is
software-timed and jitters under exactly the load a neural net creates, so a
separate board is the more reliable arrangement.

```
host (YOLO)  --USB serial-->  Arduino  --PWM-->  pan + tilt servos
             "P090T090\n"      Servo.h
```

Flash `arduino/pan_tilt/pan_tilt.ino`. It reads one absolute command per line
and replies `ok <pan> <tilt>`. **[HARDWARE.md](HARDWARE.md) has step-by-step
setup instructions** written for someone new to Arduino; the two rules that
cause the most grief:

- **Power servos from an external 5V supply**, not the board's 5V pin. Stall
  current browns the board out and resets it mid-run.
- **Common ground.** Servo ground must reach both the supply ground and a board
  GND pin, or the signal has no reference and the servos jitter.

`main.py` autodetects the port (`usbmodem`/`usbserial`/`ttyACM`/`ttyUSB`), or set
`SERIAL_PORT` to pin it. With no board, no port, or no `pyserial`, it prints
angles and keeps running -- so the vision half stays testable on its own.

Bring it up in this order, so a failure has one possible cause:

1. Flash the sketch and confirm the servos centre on power-up.
2. Open the Arduino serial monitor at 115200 and type `P120T060` by hand. The
   servos should move and the board should answer `ok 120 60`.
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

Not useful while the input is the local webcam. `main.py` uses `source=0` (the
camera) with `show=True` (a GUI window), and a Linux container on macOS can
reach neither — Docker Desktop runs in a VM with no camera or display
passthrough. Containerizing becomes worthwhile once the input is a video file,
an RTSP/IP stream, or the program runs headless on Linux.
