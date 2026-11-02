import sys
import time

import cv2

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # the loop still runs (and prints) without a board attached
    serial = None

from ultralytics import YOLO

# cv2 camera index. On this Mac, 1 is the built-in FaceTime camera; on Linux
# (the Pi) the attached camera is normally 0. Override: `python main.py 0`
CAMERA_INDEX = 1

# cv2.flip code applied to every frame before detection, so the steering maths
# sees an upright image: -1 rotates 180 (camera mounted upside down), 0 flips
# vertically, 1 mirrors left-right, None leaves frames untouched.
FLIP = -1

TARGET_CLASSES = {"person"}
MIN_CONFIDENCE = 0.5     # weak detections are the main false-trigger source

# The camera rides on the pan/tilt rig, so a detection's offset from the centre
# of frame is the error signal: steer until the target is centered, then fire.
PAN_HOME, TILT_HOME = 90, 90
PAN_LIMITS, TILT_LIMITS = (0, 180), (0, 180)

# Camera field of view in degrees. Measure once: centre something in frame, pan
# until it sits at the frame edge, and double the angle you travelled.
FOV_PAN_DEG, FOV_TILT_DEG = 60.0, 45.0

PAN_SIGN, TILT_SIGN = 1, 1   # flip to -1 if the rig steers away from the target
GAIN = 0.6               # fraction of the error corrected per update; <1 damps overshoot
MAX_STEP = 10.0          # degrees per update, so one bad frame cannot slam the rig
DEADZONE = 0.05          # |error| under this counts as centred
CENTERED_FRAMES = 3      # consecutive centred frames before firing
COOLDOWN_SECONDS = 10    # minimum gap between firings
LOST_FRAMES = 10         # frames without the locked target before re-locking

SERIAL_PORT = None       # None autodetects; set e.g. "/dev/cu.usbmodem1101" to pin it
BAUD = 115200            # must match Serial.begin() in arduino/pan_tilt/pan_tilt.ino

VERBOSE = False          # print every tracked detection, not just rig activity

rig = {
    "pan": float(PAN_HOME),
    "tilt": float(TILT_HOME),
    "locked": None,      # track id currently being chased
    "missing": 0,        # consecutive frames the locked target was absent
    "centered": 0,       # consecutive frames the target has been centred
    "fired_at": None,    # time.monotonic() of the last firing
}


def clamp(value, limits):
    low, high = limits
    return min(max(value, low), high)


def find_port():
    """First USB serial port that looks like a microcontroller."""
    if SERIAL_PORT:
        return SERIAL_PORT
    for port in list_ports.comports():
        if any(tag in port.device for tag in ("usbmodem", "usbserial", "ttyACM", "ttyUSB")):
            return port.device
    return None


def open_board():
    """Connect to the servo board, or return None to run in print-only mode.

    Opening the port resets an Arduino, so wait before sending: commands written
    during the bootloader window are discarded.
    """
    if serial is None:
        print("[board]   pyserial not installed, printing angles only")
        return None
    port = find_port()
    if port is None:
        print("[board]   no serial port found, printing angles only")
        return None
    try:
        board = serial.Serial(port, BAUD, timeout=1)
    except OSError as error:
        print(f"[board]   cannot open {port} ({error}), printing angles only")
        return None
    time.sleep(2)  # let the board finish resetting
    print(f"[board]   connected on {port}")
    return board


def send_angles(pan, tilt, pan_delta, tilt_delta):
    """Where the servo command goes once a board is wired up.

    Absolute angles are the source of truth -- servos are position devices, and
    sending only deltas lets a dropped command become permanent drift. The
    deltas are supplied too, since that is what a stepper or continuous-rotation
    servo would want. The wire format matches the sketch in
    arduino/pan_tilt/pan_tilt.ino: "P090T090\\n".
    """
    print(
        f"[rig]     pan {pan:3d} ({pan_delta:+.1f})  "
        f"tilt {tilt:3d} ({tilt_delta:+.1f})"
    )
    if board is not None:
        board.write(f"P{pan:03d}T{tilt:03d}\n".encode())


def fire():
    """Pulse the solenoid, once the target is centred and settled.

    The board owns the pulse length: sending "F" asks for one shot and the
    sketch releases it on its own. Holding a solenoid on from here would mean a
    crash or an unplugged cable leaves it energised, which overheats the coil.
    """
    print("[fire]    target centred")
    if board is None:
        print("[fire]    no board, solenoid not fired")
        return
    board.write(b"F\n")


def steer(error_x, error_y):
    """Move the rig a fraction of the way toward centring the target.

    error_x/error_y are the target's offset from the centre of frame, in the
    range -0.5..0.5. Because the camera moves with the rig, the next frame
    measures a smaller error, so repeated partial corrections converge.
    """
    pan_delta = clamp(
        error_x * FOV_PAN_DEG * GAIN * PAN_SIGN, (-MAX_STEP, MAX_STEP)
    )
    tilt_delta = clamp(
        error_y * FOV_TILT_DEG * GAIN * TILT_SIGN, (-MAX_STEP, MAX_STEP)
    )
    rig["pan"] = clamp(rig["pan"] + pan_delta, PAN_LIMITS)
    rig["tilt"] = clamp(rig["tilt"] + tilt_delta, TILT_LIMITS)
    send_angles(int(round(rig["pan"])), int(round(rig["tilt"])), pan_delta, tilt_delta)


def pick_target(targets):
    """Stay locked on one target; prefer the largest (nearest) when re-locking.

    Without a lock the rig oscillates between two people instead of centring
    either one.
    """
    if rig["locked"] in targets:
        rig["missing"] = 0
        return rig["locked"]

    rig["missing"] += 1
    if rig["locked"] is not None and rig["missing"] < LOST_FRAMES:
        return None  # brief dropout; hold position rather than switching

    rig["locked"] = max(
        targets, key=lambda i: float(targets[i][2]) * float(targets[i][3]), default=None
    )
    rig["missing"] = 0
    rig["centered"] = 0
    return rig["locked"]


def evaluate(targets, now):
    """Steer toward the locked target, and fire once it is centred."""
    object_id = pick_target(targets)
    if object_id is None:
        return

    center_x, center_y = float(targets[object_id][0]), float(targets[object_id][1])
    error_x, error_y = center_x - 0.5, center_y - 0.5

    if abs(error_x) > DEADZONE or abs(error_y) > DEADZONE:
        rig["centered"] = 0
        steer(error_x, error_y)
        return

    rig["centered"] += 1
    if rig["centered"] < CENTERED_FRAMES:
        return
    if rig["fired_at"] is not None and now - rig["fired_at"] < COOLDOWN_SECONDS:
        return

    rig["fired_at"] = now
    print(f"[centred] id {object_id} at ({center_x:.3f}, {center_y:.3f})")
    fire()


board = open_board()

camera = int(sys.argv[1]) if len(sys.argv) > 1 else CAMERA_INDEX

model = YOLO("yolo26n.pt")

# Filter at the model: the tracker then only assigns and maintains IDs for
# classes we care about, instead of tracking every chair in view and discarding
# it below. TARGET_CLASSES stays the single knob; these are its numeric IDs.
target_ids = sorted(i for i, name in model.names.items() if name in TARGET_CLASSES)
if not target_ids:
    raise SystemExit(f"No such classes in this model: {sorted(TARGET_CLASSES)}")


def frames(capture):
    """Camera frames, flipped upright.

    The camera is read here rather than handed to model.track as a source, so
    each frame can be flipped before the model sees it.
    """
    while True:
        ok, frame = capture.read()
        if not ok:
            return
        yield frame if FLIP is None else cv2.flip(frame, FLIP)


capture = cv2.VideoCapture(camera)
if not capture.isOpened():
    raise SystemExit(f"Cannot open camera {camera}")

writer = None  # created on the first frame, once its size is known
for frame in frames(capture):
    # persist=True keeps tracker IDs across calls now that frames arrive one at a time
    r = model.track(frame, classes=target_ids, persist=True, verbose=False)[0]

    annotated = r.plot()
    cv2.imshow("get-off-my-lawn", annotated)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
    if writer is None:
        height, width = annotated.shape[:2]
        fps = capture.get(cv2.CAP_PROP_FPS) or 30
        writer = cv2.VideoWriter(
            "runs/track.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
    writer.write(annotated)

    names = r.names
    boxes = r.boxes
    name_to_position_map = {}
    center_map = {}
    id_to_names = {}
    targets = {}
    for box in boxes:
        if box.id is None:  # the tracker has not assigned this detection an ID yet
            continue
        object_id = int(box.id)
        center_map[object_id] = box.xywhn[0]  # xywhn is (1, 4); [0] is the 4 values
        id_to_names[object_id] = names[int(box.cls)]
        if float(box.conf) >= MIN_CONFIDENCE:  # classes already filtered by the model
            targets[object_id] = box.xywhn[0]

    evaluate(targets, time.monotonic())

    if VERBOSE:
        for key, value in center_map.items():
            print(f"id:       {key}")
            print(f"name:     {id_to_names[key]}")
            print(f"center.x: {float(value[0]):.3f}")
            print(f"center.y: {float(value[1]):.3f}")
            print(f"width:    {float(value[2]):.3f}")
            print(f"height:   {float(value[3]):.3f}")

capture.release()
if writer is not None:
    writer.release()
cv2.destroyAllWindows()
