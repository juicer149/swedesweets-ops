"use strict";


function initializeExpandableText() {
  const containers = document.querySelectorAll(
    "[data-expandable-text]"
  );

  for (const container of containers) {
    const content = container.querySelector(
      "[data-expandable-content]"
    );

    const toggle = container.querySelector(
      "[data-expandable-toggle]"
    );

    if (!content || !toggle) {
      continue;
    }

    const updateToggleVisibility = () => {
      if (container.classList.contains("is-expanded")) {
        toggle.hidden = false;
        return;
      }

      toggle.hidden = (
        content.scrollHeight <= content.clientHeight + 1
      );
    };

    requestAnimationFrame(
      updateToggleVisibility
    );

    toggle.addEventListener(
      "click",
      () => {
        const isExpanded = container.classList.toggle(
          "is-expanded"
        );

        toggle.setAttribute(
          "aria-expanded",
          String(isExpanded)
        );

        toggle.textContent = isExpanded
          ? toggle.dataset.lessLabel
          : toggle.dataset.moreLabel;
      }
    );

    window.addEventListener(
      "resize",
      updateToggleVisibility
    );
  }
}


function initializeOfferStockHint() {
  const select = document.querySelector(
    "[data-catalog-detail-offer]"
  );

  const stock = document.querySelector(
    "[data-catalog-detail-stock]"
  );

  if (!select || !stock) {
    return;
  }

  const renderStock = () => {
    const option = select.options[
      select.selectedIndex
    ];

    if (!option) {
      return;
    }

    stock.textContent = (
      option.dataset.stockLabel
      || ""
    );
  };

  select.addEventListener(
    "change",
    renderStock
  );

  renderStock();
}


function initializeCatalogDetail() {
  initializeExpandableText();
  initializeOfferStockHint();
}


if (document.readyState === "loading") {
  document.addEventListener(
    "DOMContentLoaded",
    initializeCatalogDetail
  );
} else {
  initializeCatalogDetail();
}
