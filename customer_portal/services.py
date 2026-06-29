from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from customers.models import Customer
from inventory.errors import InvalidStockOperation
from orders.datatypes import OrderLineInput
from orders.errors import InvalidOrderOperation
from orders.models import Order
from orders.services import (
    discard_draft_order,
    get_or_create_customer_draft_order,
    replace_draft_order_lines,
)

DRAFT_SAVED = "saved"
DRAFT_CLEARED = "cleared"
DRAFT_UNCHANGED = "unchanged"


PORTAL_DRAFT_OPERATION_ERRORS = (
    InvalidOrderOperation,
    InvalidStockOperation,
)


@dataclass(frozen=True, slots=True)
class PortalDraftMutationResult:
    draft_order: Order | None
    succeeded: bool
    status: str
    errors: tuple[str, ...] = ()


def save_or_clear_portal_draft_order(
    *,
    customer: Customer,
    draft_order: Order | None,
    line_inputs: Iterable[OrderLineInput],
    user=None,
) -> PortalDraftMutationResult:
    """Save validated portal draft lines, or clear the draft if it is empty.

    This is a customer-portal workflow rule:

    - non-empty lines mean "persist these draft lines"
    - empty lines mean "there is no draft content to keep"

    Core order mutations are delegated to orders.services.
    """
    line_inputs = tuple(line_inputs)

    scope_error = _validate_optional_order_customer_scope(
        customer=customer,
        order=draft_order,
    )

    if scope_error:
        return _failed(
            draft_order=draft_order,
            errors=(scope_error,),
        )

    if not line_inputs:
        return discard_portal_draft_order(
            customer=customer,
            draft_order=draft_order,
            empty_save=True,
        )

    if draft_order is None:
        try:
            draft_order = get_or_create_customer_draft_order(
                customer=customer,
            )
        except PORTAL_DRAFT_OPERATION_ERRORS as error:
            return _failed(
                draft_order=None,
                errors=(str(error),),
            )

    try:
        draft_order = replace_draft_order_lines(
            order=draft_order,
            lines=line_inputs,
            user=user,
        )
    except PORTAL_DRAFT_OPERATION_ERRORS as error:
        return _failed(
            draft_order=draft_order,
            errors=(str(error),),
        )

    return _succeeded(
        draft_order=draft_order,
        status=DRAFT_SAVED,
    )


def discard_portal_draft_order(
    *,
    customer: Customer,
    draft_order: Order | None,
    empty_save: bool = False,
) -> PortalDraftMutationResult:
    """Discard a draft order in the customer portal scope.

    The ownership check lives outside the core order service. That keeps
    orders.services reusable while preventing portal code from mutating another
    customer's draft.
    """
    scope_error = _validate_optional_order_customer_scope(
        customer=customer,
        order=draft_order,
    )

    if scope_error:
        return _failed(
            draft_order=draft_order,
            errors=(scope_error,),
        )

    if draft_order is None:
        return _succeeded(
            draft_order=None,
            status=DRAFT_UNCHANGED,
        )

    try:
        discard_draft_order(order=draft_order)
    except PORTAL_DRAFT_OPERATION_ERRORS as error:
        return _failed(
            draft_order=draft_order,
            errors=(str(error),),
        )

    status = DRAFT_CLEARED if empty_save else DRAFT_CLEARED

    return _succeeded(
        draft_order=None,
        status=status,
    )


def _validate_optional_order_customer_scope(
    *,
    customer: Customer,
    order: Order | None,
) -> str:
    if order is None:
        return ""

    if order.customer_id == customer.id:
        return ""

    return "Order does not belong to the current customer."


def _succeeded(
    *,
    draft_order: Order | None,
    status: str,
) -> PortalDraftMutationResult:
    return PortalDraftMutationResult(
        draft_order=draft_order,
        succeeded=True,
        status=status,
        errors=(),
    )


def _failed(
    *,
    draft_order: Order | None,
    errors: tuple[str, ...],
) -> PortalDraftMutationResult:
    return PortalDraftMutationResult(
        draft_order=draft_order,
        succeeded=False,
        status=DRAFT_UNCHANGED,
        errors=errors,
    )
