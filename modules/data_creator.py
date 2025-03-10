from typing import Dict

import os
from PIL import Image

from modules.processors import ImageProcessor
from modules.handlers import PDFHandler, ImageHandler, LabelHandler
from modules.predictors.segmentation import YOLO_SegmentationPredictor
from modules.predictors.detection import FAST_DetectionPredictor


class DataCreator:
    def __init__(self) -> None:
        self.image_processor = ImageProcessor()
        self.pdf_handler = PDFHandler()
        self.image_handler = ImageHandler()
        self.label_handler = LabelHandler()

    @staticmethod
    def _read_classes(classes_path: str) -> Dict[int, str]:
        with open(classes_path, 'r') as f:
            classes = [line.strip() for line in f.readlines()]
            return {i: cl for i, cl in enumerate(classes)}

    def _save_image(self,
                    *args,
                    train_dir: str,
                    image: Image.Image,
                    image_name: str,
                    num_saved: int,
                    num_images: int) -> int:

        # Create image path
        image_stem = os.path.splitext(image_name)[0]
        str_ids = "_".join([str(i) for i in args])
        image_path = os.path.join(
            train_dir, image_stem) + "_" + str_ids + ".jpg"

        if not os.path.exists(image_path):
            image.save(image_path, "JPEG")
            num_saved += 1
            print(f"{num_saved}/{num_images} images was saved.")

            image.close()

        return num_saved

    def extract_pages(self,
                      raw_dir: str,
                      train_dir: str,
                      scan_type: str,
                      num_images: int) -> None:

        # Pdf listdir
        pdf_listdir = [pdf for pdf in os.listdir(
            raw_dir) if pdf.endswith('pdf')]

        # Counter for saved images
        num_saved = 0

        while num_images != num_saved:
            rand_image, rand_image_name, rand_page_idx = self.pdf_handler.get_random_image(pdf_listdir=pdf_listdir,
                                                                                           pdf_dir=raw_dir)

            # Process image
            rand_image = self.image_processor.process(image=rand_image,
                                                      scan_type=scan_type)

            # Save image
            num_saved = self._save_image(rand_page_idx,
                                         train_dir=train_dir,
                                         image=rand_image,
                                         image_name=rand_image_name,
                                         num_saved=num_saved,
                                         num_images=num_images)

    def extract_questions(self,
                          page_raw_dir: str,
                          train_dir: str,
                          num_images: int) -> None:
        # Paths
        images_dir = os.path.join(page_raw_dir, "images")
        labels_dir = os.path.join(page_raw_dir, "labels")
        classes_path = os.path.join(page_raw_dir, "classes.txt")

        # Classes
        classes_dict = DataCreator._read_classes(classes_path)

        # Images listdir
        images_listdir = os.listdir(images_dir)

        # Counter for saved images
        num_saved = 0

        while num_images != num_saved:
            # Extract random image, points
            rand_image, rand_image_name = self.image_handler.get_random_image(images_listdir=images_listdir,
                                                                              images_dir=images_dir)

            rand_points_idx, rand_points = self.label_handler.get_points(image_name=rand_image_name,
                                                                         labels_dir=labels_dir,
                                                                         classes_dict=classes_dict,
                                                                         target_classes=["question"])
            rand_points = self.label_handler.points_to_abs_polygon(points=rand_points,
                                                                   image_width=rand_image.width,
                                                                   image_height=rand_image.height)

            # Crop image and add borders
            rand_image = self.image_handler.crop_image(image=rand_image,
                                                       points=rand_points)

            # Save image
            num_saved = self._save_image(rand_points_idx,
                                         train_dir=train_dir,
                                         image=rand_image,
                                         image_name=rand_image_name,
                                         num_saved=num_saved,
                                         num_images=num_images)

    def predict_questions(self,
                          raw_dir: str,
                          train_dir: str,
                          yolo_model_path: str,
                          scan_type: str,
                          num_images: int) -> None:

        # Load model
        yolo_page_predictor = YOLO_SegmentationPredictor(
            model_path=yolo_model_path)

        # Pdf listdir
        pdf_listdir = [pdf for pdf in os.listdir(
            raw_dir) if pdf.endswith('pdf')]

        # Counter for saved images
        num_saved = 0

        while num_images != num_saved:
            # Extract random image, points
            rand_image, rand_image_name, rand_page_idx = self.pdf_handler.get_random_image(pdf_listdir=pdf_listdir,
                                                                                           pdf_dir=raw_dir)
            rand_image = self.image_processor.process(image=rand_image,
                                                      scan_type=scan_type)

            pred_result = yolo_page_predictor(image=rand_image)
            points_dict = pred_result.id2polygons
            rand_points_idx, rand_points = self.label_handler._get_random_points(classes_dict=pred_result.id2label,
                                                                                 points_dict=points_dict,
                                                                                 target_classes=["question"])

            # Crop question image and add borders
            rand_image = self.image_handler.crop_image(image=rand_image,
                                                       points=rand_points)

            # Save image
            num_saved = self._save_image(rand_page_idx,
                                         rand_points_idx,
                                         train_dir=train_dir,
                                         image=rand_image,
                                         image_name=rand_image_name,
                                         num_saved=num_saved,
                                         num_images=num_images)

    def extract_parts(self,
                      question_raw_dir: str,
                      train_dir: str,
                      num_images: int,
                      target_classes: list[str] = ["answer", "number", "option", "question", "spec"]) -> None:
        # Paths
        images_dir = os.path.join(question_raw_dir, "images")
        labels_dir = os.path.join(question_raw_dir, "labels")
        classes_path = os.path.join(question_raw_dir, "classes.txt")

        # Classes
        classes_dict = DataCreator._read_classes(classes_path)

        # Images listdir
        images_listdir = os.listdir(images_dir)

        # Counter for saved images
        num_saved = 0

        while num_images != num_saved:
            # Extract random image, points
            rand_image, rand_image_name = self.image_handler.get_random_image(images_listdir=images_listdir,
                                                                              images_dir=images_dir)

            rand_points_idx, rand_points = self.label_handler.get_points(image_name=rand_image_name,
                                                                         labels_dir=labels_dir,
                                                                         classes_dict=classes_dict,
                                                                         target_classes=target_classes)
            if not rand_points:
                continue

            rand_points = self.label_handler.points_to_abs_polygon(points=rand_points,
                                                                   image_width=rand_image.width,
                                                                   image_height=rand_image.height)

            # Crop image
            rand_image = self.image_handler.crop_image(image=rand_image,
                                                       points=rand_points,
                                                       offset=0.0)

            # Save image
            num_saved = self._save_image(rand_points_idx,
                                         train_dir=train_dir,
                                         image=rand_image,
                                         image_name=rand_image_name,
                                         num_saved=num_saved,
                                         num_images=num_images)

    def predict_parts(self,
                      raw_dir: str,
                      train_dir: str,
                      yolo_page_model_path: str,
                      yolo_question_model_path: str,
                      scan_type: str,
                      num_images: int,
                      target_classes: list[str] = ["answer", "number", "option", "question", "spec"]) -> None:
        # Load models
        yolo_page_predictor = YOLO_SegmentationPredictor(yolo_page_model_path)
        yolo_question_predictor = YOLO_SegmentationPredictor(
            yolo_question_model_path)

        # Pdf listdir
        pdf_listdir = [pdf for pdf in os.listdir(
            raw_dir) if pdf.endswith('pdf')]

        # Counter for saved images
        num_saved = 0

        while num_images != num_saved:
            # Extract random image, points
            page_rand_image, rand_image_name, rand_page_idx = self.pdf_handler.get_random_image(pdf_listdir=pdf_listdir,
                                                                                                pdf_dir=raw_dir)
            page_rand_image = self.image_processor.process(image=page_rand_image,
                                                           scan_type=scan_type)

            # Predict page
            page_pred_result = yolo_page_predictor(page_rand_image)
            page_points_dict = page_pred_result.id2polygons
            question_rand_points_idx, question_rand_points = self.label_handler._get_random_points(classes_dict=page_pred_result.id2label,
                                                                                                   points_dict=page_points_dict,
                                                                                                   target_classes=["question"])

            # Crop question image and add borders
            question_rand_image = self.image_handler.crop_image(image=page_rand_image,
                                                                points=question_rand_points)

            # Predict question
            question_pred_result = yolo_question_predictor(question_rand_image)
            question_points_dict = question_pred_result.id2polygons
            part_rand_points_idx, part_rand_points = self.label_handler._get_random_points(classes_dict=question_pred_result.id2label,
                                                                                           points_dict=question_points_dict,
                                                                                           target_classes=target_classes)

            if not part_rand_points:
                continue

            # Crop part image
            part_rand_image = self.image_handler.crop_image(image=question_rand_image,
                                                            points=part_rand_points,
                                                            offset=0.0)

            # Save image
            num_saved = self._save_image(rand_page_idx,
                                         question_rand_points_idx,
                                         part_rand_points_idx,
                                         train_dir=train_dir,
                                         image=part_rand_image,
                                         image_name=rand_image_name,
                                         num_saved=num_saved,
                                         num_images=num_images)

    def extract_words(self,
                      parts_raw_dir: str,
                      train_dir: str,
                      num_images: int) -> None:
        # Paths
        images_dir = os.path.join(parts_raw_dir, "images")
        labels_dir = os.path.join(parts_raw_dir, "labels")
        classes_path = os.path.join(parts_raw_dir, "classes.txt")

        # Classes
        classes_dict = DataCreator._read_classes(classes_path)
        target_classes = ["text"]

        # Images listdir
        images_listdir = os.listdir(images_dir)

        # Counter for saved images
        num_saved = 0

        while num_images != num_saved:
            # Extract random image, points
            rand_image, rand_image_name = self.image_handler.get_random_image(images_listdir=images_listdir,
                                                                              images_dir=images_dir)

            rand_points_idx, rand_points = self.label_handler.get_points(image_name=rand_image_name,
                                                                         labels_dir=labels_dir,
                                                                         classes_dict=classes_dict,
                                                                         target_classes=target_classes)
            rand_points = self.label_handler.points_to_abs_polygon(points=rand_points,
                                                                   image_width=rand_image.width,
                                                                   image_height=rand_image.height)

            # Crop image
            rand_image = self.image_handler.crop_image(image=rand_image,
                                                       points=rand_points,
                                                       offset=0.0)

            # Save image
            num_saved = self._save_image(rand_points_idx,
                                         train_dir=train_dir,
                                         image=rand_image,
                                         image_name=rand_image_name,
                                         num_saved=num_saved,
                                         num_images=num_images)

    def predict_words(self,
                      raw_dir: str,
                      train_dir: str,
                      yolo_page_model_path: str,
                      yolo_question_model_path: str,
                      fast_word_model_path: str,
                      scan_type: str,
                      num_images: int) -> None:
        # Load models
        yolo_page_predictor = YOLO_SegmentationPredictor(yolo_page_model_path)
        yolo_question_predictor = YOLO_SegmentationPredictor(
            yolo_question_model_path)
        fast_word_predictor = FAST_DetectionPredictor(fast_word_model_path)

        # Pdf listdir
        pdf_listdir = [pdf for pdf in os.listdir(
            raw_dir) if pdf.endswith('pdf')]

        # Classes
        parts_target_classes = [
            "answer", "number", "option", "question", "spec"]

        # Counter for saved images
        num_saved = 0

        while num_images != num_saved:
            # Extract random image, points
            page_rand_image, rand_image_name, rand_page_idx = self.pdf_handler.get_random_image(pdf_listdir=pdf_listdir,
                                                                                                pdf_dir=raw_dir)
            page_rand_image = self.image_processor.process(image=page_rand_image,
                                                           scan_type=scan_type)

            # Predict page
            page_pred_result = yolo_page_predictor(page_rand_image)
            page_points_dict = page_pred_result.id2polygons
            question_rand_points_idx, question_rand_points = self.label_handler._get_random_points(classes_dict=page_pred_result.id2label,
                                                                                                   points_dict=page_points_dict,
                                                                                                   target_classes=["question"])

            # Crop question image and add borders
            question_rand_image = self.image_handler.crop_image(image=page_rand_image,
                                                                points=question_rand_points)

            # Predict question
            question_pred_result = yolo_question_predictor(question_rand_image)
            question_points_dict = question_pred_result.id2polygons
            part_rand_points_idx, part_rand_points = self.label_handler._get_random_points(classes_dict=question_pred_result.id2label,
                                                                                           points_dict=question_points_dict,
                                                                                           target_classes=parts_target_classes)
            # Crop part image
            part_rand_image = self.image_handler.crop_image(image=question_rand_image,
                                                            points=part_rand_points,
                                                            offset=0.0)

            # Predict word
            word_pred_result = fast_word_predictor(part_rand_image)
            word_points_dict = word_pred_result.id2polygons
            word_rand_points_idx, word_rand_points = self.label_handler._get_random_points(classes_dict=word_pred_result.id2label,
                                                                                           points_dict=word_points_dict,
                                                                                           target_classes=["text"])

            # Crop word image
            word_rand_image = self.image_handler.crop_image(image=part_rand_image,
                                                            points=word_rand_points)

            # Save image
            num_saved = self._save_image(rand_page_idx,
                                         question_rand_points_idx,
                                         part_rand_points_idx,
                                         word_rand_points_idx,
                                         train_dir=train_dir,
                                         image=word_rand_image,
                                         image_name=rand_image_name,
                                         num_saved=num_saved,
                                         num_images=num_images)
