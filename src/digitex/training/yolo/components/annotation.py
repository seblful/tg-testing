import os
from urllib.parse import unquote

from tqdm import tqdm

from digitex.core.processors.file import FileProcessor


class Keypoint:
    def __init__(self, x: float | int, y: float | int, visible: int) -> None:
        assert visible in [0, 1], "Keypoint visibility parameter must be one of [0, 1]."

        self.x = x
        self.y = y
        self.visible = visible

    def clip(self, img_width: int, img_height: int) -> None:
        self.x = max(0, min(self.x, img_width - 1))
        self.y = max(0, min(self.y, img_height - 1))


class KeypointsObject:
    def __init__(
        self,
        class_idx: int,
        keypoints: list[Keypoint],
        num_keypoints: int,
        bbox_center: tuple[float | int] = None,
        bbox_width: float | int = None,
        bbox_height: float | int = None,
    ) -> None:
        self.class_idx = class_idx
        self.num_keypoints = num_keypoints
        self.keypoints = self.pad_keypoints(keypoints, num_keypoints)

        self.__bbox = None

        self.bbox_center = bbox_center
        self.bbox_width = bbox_width
        self.bbox_height = bbox_height

        self.bbox_offset = 1.05

        if None in (self.bbox_center, self.bbox_width, self.bbox_height):
            self.calc_props()

    @property
    def bbox(self) -> list[float | int]:
        if self.__bbox is None:
            x0 = self.bbox_center[0] - int(self.bbox_width / 2)
            y0 = self.bbox_center[1] - int(self.bbox_height / 2)
            x1 = self.bbox_center[0] + int(self.bbox_width / 2)
            y1 = self.bbox_center[1] + int(self.bbox_height / 2)
            self.__bbox = [x0, y0, x1, y1]

        return self.__bbox

    def pad_keypoints(
        self, keypoints: list[Keypoint], num_keypoints: int
    ) -> list[Keypoint]:
        keypoints = keypoints[:num_keypoints]

        if len(keypoints) < num_keypoints:
            keypoints = keypoints + [Keypoint(0, 0, 0)] * (
                num_keypoints - len(keypoints)
            )

        return keypoints

    def calc_props(self) -> None:
        if self.class_idx is None:
            self.bbox_center = (0, 0)
            self.bbox_width = 0
            self.bbox_height = 0

            return

        visible_kps = [kp for kp in self.keypoints if kp.visible == 1]
        if not visible_kps:
            self.bbox_center = (0, 0)
            self.bbox_width = 0
            self.bbox_height = 0
            return

        # Calculate min and max coordinates
        min_x = min(kp.x for kp in visible_kps)
        max_x = max(kp.x for kp in visible_kps)
        min_y = min(kp.y for kp in visible_kps)
        max_y = max(kp.y for kp in visible_kps)

        # Calculate
        if max_x <= 1 or max_y <= 1:
            self.bbox_center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
            self.bbox_width = min((max_x - min_x) * self.bbox_offset, 1.0)
            self.bbox_height = min((max_y - min_y) * self.bbox_offset, 1.0)
        else:
            self.bbox_center = int((min_x + max_x) / 2), int((min_y + max_y) / 2)
            self.bbox_width = int(max(max_x - min_x, 0))
            self.bbox_height = int(max(max_y - min_y, 0))

    def to_relative(
        self, img_width: int, img_height: int, clip: bool = False
    ) -> "KeypointsObject":
        # Convert coordinates
        rel_keypoints = []

        for rel_kp in self.keypoints:
            rel_x = int(rel_kp.x * img_width)
            rel_y = int(rel_kp.y * img_height)
            rel_kp = Keypoint(rel_x, rel_y, rel_kp.visible)

            if clip:
                rel_kp.clip(img_width, img_height)

            rel_keypoints.append(rel_kp)

        # Convert propertirs
        center_x = int(self.bbox_center[0] * img_width)
        center_y = int(self.bbox_center[1] * img_height)
        bbox_center = (center_x, center_y)
        bbox_width = int(self.bbox_width * img_width)
        bbox_height = int(self.bbox_height * img_height)

        return KeypointsObject(
            class_idx=self.class_idx,
            keypoints=rel_keypoints,
            num_keypoints=len(self.keypoints),
            bbox_center=bbox_center,
            bbox_width=bbox_width,
            bbox_height=bbox_height,
        )

    def to_absolute(self, img_width: int, img_height: int) -> "KeypointsObject":
        # Convert coordinates
        abs_keypoints = []

        for rel_kp in self.keypoints:
            abs_x = rel_kp.x / img_width
            abs_y = rel_kp.y / img_height
            abs_kp = Keypoint(abs_x, abs_y, rel_kp.visible)

            abs_keypoints.append(abs_kp)

        # Convert propertirs
        center_x = self.bbox_center[0] / img_width
        center_y = self.bbox_center[1] / img_height
        bbox_center = (center_x, center_y)
        bbox_width = self.bbox_width / img_width
        bbox_height = self.bbox_height / img_height

        return KeypointsObject(
            class_idx=self.class_idx,
            keypoints=abs_keypoints,
            num_keypoints=len(self.keypoints),
            bbox_center=bbox_center,
            bbox_width=bbox_width,
            bbox_height=bbox_height,
        )

    def get_vis_coords(self) -> list[tuple]:
        coords = []

        for kp in self.keypoints:
            if kp.visible == 1:
                coords.append((kp.x, kp.y))

        return coords

    def to_string(self) -> str:
        if self.class_idx is None:
            return ""

        # Get all props
        props = [
            self.class_idx,
            self.bbox_center[0],
            self.bbox_center[1],
            self.bbox_width,
            self.bbox_height,
        ]
        coords = [coord for kp in self.keypoints for coord in (kp.x, kp.y, kp.visible)]

        keypoints_str = " ".join(map(str, props + coords))

        return keypoints_str


class AnnotationCreator:
    def __init__(
        self,
        raw_dir: str,
        id2label: dict[int, str],
        label2id: dict[str, int],
        num_keypoints: int = 30,
    ) -> None:
        self.raw_dir = raw_dir
        self.data_json_path = os.path.join(raw_dir, "data.json")
        self.classes_path = os.path.join(raw_dir, "classes.txt")
        self.__labels_dir = None

        self.id2label = id2label
        self.label2id = label2id

        self.num_keypoints = num_keypoints

    @property
    def labels_dir(self) -> str:
        if self.__labels_dir is None:
            self.__labels_dir = os.path.join(self.raw_dir, "labels")
            os.mkdir(self.__labels_dir)

        return self.__labels_dir

    def get_keypoints_obj(self, task: dict) -> tuple:
        keypoints = []

        # Get points
        result = task["annotations"][0]["result"]

        for entry in result:
            value = entry["value"]
            x = value["x"] / 100
            y = value["y"] / 100
            label = value["keypointlabels"][0]
            keypoint = Keypoint(x, y, 1)
            keypoints.append(keypoint)

        if not keypoints:
            return KeypointsObject(
                class_idx=None, keypoints=[], num_keypoints=self.num_keypoints
            )

        return KeypointsObject(
            class_idx=self.label2id[label],
            keypoints=keypoints,
            num_keypoints=self.num_keypoints,
        )

    def create_keypoints(self) -> None:
        # Read json
        json_dict = FileProcessor.read_json(self.data_json_path)

        # Iterate through json dict
        for task in tqdm(json_dict, desc="Creating keypoints annotations"):
            image_name = unquote(os.path.basename(task["data"]["img"]))

            keypoints_obj = self.get_keypoints_obj(task)
            keypoints_str = keypoints_obj.to_string()

            # Write txt
            txt_name = os.path.splitext(image_name)[0] + ".txt"
            txt_path = os.path.join(self.labels_dir, txt_name)
            FileProcessor.write_txt(txt_path, lines=[keypoints_str])
