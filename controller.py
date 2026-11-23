"""Aiming decisions: which target to chase, where to point, when to fire.

Pure logic -- no camera, model or serial port -- so it can be reasoned about
(and tested) on its own. main.py feeds it the detections from each settled
frame and carries out whatever it returns.
"""

import time
from typing import NamedTuple

import config


class Move(NamedTuple):
    pan: int
    tilt: int


class Fire(NamedTuple):
    pass


def clamp(value, limits):
    low, high = limits
    return min(max(value, low), high)


class Controller:
    def __init__(self):
        self.pan = float(config.PAN_HOME)
        self.tilt = float(config.TILT_HOME)
        self._locked = None    # track id currently being chased
        self._missing = 0      # consecutive frames the locked target was absent
        self._centered = 0     # consecutive frames the target has been centred
        self._fired_at = None  # time.monotonic() of the last shot

    def home(self):
        return Move(int(round(self.pan)), int(round(self.tilt)))

    def update(self, targets):
        """Decide the next action from one frame's {track id: Box}.

        Returns a Move, a Fire, or None to just keep watching. The frame must
        have been taken after the previous action finished; the caller ensures
        that, so the offset measured here is the true remaining error.
        """
        target_id = self._pick_target(targets)
        if target_id is None:
            return None

        box = targets[target_id]
        error_x, error_y = box.x - 0.5, box.y - 0.5

        if abs(error_x) > config.DEADZONE or abs(error_y) > config.DEADZONE:
            self._centered = 0
            return self._steer(error_x, error_y)

        self._centered += 1
        if self._centered < config.CENTERED_FRAMES:
            return None
        now = time.monotonic()
        if self._fired_at is not None and now - self._fired_at < config.COOLDOWN_SECONDS:
            return None

        self._fired_at = now
        print(f"[centred] id {target_id} at ({box.x:.3f}, {box.y:.3f})")
        return Fire()

    def _steer(self, error_x, error_y):
        """Move a fraction (GAIN) of the way toward centring the target.

        error_x/error_y are the target's offset from the centre of frame, in
        the range -0.5..0.5; multiplied by the field of view they become an
        angle. Because the camera moves with the rig, the next settled frame
        measures what is left, so repeated corrections converge.
        """
        pan_delta = clamp(
            error_x * config.FOV_PAN_DEG * config.GAIN * config.PAN_SIGN,
            (-config.MAX_STEP, config.MAX_STEP),
        )
        tilt_delta = clamp(
            error_y * config.FOV_TILT_DEG * config.GAIN * config.TILT_SIGN,
            (-config.MAX_STEP, config.MAX_STEP),
        )
        self.pan = clamp(self.pan + pan_delta, config.PAN_LIMITS)
        self.tilt = clamp(self.tilt + tilt_delta, config.TILT_LIMITS)
        return Move(int(round(self.pan)), int(round(self.tilt)))

    def _pick_target(self, targets):
        """Stay locked on one target; prefer the largest (nearest) when re-locking.

        Without a lock the rig oscillates between two people instead of
        centring either one.
        """
        if self._locked in targets:
            self._missing = 0
            return self._locked

        self._missing += 1
        if self._locked is not None and self._missing < config.LOST_FRAMES:
            return None  # brief dropout; hold position rather than switching

        self._locked = max(
            targets, key=lambda i: targets[i].width * targets[i].height, default=None
        )
        self._missing = 0
        self._centered = 0
        return self._locked
