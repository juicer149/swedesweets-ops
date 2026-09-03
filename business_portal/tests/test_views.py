from __future__ import annotations

import pytest
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from business_portal.orders.services import DraftStatus
from business_portal.orders.views import (
    PortalOrderIntent,
    _add_draft_save_message,
)


def _request_with_messages():
    request = RequestFactory().get("/")
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (DraftStatus.SAVED, "Draft order saved."),
        (DraftStatus.CLEARED, "Draft cleared."),
        (DraftStatus.UNCHANGED, "Nothing to save."),
    ],
)
def test_add_draft_save_message(status, message):
    request = _request_with_messages()

    _add_draft_save_message(request, status)

    stored_messages = list(get_messages(request))
    assert [str(item) for item in stored_messages] == [message]


def test_portal_order_intent_rejects_unknown_value():
    with pytest.raises(ValueError):
        PortalOrderIntent("not_a_real_intent")
