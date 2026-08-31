from __future__ import annotations

from products.models import Product


def translated_product_name(
    product: Product,
    *,
    language_code: str,
) -> str:
    """Return the customer-facing product name for a language.

    Prefer prefetched translations when available to avoid per-product queries.
    Fall back to the product's normal display name when no translation exists.
    """

    prefetched_translations = getattr(
        product,
        "prefetched_translations",
        None,
    )

    if prefetched_translations is not None:
        for translation in prefetched_translations:
            if (
                translation.language_code == language_code
                and translation.name
            ):
                return translation.name

        return product.display_name

    translation = (
        product.translations
        .filter(language_code=language_code)
        .first()
    )

    if translation is None:
        return product.display_name

    return translation.name
