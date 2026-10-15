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
