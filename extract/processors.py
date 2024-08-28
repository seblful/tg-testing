import os
from PIL import Image

import numpy as np
import cv2
import pypdfium2 as pdfium

from marker.models import load_all_models
from marker.convert import convert_single_pdf
from marker.output import save_markdown


class ImageProcessor:
    def __init__(self,
                 alpha: int,
                 beta: int,
                 remove_ink: bool,
                 binarize: bool,
                 blur: bool) -> None:
        # Parameters
        self.alpha = alpha
        self.beta = beta
        self.remove_ink = remove_ink
        self.binarize = binarize
        self.blur = blur


class PDFProcessor:
    def __init__(self,
                 raw_dir: str,
                 input_dir: str,
                 output_dir: str,
                 alpha: int = 3,
                 beta: int = 15,
                 remove_ink: bool = True,
                 binarize: bool = False,
                 blur: bool = False) -> None:
        # Paths
        self.raw_dir = raw_dir
        self.input_dir = input_dir
        self.output_dir = output_dir

        # Image processor
        self.image_processor = ImageProcessor(alpha=alpha,
                                              beta=beta,
                                              remove_ink=remove_ink,
                                              binarize=binarize,
                                              blur=blur)

        # Model, langs
        self.model_lst = load_all_models()
        self.langs = ["ru", "en"]

    @staticmethod
    def insert_image(pdf: pdfium.PdfDocument,
                     image: Image.Image,
                     width: float,
                     height: float) -> None:
        # Insert image to pdf image
        pdf_image = pdfium.PdfImage.new(pdf)
        bitmap = pdfium.PdfBitmap.from_pil(image)
        image.close()
        pdf_image.set_bitmap(bitmap)
        bitmap.close()

        # Set matrix
        pdf_image.set_matrix(
            pdfium.PdfMatrix().scale(width, height))

        # Create page and insert pdf image
        page = pdf.new_page(width, height)
        page.insert_obj(pdf_image)
        page.gen_content()

        # Close
        pdf_image.close()
        page.close()

    def preprocess_pdf(self) -> None:
        for pdf_name in os.listdir(self.raw_dir):
            # Check if it was preprocessed before
            if not os.path.exists(os.path.join(self.input_dir, pdf_name)):
                # Open pdf
                full_pdf_path = os.path.join(self.raw_dir, pdf_name)
                raw_pdf = pdfium.PdfDocument(full_pdf_path)
                version = raw_pdf.get_version()

                # Create new pdf
                input_pdf = pdfium.PdfDocument.new()

                # Iterate
                for page in raw_pdf:
                    # Get width and height of the page
                    width, height = page.get_size()

                    # Retrieve image
                    bitmap = page.render(scale=3,
                                         rotation=0)
                    image = bitmap.to_pil()

                    # Clean image
                    image = self.image_processor.clean_image(image=image,
                                                             remove_ink=self.remove_ink,
                                                             binarize=self.binarize,
                                                             blur=self.blur)

                    PDFProcessor.insert_image(pdf=input_pdf,
                                              image=image,
                                              width=width,
                                              height=height)

                # Save pdf
                input_pdf.save(dest=os.path.join(self.input_dir, pdf_name),
                               version=version)

                # Close pdfs
                raw_pdf.close()
                input_pdf.close()

    def convert_to_md(self) -> None:
        for pdf_name in os.listdir(self.input_dir):
            # Check if it was converted before
            if not os.path.exists(os.path.join(self.output_dir, os.path.splitext(pdf_name)[0])):
                full_pdf_path = os.path.join(self.input_dir, pdf_name)

                # Convert pdf
                full_text, images, out_meta = convert_single_pdf(
                    full_pdf_path, self.model_lst, langs=self.langs,  ocr_all_pages=True)

                # Save markdown
                subfolder_dir = save_markdown(
                    self.output_dir, pdf_name, full_text, images, out_meta)
                print(f"Saved markdown to the '{
                    os.path.basename(subfolder_dir)}' folder.")

    def process(self):
        self.preprocess_pdf()
        self.convert_to_md()