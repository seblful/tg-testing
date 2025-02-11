import os
import random
from PIL import Image

import numpy as np
import cv2

import supervision as sv

import albumentations as A

from tqdm import tqdm

from modules.handlers import ImageHandler, LabelHandler


class Augmenter:
    def __init__(self,
                 dataset_dir) -> None:
        # Paths
        self.dataset_dir = dataset_dir
        self.train_dir = os.path.join(self.dataset_dir, 'train')

        self.__transform = None

        self.label_types = ["polygon", "obb"]

        self.preprocess_funcs = {"polygon": self.point_to_polygon,
                                 "obb": self.xyxyxyxy_to_polygon}
        self.postprocess_funcs = {"polygon": self.polygon_to_point,
                                  "obb": self.polygon_to_xyxyxyxy}

        self.img_ext = ".jpg"
        self.anns_ext = ".txt"

        # Handlers
        self.image_handler = ImageHandler()
        self.label_handler = LabelHandler()

    @property
    def transform(self) -> A.Compose:
        if self.__transform is None:
            self.__transform = A.Compose([
                A.Affine(scale=0.9, p=0.7),
                A.Perspective(scale=(0.01, 0.05), p=0.5),
                A.CropAndPad(percent=(-0.04, 0.04), p=0.5),
                A.CoarseDropout(p=0.2),
                A.ISONoise(color_shift=(0.01, 0.05), p=0.2),
                A.GaussianBlur(blur_limit=(0, 3), p=0.5),
                A.RandomBrightnessContrast(brightness_limit=(-0.3, 0.3),
                                           contrast_limit=(-0.3, 0.3),
                                           p=0.5),
                A.HueSaturationValue(hue_shift_limit=10,
                                     sat_shift_limit=20,
                                     val_shift_limit=10,
                                     p=0.5),
                A.RandomGamma(gamma_limit=(50, 200), p=0.5)
            ])

        return self.__transform

    def save_anns(self,
                  name: str,
                  increment: int,
                  points_dict: dict[int, list]) -> None:
        filename = f"{name}_aug_{increment}{self.anns_ext}"
        filepath = os.path.join(self.train_dir, filename)

        # Write each class and anns to txt
        with open(filepath, 'w') as file:
            for class_idx, points in points_dict.items():
                for point in points:
                    point = [str(pts) for pts in point]
                    pts = " ".join(point)
                    line = f"{class_idx} {pts}\n"
                    file.write(line)

    def save_image(self,
                   name: str,
                   img: np.ndarray) -> int:
        # Create filename and filepath of new image
        increment = 1
        filename = f"{name}_aug_{increment}{self.img_ext}"
        while os.path.exists(filename):
            filename = f"{name}_aug_{increment}{self.img_ext}"
            increment += 1
        filepath = os.path.join(self.train_dir, filename)

        # Save image
        image = Image.fromarray(img)
        image.save(filepath)

        return increment

    def save(self,
             img_name,
             img: np.ndarray,
             points_dict: dict[int, list]) -> None:
        name = os.path.splitext(img_name)[0]

        increment = self.save_image(name, img)

        if points_dict is not None:
            self.save_anns(name, increment, points_dict)

    def get_random_img(self,
                       images_listdir: list[str]) -> tuple[np.ndarray, str]:
        img_name = random.choice(images_listdir)
        img_path = os.path.join(self.train_dir, img_name)
        image = Image.open(img_path)
        img = np.array(image)

        return img_name, img

    def xyxyxyxy_to_polygon(self,
                            xyxyxyxy: list[float],
                            img_width: int,
                            img_height: int) -> np.ndarray:
        xyxyxyxy = [xyxyxyxy[i] * (img_width if i % 2 == 0 else img_height)
                    for i in range(len(xyxyxyxy))]
        xyxyxyxy = np.array(xyxyxyxy)
        polygon = xyxyxyxy.reshape((-1, 2))

        return polygon

    def point_to_polygon(self,
                         point: list[float],
                         img_width: int,
                         img_height: int) -> np.ndarray:
        polygon = list(zip(point[::2], point[1::2]))
        polygon = np.array(polygon) * np.array((img_width, img_height))

        return polygon

    def polygon_to_xyxyxyxy(self,
                            polygon: np.ndarray,
                            img_width: int,
                            img_height: int) -> list[float]:
        xyxyxyxy = polygon / np.array((img_width, img_height))
        xyxyxyxy = xyxyxyxy.flatten().tolist()

        assert len(xyxyxyxy) == 8, "Length of xyxyxyxy must be equal 8."

        return xyxyxyxy

    def polygon_to_point(self,
                         polygon: np.ndarray,
                         img_width: int,
                         img_height: int) -> list[float]:
        point = polygon / np.array((img_width, img_height))
        point = point.flatten().tolist()

        return point

    def create_masks(self,
                     img_name: str,
                     img_width: int,
                     img_height: int,
                     anns_type: str) -> None | dict[int, list]:
        anns_name = os.path.splitext(img_name)[0] + '.txt'
        anns_path = os.path.join(self.train_dir, anns_name)

        if not os.path.exists(anns_path):
            return None

        preprocess_func = self.preprocess_funcs[anns_type]

        points_dict = self.label_handler._read_points(anns_path)
        masks_dict = {key: [] for key in points_dict.keys()}

        # Iterate through points, preprocess and convert to mask
        for class_idx, points in points_dict.items():
            for point in points:
                polygon = preprocess_func(point, img_width, img_height)

                # Convert polygon to mask
                mask = sv.polygon_to_mask(polygon, (img_width, img_height))

                masks_dict[class_idx].append(mask)

        return masks_dict

    def create_anns(self,
                    masks_dict: dict[int, list],
                    img_width: int,
                    img_height: int,
                    anns_type: str) -> None | dict[int, list]:
        if masks_dict is None:
            return None

        postprocess_func = self.postprocess_funcs[anns_type]

        points_dict = {key: [] for key in masks_dict.keys()}

        # Iterate through masks and convert to anns
        for class_idx, masks in masks_dict.items():
            for mask in masks:
                polygon = sv.mask_to_polygons(mask)
                anns = postprocess_func(polygon, img_width, img_height)
                points_dict[class_idx].append(anns)

        return points_dict

    def augment_image(self,
                      img: np.ndarray,
                      masks_dict: dict[int, list] = None) -> tuple[np.ndarray, None] | tuple[np.ndarray, dict[int, list]]:
        # Case if no masks_dict
        if masks_dict is None:
            transf = self.transform(image=img)
            transf_img = transf['image']

            return (transf_img, None)

        # Obtain masks
        masks = []
        for v in masks_dict.values():
            masks.extend(v)

        # Transform
        transf = self.transform(image=img, masks=masks)
        transf_img = transf['image']
        transf_masks = transf['masks']

        # Create transf_masks_dict
        transf_masks_dict = {key: [] for key in masks_dict.keys()}
        i = 0
        for class_idx, masks in masks_dict.items():
            for _ in range(len(masks)):
                transf_masks_dict[class_idx].append(transf_masks[i])
                i += 1

        return transf_img, transf_masks_dict

    def augment(self,
                anns_type: str,
                num_images: int) -> None:
        assert anns_type in self.label_types, f"label_type must be one of {self.label_types}."

        images_listdir = [i for i in os.listdir(
            self.train_dir) if i.endswith(".jpg")]

        for _ in tqdm(range(num_images), desc="Augmenting images"):
            img_name, img = self.get_random_img(images_listdir)
            img_height, img_width, _ = img.shape

            masks_dict = self.create_masks(
                img_name, img_width, img_height, anns_type)
            transf_img, transf_masks_dict = self.augment_image(img, masks_dict)
            transf_points_dict = self.create_anns(
                transf_masks_dict, img_width, img_height, anns_type)
            self.save(img_name, transf_img, transf_points_dict)
