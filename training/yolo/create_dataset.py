import os
import argparse

from components.dataset import DatasetCreator
from components.augmenter import Augmenter
from components.visualizer import Visualizer


# Create a parser
parser = argparse.ArgumentParser(description="Get some hyperparameters.")

parser.add_argument("--data_subdir",
                    default="page",
                    type=str,
                    help="Type of task type.")

parser.add_argument("--train_split",
                    default=0.8,
                    type=float,
                    help="Split of train set.")

parser.add_argument("--augment",
                    action="store_true",
                    help="Whether to augment train data.")

parser.add_argument("--aug_images",
                    default=100,
                    type=int,
                    help="How many augmented images to create.")

parser.add_argument("--visualize",
                    action="store_true",
                    help="Whether to visualize data.")

parser.add_argument("--vis_images",
                    default=20,
                    type=int,
                    help="How many images to visualize.")


# Get our arguments from the parser
args = parser.parse_args()

# Setup hyperparameters
DATA_SUBDIR = args.data_subdir
TRAIN_SPLIT = args.train_split
AUGMENT = args.augment
AUG_IMAGES = args.aug_images
VISUALIZE = args.visualize
VIS_IMAGES = args.vis_images

ANNS_TYPE = "polygon" if DATA_SUBDIR in ["page", "question"] else "obb"

HOME = os.getcwd()
DATA_DIR = os.path.join(HOME, "data", DATA_SUBDIR)
RAW_DIR = os.path.join(DATA_DIR, 'raw-data')
DATASET_DIR = os.path.join(DATA_DIR, 'dataset')
CHECK_IMAGES_DIR = os.path.join(DATA_DIR, "check-images")


def main() -> None:
    # Create dataset
    dataset_creator = DatasetCreator(RAW_DIR,
                                     DATASET_DIR,
                                     train_split=TRAIN_SPLIT)
    dataset_creator.process()

    # Augment dataset
    if AUGMENT:
        augmenter = Augmenter(dataset_dir=DATASET_DIR)
        augmenter.augment(anns_type=ANNS_TYPE,
                          num_images=AUG_IMAGES)

    # Visualize dataset
    if VISUALIZE:
        visualizer = Visualizer(dataset_dir=DATASET_DIR,
                                check_images_dir=CHECK_IMAGES_DIR)
        visualizer.visualize(anns_type=ANNS_TYPE,
                             num_images=VIS_IMAGES)


if __name__ == '__main__':
    main()
