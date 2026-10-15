import sys

from ultralytics import YOLO

# cv2 camera index. On this Mac, 1 is the built-in FaceTime camera; on Linux
# (the Pi) the attached camera is normally 0. Override: `python main.py 0`
CAMERA_INDEX = 1

camera = int(sys.argv[1]) if len(sys.argv) > 1 else CAMERA_INDEX

model = YOLO("yolo26n.pt")

results = model.track(source=camera, show=True, stream=True, save=True)
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
