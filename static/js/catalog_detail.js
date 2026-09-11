"use strict";


function initializeOfferStockHint() {
  const select = document.querySelector(
    "[data-catalog-detail-offer]"
  );

  const stock = document.querySelector(
    "[data-catalog-detail-stock]"
  );

  const stockContainer = document.querySelector(
    "[data-catalog-detail-stock-container]"
  );

  if (
    !select
    || !stock
    || !stockContainer
  ) {
    return;
  }

  const initialStockLabel = (
    stock.textContent.trim()
  );

  const renderStock = () => {
    const option = select.options[
      select.selectedIndex
    ];

    if (!option) {
      return;
    }

    const stockLabel = (
      option.dataset.stockLabel
      || initialStockLabel
    ).trim();

    stock.textContent = stockLabel;

    stockContainer.hidden = (
      stockLabel.length === 0
    );
  };

  select.addEventListener(
    "change",
    renderStock
  );

  renderStock();
}


function initializeCatalogDetail() {
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
