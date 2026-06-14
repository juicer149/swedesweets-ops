from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def index(request):
    return HttpResponse("Customer portal home")


@login_required
def orders(request):
    return HttpResponse("My orders")


@login_required
def order_detail(request, order_id: int):
    return HttpResponse(f"My order {order_id}")


@login_required
def profile(request):
    return HttpResponse("My profile")


@login_required
def edit_profile(request):
    return HttpResponse("Edit my profile")
