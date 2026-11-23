"""get-off-my-lawn: find a person, aim the pan/tilt rig at them, fire.

The loop is look -> decide -> act, strictly in turn:

    camera.read()        a frame taken AFTER the last action finished
    detector.detect()    where the targets are in that frame
    controller.update()  Move, Fire, or nothing
    rig.move/fire()      blocks until the board reports the action done

Nothing is detected while the rig is moving, so every decision is made from a
frame showing where the rig actually ended up. That is what stops overshoot.

Modules: config.py (all tunables), camera.py, detector.py, controller.py, rig.py.
"""

import sys
import time

import cv2

import config
from camera import Camera
from controller import Controller, Fire, Move
from detector import Detector
from rig import open_rig


def main():
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else config.CAMERA_INDEX

    rig = open_rig(config.SERIAL_PORT, config.BAUD, config.COMMAND_TIMEOUT)
    detector = Detector(
        config.MODEL, config.TARGET_CLASSES, config.MIN_CONFIDENCE, config.VERBOSE
    )
    controller = Controller()
    camera = Camera(camera_index, config.FLIP)
    writer = None  # created on the first frame, once its size is known

    # Start from a known position, so the controller's angles match the rig's.
    pan, tilt = controller.home()
    rig.move(pan, tilt)
    settled_at = time.monotonic()  # only frames captured after this are used

    try:
        while True:
            got = camera.read(newer_than=settled_at)
            if got is None:
                print("[camera]  no more frames")
                break
            frame, _ = got

            targets, annotated = detector.detect(frame)

            cv2.imshow("get-off-my-lawn", annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if writer is None:
                height, width = annotated.shape[:2]
                writer = cv2.VideoWriter(
                    "runs/track.mp4", cv2.VideoWriter_fourcc(*"mp4v"),
                    camera.fps, (width, height),
                )
            writer.write(annotated)

            action = controller.update(targets)
            if isinstance(action, Move):
                rig.move(action.pan, action.tilt)
            elif isinstance(action, Fire):
                rig.fire()  # the recoil shakes the rig too, so wait it out as well
            else:
                continue
            settled_at = time.monotonic()
    finally:
        camera.close()
        rig.close()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
