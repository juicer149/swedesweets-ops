from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NavbarCartLine:
    line_id: int
    label: str
    product_url: str
    metadata: tuple[str, ...]
    quantity: int
    quantity_url: str
    remove_url: str


@dataclass(frozen=True, slots=True)
class NavbarCart:
    aria_label: str
    title: str
    line_count: int
    lines: tuple[NavbarCartLine, ...]
    fragment_url: str
    proceed_label: str
    proceed_url: str
    empty_message: str
    empty_action_label: str
    empty_action_url: str

    @property
    def has_lines(self) -> bool:
        return self.line_count > 0
