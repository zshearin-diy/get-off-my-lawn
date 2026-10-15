import atexit
import re
import subprocess
import sys
import time

import imageio_ffmpeg
from ultralytics import YOLO

# "usb" streams the USB camera via ffmpeg (see README). Pass a cv2 index instead
# to use a camera directly, e.g. `python main.py 1` for the built-in camera.
SOURCE = "usb"

USB_NAME = "USB Camera"
USB_SIZE = "320x240"  # the only sizes this camera offers are 320x240 and 160x120
USB_FPS = "15"        # ...and only at 15fps
STREAM_URL = "tcp://127.0.0.1:5000"

def usb_device_index(ffmpeg):
    """AVFoundation index of the USB camera, which changes between replugs."""
    listing = subprocess.run(
        [ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    ).stderr
    match = re.search(r"\[(\d+)\] " + re.escape(USB_NAME), listing)
    if not match:
        raise RuntimeError("'" + USB_NAME + "' not found. Devices:\n" + listing)
    return match.group(1)


def start_usb_stream():
    """Publish the USB camera as a local TCP stream and return its URL.

    OpenCV cannot open this camera directly -- it offers only 320x240@15fps,
    below what the AVFoundation backend requests -- but it reads a network
    stream fine, so ffmpeg does the capture and YOLO consumes the stream. That
    keeps Ultralytics' own capture loop, which a hand-fed frame loop does not.
    """
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    process = subprocess.Popen([
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "avfoundation", "-framerate", USB_FPS, "-pixel_format", "uyvy422",
        "-video_size", USB_SIZE, "-i", usb_device_index(ffmpeg),
        "-c:v", "mpeg4", "-q:v", "3", "-f", "mpegts", STREAM_URL + "?listen=1",
    ])
    atexit.register(process.kill)
    time.sleep(3)  # let ffmpeg start listening before YOLO connects
    return STREAM_URL


source = sys.argv[1] if len(sys.argv) > 1 else SOURCE
source = start_usb_stream() if source == "usb" else int(source)

model = YOLO("yolo26n.pt")

results = model.track(source=source, show=True, stream=True, save=True)
for r in results:
    names = r.names
    boxes = r.boxes
    name_to_position_map = {}
    center_map = {}
    id_to_names = {}
    for box in boxes:
        if box.id is None:  # the tracker has not assigned this detection an ID yet
            continue
        object_id = int(box.id)
        center_map[object_id] = box.xywhn[0]  # xywhn is (1, 4); [0] is the 4 values
        id_to_names[object_id] = names[int(box.cls)]
    for key, value in center_map.items():
        print(f"id:       {key}")
        print(f"name:     {id_to_names[key]}")
        print(f"center.x: {float(value[0]):.3f}")
        print(f"center.y: {float(value[1]):.3f}")
        print(f"width:    {float(value[2]):.3f}")
        print(f"height:   {float(value[3]):.3f}")
