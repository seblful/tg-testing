import json
import yaml

from PIL import Image

import numpy as np
import cv2

import doxapy


class ImageProcessor:
    def __init__(self) -> None:
        # Scan
        self.scan_types = ["bw", "gray", "color"]

        # Blue remove range
        self.lower_blue = np.array([70, 30, 30])
        self.upper_blue = np.array([130, 255, 255])

        # Binarization
        self.bin_params = {"window": 30, "k": 0.16}

    def remove_color(self,
                     img: np.ndarray) -> np.ndarray:
        # Convert to HSV color space
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Create a mask for blue color
        mask = cv2.inRange(hsv, self.lower_blue, self.upper_blue)

        # Dilate the mask to cover entire pen marks
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)

        # Inpaint the masked region
        img = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)

        return img

    def illuminate_image(self,
                         img: np.array,
                         alpha: float = 1.1,
                         beta=1) -> None:

        # Change luminance
        img = cv2.convertScaleAbs(img,
                                  alpha=alpha,
                                  beta=beta)

        return img

    def binarize_image(self,
                       img: np.ndarray) -> np.ndarray:
        # Convert image to gray
        if len(img.shape) != 2:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # Create empty binary image
        bin_img = np.empty(gray.shape, gray.dtype)

        # Convert the image to binary
        wan = doxapy.Binarization(doxapy.Binarization.Algorithms.WAN)
        wan.initialize(gray)
        wan.to_binary(bin_img, self.bin_params)

        # Convert image back to 3d
        img = cv2.cvtColor(bin_img, cv2.COLOR_GRAY2BGR)

        return img

    def resize_image(self,
                     img: np.ndarray,
                     max_height: int = 2000) -> np.ndarray:

        height, width = img.shape[:2]

        # Check if the height is greater than the specified max height
        if height > max_height:
            # Calculate the aspect ratio
            aspect_ratio = width / height
            # Calculate the new dimensions
            new_height = max_height
            new_width = int(new_height * aspect_ratio)

            # Resize the image
            img = cv2.resize(
                img, (new_width, new_height), interpolation=cv2.INTER_AREA)

        return img

    def process(self,
                image: Image.Image,
                scan_type: str,
                resize: bool = False,
                remove_ink: bool = False,
                illuminate: bool = False,
                binarize: bool = False) -> Image.Image:
        # Check scan type
        assert scan_type in self.scan_types, f"Scan type should be in one of {
            str(self.scan_types)}"

        # Convert image to array
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Resize image
        if resize is True:
            img = self.resize_image(img)

        # Remove ink
        if remove_ink is True:
            img = self.remove_color(img)

        if illuminate is True:
            img = self.illuminate_image(img)

        # Binarize image
        if binarize is True and scan_type != "bw":
            img = self.binarize_image(img)

        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


class FileProcessor:
    @staticmethod
    def read_txt(txt_path) -> list[str]:
        with open(txt_path, "r", encoding="utf-8") as txt_file:
            content = txt_file.readlines()

        return content

    @staticmethod
    def write_txt(txt_path: str,
                  lines: list[str]) -> None:
        with open(txt_path, 'w', encoding="utf-8") as txt_file:
            txt_file.writelines(lines)

        return None

    @staticmethod
    def read_json(json_path) -> dict:
        try:
            with open(json_path, "r", encoding="utf-8") as json_file:
                json_dict = json.load(json_file)

        except FileNotFoundError:
            json_dict = {}

        return json_dict

    @staticmethod
    def write_json(json_dict: dict,
                   json_path: str,
                   indent: int = 4) -> None:
        with open(json_path, 'w', encoding="utf-8") as json_file:
            json.dump(json_dict, json_file,
                      indent=indent,
                      ensure_ascii=False)

        return None

    @staticmethod
    def write_yaml(yaml_path: str, data: dict, comment: str = None) -> None:
        with open(yaml_path, 'w', encoding="utf-8") as yaml_file:
            if comment:
                yaml_file.write(comment)
            yaml.dump(data, yaml_file,
                      default_flow_style=False,
                      allow_unicode=True)

        return None
