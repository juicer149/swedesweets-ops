"use strict";


(() => {
  if (
    window.__swedeSweetsQuantityStepperInitialized
  ) {
    return;
  }

  window.__swedeSweetsQuantityStepperInitialized = true;


  function parseOptionalNumber(
    value,
    fallback
  ) {
    if (
      value === null
      || value === undefined
      || String(value).trim() === ""
    ) {
      return fallback;
    }

    const parsed = Number(
      value
    );

    return Number.isFinite(parsed)
      ? parsed
      : fallback;
  }


  function getStepper(element) {
    return element.closest(
      "[data-quantity-stepper]"
    );
  }


  function getInput(stepper) {
    return stepper.querySelector(
      "[data-quantity-input]"
    );
  }


  function getMinimum(input) {
    return parseOptionalNumber(
      input.min,
      1
    );
  }


  function getMaximum(input) {
    return parseOptionalNumber(
      input.max,
      Number.POSITIVE_INFINITY
    );
  }


  function getStep(input) {
    const step = parseOptionalNumber(
      input.step,
      1
    );

    return step > 0
      ? step
      : 1;
  }


  function readQuantity(input) {
    const rawValue = input.value.trim();

    if (!rawValue) {
      return null;
    }

    const quantity = Number(
      rawValue
    );

    if (
      !Number.isFinite(quantity)
      || !Number.isInteger(quantity)
    ) {
      return null;
    }

    return quantity;
  }


  function renderState(stepper) {
    const input = getInput(
      stepper
    );

    if (!input) {
      return;
    }

    const quantity = readQuantity(
      input
    );

    const minimum = getMinimum(
      input
    );

    const maximum = getMaximum(
      input
    );

    const decreaseButton = (
      stepper.querySelector(
        "[data-quantity-decrease]"
      )
    );

    const increaseButton = (
      stepper.querySelector(
        "[data-quantity-increase]"
      )
    );

    if (decreaseButton) {
      decreaseButton.disabled = (
        quantity === null
        || quantity <= minimum
      );
    }

    if (increaseButton) {
      increaseButton.disabled = (
        quantity !== null
        && quantity >= maximum
      );
    }
  }


  function setQuantity(
    stepper,
    quantity
  ) {
    const input = getInput(
      stepper
    );

    if (!input) {
      return;
    }

    input.value = String(
      quantity
    );

    /*
     * Keep the same browser contract as the original
     * quantity stepper.
     *
     * "input" lets presentation code react immediately.
     * "change" lets mutation code persist the new value.
     */
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
  }


  function decreaseQuantity(button) {
    const stepper = getStepper(
      button
    );

    if (!stepper) {
      return;
    }

    const input = getInput(
      stepper
    );

    if (!input) {
      return;
    }

    const quantity = readQuantity(
      input
    );

    const minimum = getMinimum(
      input
    );

    const step = getStep(
      input
    );

    if (
      quantity === null
      || quantity <= minimum
    ) {
      return;
    }

    setQuantity(
      stepper,
      Math.max(
        minimum,
        quantity - step
      )
    );
  }


  function increaseQuantity(button) {
    const stepper = getStepper(
      button
    );

    if (!stepper) {
      return;
    }

    const input = getInput(
      stepper
    );

    if (!input) {
      return;
    }

    const quantity = readQuantity(
      input
    );

    const minimum = getMinimum(
      input
    );

    const maximum = getMaximum(
      input
    );

    const step = getStep(
      input
    );

    const nextQuantity = (
      quantity === null
        ? minimum
        : quantity + step
    );

    setQuantity(
      stepper,
      Math.min(
        maximum,
        nextQuantity
      )
    );
  }


  document.addEventListener(
    "click",
    (event) => {
      const decreaseButton = (
        event.target.closest(
          "[data-quantity-decrease]"
        )
      );

      if (decreaseButton) {
        decreaseQuantity(
          decreaseButton
        );

        return;
      }

      const increaseButton = (
        event.target.closest(
          "[data-quantity-increase]"
        )
      );

      if (increaseButton) {
        increaseQuantity(
          increaseButton
        );
      }
    }
  );


  document.addEventListener(
    "input",
    (event) => {
      if (
        !event.target.matches(
          "[data-quantity-input]"
        )
      ) {
        return;
      }

      const stepper = getStepper(
        event.target
      );

      if (stepper) {
        renderState(
          stepper
        );
      }
    }
  );


  document.addEventListener(
    "change",
    (event) => {
      if (
        !event.target.matches(
          "[data-quantity-input]"
        )
      ) {
        return;
      }

      const stepper = getStepper(
        event.target
      );

      if (stepper) {
        renderState(
          stepper
        );
      }
    }
  );


  document
    .querySelectorAll(
      "[data-quantity-stepper]"
    )
    .forEach(
      renderState
    );
})();
