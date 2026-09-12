from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import (
    SimpleUploadedFile,
)
from django.test import override_settings
from PIL import Image

from products.image_services import (
    change_product_image,
)
from products.tests.factories import (
    product_factory,
)


def uploaded_image(
    *,
    name: str = "product.png",
    width: int = 1200,
    height: int = 900,
    image_format: str = "PNG",
) -> SimpleUploadedFile:
    output = BytesIO()

    Image.new(
        "RGB",
        (
            width,
            height,
        ),
    ).save(
        output,
        format=image_format,
    )

    content_type = (
        "image/jpeg"
        if image_format == "JPEG"
        else "image/png"
    )

    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type=content_type,
    )


@pytest.mark.django_db
def test_change_product_image_stores_original_and_thumbnail(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        change = change_product_image(
            product=product,
            uploaded_image=(
                uploaded_image()
            ),
        )

        product.profile.refresh_from_db()

        assert product.profile.image
        assert product.profile.thumbnail

        assert (
            product.profile.image.name
            .startswith(
                "products/originals/"
            )
        )

        assert (
            product.profile.thumbnail.name
            .startswith(
                "products/thumbnails/"
            )
        )

        assert (
            product.profile.thumbnail.name
            .endswith(".webp")
        )

        assert (
            product.profile.image.storage.exists(
                product.profile.image.name
            )
        )

        assert (
            product.profile.thumbnail.storage.exists(
                product.profile.thumbnail.name
            )
        )

        change.commit()


@pytest.mark.django_db
def test_change_product_image_preserves_original_format(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        change = change_product_image(
            product=product,
            uploaded_image=(
                uploaded_image(
                    name="product.jpg",
                    image_format="JPEG",
                )
            ),
        )

        product.profile.refresh_from_db()

        assert (
            product.profile.image.name
            .endswith(".jpg")
        )

        change.commit()


@pytest.mark.django_db
def test_product_thumbnail_is_webp_and_at_most_640_pixels(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        change = change_product_image(
            product=product,
            uploaded_image=(
                uploaded_image(
                    width=1600,
                    height=1200,
                )
            ),
        )

        product.profile.refresh_from_db()

        storage = (
            product.profile
            .thumbnail
            .storage
        )

        with storage.open(
            product.profile.thumbnail.name,
            "rb",
        ) as thumbnail_file:
            with Image.open(
                thumbnail_file
            ) as thumbnail:
                assert (
                    thumbnail.width
                    <= 640
                )
                assert (
                    thumbnail.height
                    <= 640
                )
                assert (
                    thumbnail.format
                    == "WEBP"
                )

        change.commit()


@pytest.mark.django_db
def test_product_thumbnail_preserves_aspect_ratio(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        change = change_product_image(
            product=product,
            uploaded_image=(
                uploaded_image(
                    width=1200,
                    height=600,
                )
            ),
        )

        product.profile.refresh_from_db()

        storage = (
            product.profile
            .thumbnail
            .storage
        )

        with storage.open(
            product.profile.thumbnail.name,
            "rb",
        ) as thumbnail_file:
            with Image.open(
                thumbnail_file
            ) as thumbnail:
                assert (
                    thumbnail.size
                    == (
                        640,
                        320,
                    )
                )

        change.commit()


@pytest.mark.django_db
def test_image_change_rollback_removes_new_files(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        change = change_product_image(
            product=product,
            uploaded_image=(
                uploaded_image()
            ),
        )

        new_files = (
            change.new_files
        )

        assert all(
            stored_file.storage.exists(
                stored_file.name
            )
            for stored_file
            in new_files
        )

        change.rollback()

        assert all(
            not stored_file.storage.exists(
                stored_file.name
            )
            for stored_file
            in new_files
        )


@pytest.mark.django_db
def test_replacing_image_keeps_old_files_until_commit(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        first_change = (
            change_product_image(
                product=product,
                uploaded_image=(
                    uploaded_image(
                        name="first.png"
                    )
                ),
            )
        )

        first_change.commit()

        product.profile.refresh_from_db()

        old_image_name = (
            product.profile.image.name
        )
        old_thumbnail_name = (
            product.profile.thumbnail.name
        )

        image_storage = (
            product.profile.image.storage
        )
        thumbnail_storage = (
            product.profile.thumbnail.storage
        )

        second_change = (
            change_product_image(
                product=product,
                uploaded_image=(
                    uploaded_image(
                        name="second.png"
                    )
                ),
            )
        )

        assert (
            image_storage.exists(
                old_image_name
            )
        )
        assert (
            thumbnail_storage.exists(
                old_thumbnail_name
            )
        )

        second_change.commit()

        assert not (
            image_storage.exists(
                old_image_name
            )
        )
        assert not (
            thumbnail_storage.exists(
                old_thumbnail_name
            )
        )


@pytest.mark.django_db
def test_replacing_image_commit_keeps_new_files(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        first_change = (
            change_product_image(
                product=product,
                uploaded_image=(
                    uploaded_image(
                        name="first.png"
                    )
                ),
            )
        )
        first_change.commit()

        second_change = (
            change_product_image(
                product=product,
                uploaded_image=(
                    uploaded_image(
                        name="second.png"
                    )
                ),
            )
        )

        product.profile.refresh_from_db()

        new_image_name = (
            product.profile.image.name
        )
        new_thumbnail_name = (
            product.profile.thumbnail.name
        )

        image_storage = (
            product.profile.image.storage
        )
        thumbnail_storage = (
            product.profile.thumbnail.storage
        )

        second_change.commit()

        assert image_storage.exists(
            new_image_name
        )
        assert thumbnail_storage.exists(
            new_thumbnail_name
        )


@pytest.mark.django_db
def test_remove_product_image_clears_database_fields(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        upload_change = (
            change_product_image(
                product=product,
                uploaded_image=(
                    uploaded_image()
                ),
            )
        )
        upload_change.commit()

        remove_change = (
            change_product_image(
                product=product,
                remove_image=True,
            )
        )

        product.profile.refresh_from_db()

        assert not product.profile.image
        assert not product.profile.thumbnail

        remove_change.commit()


@pytest.mark.django_db
def test_remove_product_image_deletes_files_only_after_commit(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        upload_change = (
            change_product_image(
                product=product,
                uploaded_image=(
                    uploaded_image()
                ),
            )
        )
        upload_change.commit()

        product.profile.refresh_from_db()

        image_name = (
            product.profile.image.name
        )
        thumbnail_name = (
            product.profile.thumbnail.name
        )

        image_storage = (
            product.profile.image.storage
        )
        thumbnail_storage = (
            product.profile.thumbnail.storage
        )

        remove_change = (
            change_product_image(
                product=product,
                remove_image=True,
            )
        )

        assert image_storage.exists(
            image_name
        )
        assert thumbnail_storage.exists(
            thumbnail_name
        )

        remove_change.commit()

        assert not image_storage.exists(
            image_name
        )
        assert not thumbnail_storage.exists(
            thumbnail_name
        )


@pytest.mark.django_db
def test_no_image_change_does_nothing(
    tmp_path,
):
    with override_settings(
        MEDIA_ROOT=tmp_path,
    ):
        product = product_factory()

        change = change_product_image(
            product=product,
        )

        product.profile.refresh_from_db()

        assert not product.profile.image
        assert not product.profile.thumbnail
        assert change.new_files == ()
        assert change.old_files == ()
