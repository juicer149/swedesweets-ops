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

  if (!select || !stock || !stockContainer) {
    return;
  }

  const initialStockLabel = stock.textContent.trim();

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


function initializeQuantityStepper() {
  const stepper = document.querySelector(
    "[data-quantity-stepper]"
  );

  if (!stepper) {
    return;
  }

  const input = stepper.querySelector(
    "[data-quantity-input]"
  );

  const decreaseButton = stepper.querySelector(
    "[data-quantity-decrease]"
  );

  const increaseButton = stepper.querySelector(
    "[data-quantity-increase]"
  );

  if (
    !input
    || !decreaseButton
    || !increaseButton
  ) {
    return;
  }

  const minimum = Number.parseInt(
    input.min || "1",
    10
  );

  const readQuantity = () => {
    const quantity = Number.parseInt(
      input.value,
      10
    );

    if (!Number.isInteger(quantity)) {
      return null;
    }

    return quantity;
  };

  const renderState = () => {
    const quantity = readQuantity();

    decreaseButton.disabled = (
      quantity === null
      || quantity <= minimum
    );
  };

  decreaseButton.addEventListener(
    "click",
    () => {
      const quantity = readQuantity();

      if (
        quantity === null
        || quantity <= minimum
      ) {
        return;
      }

      input.value = String(
        quantity - 1
      );

      renderState();
    }
  );

  increaseButton.addEventListener(
    "click",
    () => {
      const quantity = readQuantity();

      input.value = String(
        quantity === null
          ? minimum
          : quantity + 1
      );

      renderState();
    }
  );

  input.addEventListener(
    "input",
    renderState
  );

  input.addEventListener(
    "change",
    renderState
  );

  renderState();
}


function initializeCatalogDetail() {
  initializeOfferStockHint();
  initializeQuantityStepper();
}


if (document.readyState === "loading") {
  document.addEventListener(
    "DOMContentLoaded",
    initializeCatalogDetail
  );
} else {
  initializeCatalogDetail();
}
