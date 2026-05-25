from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PAGE_HEADER_ACTION_CLASS = (
    "button button--lg button--solid button--tone-place button--with-icon"
)

@dataclass(frozen=True)
class PageHeaderAction:
    label: str
    href: str
    icon: str = "plus"
    aria_label: str = ""
    css_class: str = DEFAULT_PAGE_HEADER_ACTION_CLASS 


@dataclass(frozen=True)
class PageHeader:
    title: str
    title_id: str
    description: str = ""
    action: PageHeaderAction | None = None
