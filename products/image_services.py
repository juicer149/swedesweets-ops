from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from django.core.files.storage import Storage
from django.core.files.uploadedfile import UploadedFile

from products.image_processing import (
    process_product_image,
    product_original_filename,
)
from products.models import (
    Product,
    ProductProfile,
)


@dataclass(frozen=True, slots=True)
class StoredImageFile:
    storage: Storage
    name: str


@dataclass(frozen=True, slots=True)
class ProductImageChange:
    """Files affected by one product image mutation.

    Database transactions do not include external file storage.

    rollback() removes newly written files.
    commit() removes files replaced by the successful mutation.
    """

    new_files: tuple[
        StoredImageFile,
        ...,
    ] = ()

    old_files: tuple[
        StoredImageFile,
        ...,
    ] = ()

    @classmethod
    def empty(
        cls,
    ) -> ProductImageChange:
        return cls()

    def rollback(self) -> None:
        _delete_stored_files(
            self.new_files
        )

    def commit(self) -> None:
        _delete_stored_files(
            self.old_files
        )


def change_product_image(
    *,
    product: Product,
    uploaded_image: UploadedFile | None = None,
    remove_image: bool = False,
) -> ProductImageChange:
    """Replace or remove the product catalog image.

    No upload and remove_image=False means no change.
    """

    if (
        uploaded_image is None
        and not remove_image
    ):
        return (
            ProductImageChange.empty()
        )

    if (
        uploaded_image is not None
        and remove_image
    ):
        raise ValueError(
            (
                "Cannot upload and remove "
                "a product image in the same operation."
            )
        )

    profile = (
        ProductProfile.objects
        .select_for_update()
        .get(
            product=product
        )
    )

    old_files = _profile_files(
        profile
    )

    if remove_image:
        profile.image = ""
        profile.thumbnail = ""

        profile.save(
            update_fields=[
                "image",
                "thumbnail",
            ]
        )

        return ProductImageChange(
            old_files=old_files,
        )

    assert uploaded_image is not None

    new_files: list[
        StoredImageFile
    ] = []

    try:
        processed = (
            process_product_image(
                uploaded_image
            )
        )

        profile.image.save(
            product_original_filename(
                uploaded_image.name
            ),
            uploaded_image,
            save=False,
        )

        new_files.append(
            StoredImageFile(
                storage=(
                    profile.image.storage
                ),
                name=(
                    profile.image.name
                ),
            )
        )

        profile.thumbnail.save(
            processed.thumbnail.name,
            processed.thumbnail,
            save=False,
        )

        new_files.append(
            StoredImageFile(
                storage=(
                    profile.thumbnail.storage
                ),
                name=(
                    profile.thumbnail.name
                ),
            )
        )

        profile.save(
            update_fields=[
                "image",
                "thumbnail",
            ]
        )

    except Exception:
        _delete_stored_files(
            new_files
        )
        raise

    return ProductImageChange(
        new_files=tuple(
            new_files
        ),
        old_files=old_files,
    )


def _profile_files(
    profile: ProductProfile,
) -> tuple[
    StoredImageFile,
    ...,
]:
    files: list[
        StoredImageFile
    ] = []

    if profile.image:
        files.append(
            StoredImageFile(
                storage=(
                    profile.image.storage
                ),
                name=(
                    profile.image.name
                ),
            )
        )

    if profile.thumbnail:
        files.append(
            StoredImageFile(
                storage=(
                    profile.thumbnail.storage
                ),
                name=(
                    profile.thumbnail.name
                ),
            )
        )

    return tuple(
        files
    )


def _delete_stored_files(
    stored_files: Iterable[
        StoredImageFile
    ],
) -> None:
    for stored_file in reversed(
        tuple(stored_files)
    ):
        if not stored_file.name:
            continue

        stored_file.storage.delete(
            stored_file.name
        )
