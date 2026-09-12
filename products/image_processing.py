from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from django.core.files.base import ContentFile
from PIL import Image, ImageOps


THUMBNAIL_MAX_SIZE = (
    640,
    640,
)
THUMBNAIL_QUALITY = 78


@dataclass(frozen=True, slots=True)
class ProcessedProductImage:
    thumbnail: ContentFile


def process_product_image(
    image_file: BinaryIO,
) -> ProcessedProductImage:
    """Create a WebP thumbnail from one uploaded product image.

    EXIF orientation is applied before resizing.
    The supplied original file is rewound before returning.
    """

    image_file.seek(0)

    with Image.open(
        image_file
    ) as source:
        oriented = (
            ImageOps.exif_transpose(
                source
            )
        )

        thumbnail = (
            _prepare_for_webp(
                oriented.copy()
            )
        )

        thumbnail.thumbnail(
            THUMBNAIL_MAX_SIZE,
            Image.Resampling.LANCZOS,
        )

        output = BytesIO()

        thumbnail.save(
            output,
            format="WEBP",
            quality=THUMBNAIL_QUALITY,
            method=6,
        )

    image_file.seek(0)

    return ProcessedProductImage(
        thumbnail=ContentFile(
            output.getvalue(),
            name=(
                f"{uuid4().hex}.webp"
            ),
        ),
    )


def product_original_filename(
    original_name: str,
) -> str:
    """Generate a storage-safe name while preserving JPEG/PNG format."""

    suffix = (
        Path(original_name)
        .suffix
        .lower()
    )

    if suffix == ".jpeg":
        suffix = ".jpg"

    if suffix not in {
        ".jpg",
        ".png",
    }:
        raise ValueError(
            "Unsupported product image extension."
        )

    return (
        f"{uuid4().hex}{suffix}"
    )


def _prepare_for_webp(
    image: Image.Image,
) -> Image.Image:
    if image.mode in {
        "RGB",
        "RGBA",
    }:
        return image

    if "transparency" in image.info:
        return image.convert(
            "RGBA"
        )

    return image.convert(
        "RGB"
    )
