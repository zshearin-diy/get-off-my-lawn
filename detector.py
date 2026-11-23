"""YOLO detection and tracking, reduced to the boxes the rig cares about."""

from typing import NamedTuple

from ultralytics import YOLO


class Box(NamedTuple):
    """A detection in normalised frame coordinates (0..1, origin top-left)."""

    x: float  # centre
    y: float  # centre
    width: float
    height: float


class Detector:
    def __init__(self, weights, target_classes, min_confidence, verbose=False):
        self._model = YOLO(weights)
        self._min_confidence = min_confidence
        self._verbose = verbose
        # Filter at the model: the tracker then only assigns and maintains IDs
        # for classes we care about, instead of tracking every chair in view.
        self._class_ids = sorted(
            i for i, name in self._model.names.items() if name in target_classes
        )
        if not self._class_ids:
            raise SystemExit(f"No such classes in this model: {sorted(target_classes)}")

    def detect(self, frame):
        """Return ({track id: Box} for confident targets, annotated frame)."""
        # persist=True keeps tracker IDs across calls, since frames arrive one at a time
        result = self._model.track(
            frame, classes=self._class_ids, persist=True, verbose=False
        )[0]

        targets = {}
        for box in result.boxes:
            if box.id is None:  # the tracker has not assigned this detection an ID yet
                continue
            track_id = int(box.id)
            x, y, w, h = (float(v) for v in box.xywhn[0])  # xywhn is (1, 4)
            if self._verbose:
                name = result.names[int(box.cls)]
                print(
                    f"[detect]  id {track_id} {name} conf {float(box.conf):.2f} "
                    f"centre ({x:.3f}, {y:.3f}) size {w:.3f}x{h:.3f}"
                )
            if float(box.conf) >= self._min_confidence:
                targets[track_id] = Box(x, y, w, h)

        return targets, result.plot()
