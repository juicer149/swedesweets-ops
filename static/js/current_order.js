(() => {
  "use strict";

  const currentOrder = document.querySelector(
    "[data-current-order]"
  );

  const forms = document.querySelectorAll(
    "[data-current-order-quantity-form]"
  );

  if (
    !currentOrder
    || !forms.length
  ) {
    return;
  }

  const fallbackErrorMessage =
    currentOrder.dataset.currentOrderErrorMessage
    || "Could not update quantity.";


  function parseQuantity(input) {
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
      || quantity <= 0
    ) {
      return null;
    }

    return quantity;
  }


  function setInputValue(
    input,
    quantity
  ) {
    input.value = String(
      quantity
    );

    input.dispatchEvent(
      new Event(
        "input",
        {
          bubbles: true,
        }
      )
    );
  }


  function showInputError(
    input,
    message
  ) {
    input.setCustomValidity(
      message
    );

    input.reportValidity();
  }


  async function postQuantity(
    form,
    quantity
  ) {
    const formData = new FormData(
      form
    );

    formData.set(
      "quantity",
      String(quantity)
    );

    const response = await fetch(
      form.action,
      {
        method: "POST",
        body: formData,
        headers: {
          Accept: "application/json",
        },
        credentials: "same-origin",
      }
    );

    let payload;

    try {
      payload = await response.json();
    } catch {
      throw new Error(
        fallbackErrorMessage
      );
    }

    if (
      !response.ok
      || !payload.ok
    ) {
      throw new Error(
        payload.message
        || fallbackErrorMessage
      );
    }

    return payload;
  }


  function initializeQuantityForm(form) {
    const input = form.querySelector(
      "[data-quantity-input]"
    );

    const status = form.querySelector(
      "[data-current-order-quantity-status]"
    );

    if (!input) {
      return;
    }

    let confirmedQuantity = Number(
      form.dataset.confirmedQuantity
    );

    if (
      !Number.isInteger(
        confirmedQuantity
      )
      || confirmedQuantity <= 0
    ) {
      confirmedQuantity = parseQuantity(
        input
      ) || 1;
    }

    let pendingQuantity = null;
    let updateInProgress = false;


    const announce = (message) => {
      if (!status) {
        return;
      }

      status.textContent = message;
    };


    const restoreConfirmedQuantity = () => {
      setInputValue(
        input,
        confirmedQuantity
      );
    };


    const processQueue = async () => {
      if (updateInProgress) {
        return;
      }

      updateInProgress = true;

      form.setAttribute(
        "aria-busy",
        "true"
      );

      try {
        while (
          pendingQuantity !== null
        ) {
          const quantity =
            pendingQuantity;

          pendingQuantity = null;

          if (
            quantity
            === confirmedQuantity
          ) {
            continue;
          }

          try {
            const payload =
              await postQuantity(
                form,
                quantity
              );

            confirmedQuantity =
              payload.quantity;

            form.dataset.confirmedQuantity =
              String(
                confirmedQuantity
              );

            announce(
              payload.message || ""
            );
          } catch (error) {
            pendingQuantity = null;

            restoreConfirmedQuantity();

            const message =
              error instanceof Error
                ? error.message
                : fallbackErrorMessage;

            announce(
              message
            );

            showInputError(
              input,
              message
            );

            break;
          }
        }
      } finally {
        updateInProgress = false;

        form.removeAttribute(
          "aria-busy"
        );
      }
    };


    const queueCurrentQuantity = () => {
      if (!input.checkValidity()) {
        input.reportValidity();
        return;
      }

      const quantity = parseQuantity(
        input
      );

      if (quantity === null) {
        input.reportValidity();
        return;
      }

      pendingQuantity = quantity;

      processQueue();
    };


    input.addEventListener(
      "input",
      () => {
        input.setCustomValidity("");
      }
    );


    input.addEventListener(
      "change",
      queueCurrentQuantity
    );


    form.addEventListener(
      "submit",
      (event) => {
        event.preventDefault();

        queueCurrentQuantity();
      }
    );
  }


  forms.forEach(
    initializeQuantityForm
  );
})();
