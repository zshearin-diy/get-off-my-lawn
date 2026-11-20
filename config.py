"""Every tunable value, in one place. The other modules read from here."""

# --- Camera -------------------------------------------------------------------

# cv2 camera index. On this Mac, 1 is the built-in FaceTime camera; on Linux
# (the Pi) the attached camera is normally 0. Override: `python main.py 0`
CAMERA_INDEX = 1

# cv2.flip code applied to every frame before detection, so the steering maths
# sees an upright image: -1 rotates 180 (camera mounted upside down), 0 flips
# vertically, 1 mirrors left-right, None leaves frames untouched.
FLIP = -1

# --- Detection ----------------------------------------------------------------

MODEL = "yolo26n.pt"
TARGET_CLASSES = {"person"}
MIN_CONFIDENCE = 0.5     # weak detections are the main false-trigger source
VERBOSE = False          # print every tracked detection, not just rig activity

# --- Aiming -------------------------------------------------------------------

# The camera rides on the pan/tilt rig, so a detection's offset from the centre
# of frame is the error signal: steer until the target is centered, then fire.
PAN_HOME, TILT_HOME = 90, 90
PAN_LIMITS, TILT_LIMITS = (0, 180), (0, 180)

# Camera field of view in degrees. Measure once: centre something in frame, pan
# until it sits at the frame edge, and double the angle you travelled.
FOV_PAN_DEG, FOV_TILT_DEG = 60.0, 45.0

PAN_SIGN, TILT_SIGN = 1, 1   # flip to -1 if the rig steers away from the target
# Fraction of the error corrected per move. Every move is measured from a frame
# taken after the rig settled, so this can sit near 1; lower it only if a
# mis-measured FOV makes the rig overshoot.
GAIN = 0.6
MAX_STEP = 10.0          # degrees per move, so one bad detection cannot slam the rig
DEADZONE = 0.05          # |error| under this counts as centred

# --- Firing -------------------------------------------------------------------

CENTERED_FRAMES = 3      # consecutive centred frames before firing
COOLDOWN_SECONDS = 10    # minimum gap between firings
LOST_FRAMES = 10         # frames without the locked target before re-locking

# --- Board link ---------------------------------------------------------------

SERIAL_PORT = None       # None autodetects; set e.g. "/dev/cu.usbmodem1101" to pin it
BAUD = 115200            # must match Serial.begin() in arduino/pan_tilt/pan_tilt.ino
# Longest a move or shot may take before giving up on its reply. A full
# 180-degree sweep at the sketch's DEG_PER_SEC plus SETTLE_MS must fit.
COMMAND_TIMEOUT = 3.0
