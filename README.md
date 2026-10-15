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
- **Camera.** `SOURCE` at the top of `main.py` selects the input. Default
  `"usb"` streams the USB camera through ffmpeg; pass a cv2 index instead to use
  a camera directly:

  ```sh
  python main.py          # USB camera, via ffmpeg stream
  python main.py 1        # built-in FaceTime camera, direct
  ```

  The USB camera's AVFoundation index is resolved by name at runtime, because it
  changes between replugs -- it has been observed at both 0 and 1 within a single
  session, so hardcoding it is unreliable.
- `save=True` in `main.py` writes annotated video to `runs/` (gitignored).
- Model weights (`yolo11n.pt`) download automatically on first use and are
  gitignored — no need to commit them.

## Why the USB camera needs ffmpeg

`cv2.VideoCapture` cannot open the USB camera at all, failing with
`VIDEOIO(AVFOUNDATION): raised unknown C++ exception!`. The camera offers only
320x240 and 160x120, both at 15fps, while OpenCV's AVFoundation backend requests
a higher resolution and ~30fps. Verified dead ends:

- Every index and backend pair (`CAP_AVFOUNDATION`, `CAP_ANY`).
- Explicit MJPG/YUY2 formats at 320x240 and 160x120, set before and at open time.
- opencv-python 4.10, 4.9 and 4.8 -- identical exception from each.

The camera is healthy: AVFoundation reports it connected and captures ~15fps
from it directly, and it works in Google Meet.

The fix relies on OpenCV being built with `FFMPEG: YES`, so while it cannot open
the *device*, it reads a *network stream* without trouble. `main.py` has ffmpeg
capture the camera and publish it to `tcp://127.0.0.1:5000`, then hands that URL
to YOLO. Ultralytics treats `tcp://` as a stream (`udp://` is rejected as a file
path), so its own capture loop drives playback -- the same smooth path the
built-in camera uses. Feeding frames in one at a time instead makes the display
pulse and stutter, because each `model.track()` call resets the window.

The ffmpeg binary comes from the `imageio-ffmpeg` pip wheel. Homebrew cannot
supply it here: it no longer builds Intel x86_64 bottles, so `brew install
ffmpeg` compiles from source, which this machine's Command Line Tools cannot do
(they predate macOS 26).

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
