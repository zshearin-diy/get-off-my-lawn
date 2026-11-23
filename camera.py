"""Camera capture on a background thread that always holds the newest frame."""

import threading
import time

import cv2


class Camera:
    """Reads frames continuously, so a reader never gets a stale, queued one.

    cv2 drivers buffer frames internally. If the program only reads after a
    slow step (inference, waiting for the rig to move), the first read returns
    a frame from before that step. Reading non-stop on a thread drains the
    buffer, and timestamping each frame lets `read(newer_than=...)` refuse
    anything captured before a given moment -- such as the end of a move.
    """

    def __init__(self, index, flip=None):
        self._capture = cv2.VideoCapture(index)
        if not self._capture.isOpened():
            raise SystemExit(f"Cannot open camera {index}")
        self._flip = flip
        self._frame = None
        self._captured_at = 0.0
        self._ended = False
        self._stopping = False
        self._new_frame = threading.Condition()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def fps(self):
        return self._capture.get(cv2.CAP_PROP_FPS) or 30

    def _run(self):
        while not self._stopping:
            ok, frame = self._capture.read()
            captured_at = time.monotonic()
            if ok and self._flip is not None:
                frame = cv2.flip(frame, self._flip)
            with self._new_frame:
                if not ok:
                    self._ended = True
                    self._new_frame.notify_all()
                    return
                self._frame, self._captured_at = frame, captured_at
                self._new_frame.notify_all()

    def read(self, newer_than=0.0, timeout=5.0):
        """Newest (frame, captured_at) taken after `newer_than`, or None at end.

        Times are time.monotonic(). Blocks until such a frame arrives.
        """
        with self._new_frame:
            got = self._new_frame.wait_for(
                lambda: self._ended or self._captured_at > newer_than, timeout
            )
            if not got or self._captured_at <= newer_than:
                return None  # camera stopped, or no frame within timeout
            return self._frame, self._captured_at

    def close(self):
        # Stop the reader before releasing: releasing mid-read can crash cv2.
        self._stopping = True
        self._thread.join(timeout=2)
        self._capture.release()
