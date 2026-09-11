"use strict";


function initializeQuantityStepper(stepper) {
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

  const step = Number.parseInt(
    input.step || "1",
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

  const setQuantity = (quantity) => {
    input.value = String(quantity);

    input.dispatchEvent(
      new Event(
        "input",
        {
          bubbles: true,
        }
      )
    );

    input.dispatchEvent(
      new Event(
        "change",
        {
          bubbles: true,
        }
      )
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

      setQuantity(
        Math.max(
          minimum,
          quantity - step
        )
      );
    }
  );

  increaseButton.addEventListener(
    "click",
    () => {
      const quantity = readQuantity();

      setQuantity(
        quantity === null
          ? minimum
          : quantity + step
      );
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


function initializeQuantitySteppers() {
  document
    .querySelectorAll(
      "[data-quantity-stepper]"
    )
    .forEach(
      initializeQuantityStepper
    );
}


if (document.readyState === "loading") {
  document.addEventListener(
    "DOMContentLoaded",
    initializeQuantitySteppers
  );
} else {
  initializeQuantitySteppers();
}
