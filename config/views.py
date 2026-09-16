from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def index(request: HttpRequest) -> HttpResponse:
    """Redirect the site root to the public storefront catalog.

    A placeholder landing page: the public-site branch may later replace
    this with a real hero page, but storefront:product_list remains the
    canonical catalog URL either way, so nothing downstream needs to
    change when that happens.
    """

    return redirect("storefront:product_list")
