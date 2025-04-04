from typing import List, Tuple, Dict

import os
import random

from PIL import Image

import numpy as np
import cv2
import pypdfium2 as pdfium


class PDFHandler:
    @staticmethod
    def create_pdf(images: List[Image.Image], output_path: str) -> None:
        pdf = pdfium.PdfDocument.new()

        for image in images:
            bitmap = pdfium.PdfBitmap.from_pil(image)
            pdf_image = pdfium.PdfImage.new(pdf)
            pdf_image.set_bitmap(bitmap)

            width, height = pdf_image.get_size()
            matrix = pdfium.PdfMatrix().scale(width, height)
            pdf_image.set_matrix(matrix)

            page = pdf.new_page(width, height)
            page.insert_obj(pdf_image)
            page.gen_content()

            bitmap.close()

        pdf.save(output_path, version=17)

    @staticmethod
    def open_pdf(pdf_path: str):
        pdf_obj = pdfium.PdfDocument(pdf_path)

        return pdf_obj

    def get_page_image(self,
                       page: pdfium.PdfPage,
                       scale: int = 3) -> Image.Image:
        bitmap = page.render(scale=scale, rotation=0)
        image = bitmap.to_pil()
        return image if image.mode == 'RGB' else image.convert('RGB')

    def get_random_image(self,
                         pdf_listdir: List[str],
                         pdf_dir: str) -> Tuple[str, int, Image.Image]:
        # Take random pdf
        rand_pdf_name = random.choice(pdf_listdir)
        rand_pdf_path = os.path.join(pdf_dir, rand_pdf_name)
        rand_pdf_obj = self.open_pdf(rand_pdf_path)

        # Take random pdf page and image
        rand_page_idx = random.randint(0, len(rand_pdf_obj) - 1)
        rand_page = rand_pdf_obj[rand_page_idx]

        # Get random image and name
        rand_image = self.get_page_image(page=rand_page)
        rand_image_name = os.path.splitext(rand_pdf_name)[0] + ".jpg"

        # Close pdf file-object
        rand_pdf_obj.close()

        return rand_image, rand_image_name, rand_page_idx


class ImageHandler:
    @staticmethod
    def resize_image(image: Image.Image,
                     target_width: int,
                     target_height: int) -> Image.Image:
        image_width, image_height = image.size

        # Calculate scaling factor while maintaining aspect ratio
        width_ratio = target_width / image_width
        height_ratio = target_height / image_height
        scale_factor = min(width_ratio, height_ratio)

        # Resize the image
        new_width = int(image_width * scale_factor)
        new_height = int(image_height * scale_factor)
        resized_image = image.resize(
            (new_width, new_height), Image.LANCZOS)

        return resized_image

    @staticmethod
    def crop_image(image: Image.Image,
                   points: List[float],
                   offset: float = 0.025) -> Image.Image:
        img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        height, width = img.shape[:2]

        pts = np.array(points)
        rect = cv2.boundingRect(pts)
        x, y, w, h = rect
        img = img[y:y+h, x:x+w].copy()

        pts = pts - pts.min(axis=0)
        mask = np.zeros(img.shape[:2], np.uint8)
        cv2.drawContours(mask, [pts], -1, (255, 255, 255), -1, cv2.LINE_AA)

        result = cv2.bitwise_and(img, img, mask=mask)
        bg = np.ones_like(img, np.uint8)*255
        cv2.bitwise_not(bg, bg, mask=mask)
        result = bg + result

        border = int(height*offset)
        result = cv2.copyMakeBorder(result, border, border, border, border,
                                    cv2.BORDER_CONSTANT, value=[255, 255, 255])

        return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))

    def get_random_image(self,
                         images_listdir: List[str],
                         images_dir: str) -> Tuple[Image.Image, str]:
        rand_image_name = random.choice(images_listdir)
        rand_image_path = os.path.join(images_dir, rand_image_name)
        rand_image = Image.open(rand_image_path)

        return rand_image, rand_image_name


class LabelHandler:
    @staticmethod
    def _read_points(label_path: str) -> Dict[int, list[list[float]]]:
        points_dict = dict()
        with open(label_path, "r") as f:
            for line in f:
                # Get points
                data = line.strip().split()
                class_idx = int(data[0])
                points = [float(point) for point in data[1:]]

                # Append points to the list in dict
                if class_idx not in points_dict:
                    points_dict[class_idx] = []
                points_dict[class_idx].append(points)

        return points_dict

    @staticmethod
    def _get_random_points(classes_dict: Dict[int, str],
                           points_dict: Dict[int, list],
                           target_classes: List[str]) -> Tuple[int, List[float]]:
        # Create subset of dict with target classes
        points_dict = {k: points_dict[k]
                       for k in points_dict if classes_dict[k] in target_classes}

        if not points_dict:
            return -1, []

        # Get random label
        rand_class_idx = random.choice(list(points_dict.keys()))

        # Get random points
        rand_points_idx = random.randint(
            0, len(points_dict[rand_class_idx])-1)
        rand_points = points_dict[rand_class_idx][rand_points_idx]

        return rand_points_idx, rand_points

    @staticmethod
    def get_random_label(image_name: str,
                         labels_dir: str) -> str:

        label_name = os.path.splitext(image_name)[0] + '.txt'
        label_path = os.path.join(labels_dir, label_name)

        # Return None if label_path doesn't exist
        if not os.path.exists(label_path):
            return (None, None)

        return label_name, label_path

    @staticmethod
    def points_to_abs_polygon(points: list[float],
                              image_width: int,
                              image_height: int) -> list[tuple[float]]:
        points = list(zip(points[::2], points[1::2]))
        points = [(int(x * image_width), int(y * image_height))
                  for x, y in points]

        return points

    def get_points(self,
                   image_name: str,
                   labels_dir: str,
                   classes_dict: Dict[int, str],
                   target_classes: List[str]) -> Tuple[int, List[float]]:
        _, rand_label_path = self.get_random_label(image_name=image_name,
                                                   labels_dir=labels_dir)
        points_dict = self._read_points(rand_label_path)

        rand_points_idx, rand_points = self._get_random_points(classes_dict=classes_dict,
                                                               points_dict=points_dict,
                                                               target_classes=target_classes)

        return rand_points_idx, rand_points
