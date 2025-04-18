from pydantic import computed_field
from pydantic_settings import BaseSettings

import torch


class Settings(BaseSettings):
    IMAGE_DPI: int = 96
    IMAGE_DPI_HIGHRES: int = 192
    MAX_WIDTH: int = 1525
    MAX_HEIGHT: int = 2048

    @computed_field
    def DEVICE(self) -> str:
        if torch.cuda.is_available():
            return "cuda"

        return "cpu"


settings = Settings()
