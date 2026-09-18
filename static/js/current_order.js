(() => {
  const root = document.querySelector(
    "[data-current-order]"
  );

  if (!root) {
    return;
  }

  const fallbackErrorMessage = (
    root.dataset.currentOrderErrorMessage
    || "Could not update quantity."
  );

  function notifyCartChanged(
    {
      lineId,
      quantity,
    }
  ) {
    document.dispatchEvent(
      new CustomEvent(
        "cart-changed",
        {
          detail: {
            source: "current-order",
            lineId,
            quantity,
          },
        }
      )
    );
  }

  async function updateQuantity(form) {
    const input = form.querySelector(
      "[data-quantity-input]"
    );

    const status = form.querySelector(
      "[data-current-order-quantity-status]"
    );

    if (!input) {
      return;
    }

    const requestedQuantity = Number(
      input.value
    );

    const confirmedQuantity = Number(
      form.dataset.confirmedQuantity
    );

    if (
      !Number.isInteger(
        requestedQuantity
      )
      || requestedQuantity < 1
    ) {
      input.value = String(
        confirmedQuantity || 1
      );

      return;
    }

    if (
      requestedQuantity
      === confirmedQuantity
    ) {
      return;
    }

    if (
      form.dataset.updateInProgress
      === "true"
    ) {
      form.dataset.pendingQuantity = String(
        requestedQuantity
      );

      return;
    }

    form.dataset.updateInProgress = "true";
    form.dataset.pendingQuantity = "";

    try {
      const formData = new FormData(
        form
      );

      formData.set(
        "quantity",
        String(requestedQuantity)
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

      const payload = await response.json();

      if (
        !response.ok
        || !payload.ok
      ) {
        throw new Error(
          payload.message
          || fallbackErrorMessage
        );
      }

      const savedQuantity = Number(
        payload.quantity
      );

      form.dataset.confirmedQuantity = String(
        savedQuantity
      );

      input.value = String(
        savedQuantity
      );

      if (status) {
        status.textContent = (
          payload.message || ""
        );
      }

      const lineId = (
        extractLineId(
          form.action
        )
      );

      notifyCartChanged({
        lineId,
        quantity: savedQuantity,
      });
    } catch (error) {
      input.value = (
        form.dataset.confirmedQuantity
        || "1"
      );

      if (status) {
        status.textContent = (
          error instanceof Error
            ? error.message
            : fallbackErrorMessage
        );
      }
    } finally {
      form.dataset.updateInProgress = "false";

      const pendingQuantity = Number(
        form.dataset.pendingQuantity
      );

      form.dataset.pendingQuantity = "";

      if (
        Number.isInteger(
          pendingQuantity
        )
        && pendingQuantity >= 1
        && pendingQuantity !== Number(
          form.dataset.confirmedQuantity
        )
      ) {
        input.value = String(
          pendingQuantity
        );

        void updateQuantity(
          form
        );
      }
    }
  }

  function extractLineId(url) {
    const match = url.match(
      /\/lines\/(\d+)\/quantity\/?$/
    );

    if (!match) {
      return null;
    }

    return Number(
      match[1]
    );
  }

  root.addEventListener(
    "change",
    (event) => {
      const input = event.target.closest(
        "[data-current-order-quantity-form] [data-quantity-input]"
      );

      if (!input) {
        return;
      }

      const form = input.closest(
        "[data-current-order-quantity-form]"
      );

      if (!form) {
        return;
      }

      void updateQuantity(
        form
      );
    }
  );

  root.addEventListener(
    "submit",
    (event) => {
      const form = event.target.closest(
        "[data-current-order-quantity-form]"
      );

      if (!form) {
        return;
      }

      event.preventDefault();

      void updateQuantity(
        form
      );
    }
  );

  document.addEventListener(
    "cart-changed",
    (event) => {
      if (
        event.detail?.source
        !== "navbar-cart"
      ) {
        return;
      }

      const lineId = Number(
        event.detail.lineId
      );

      const quantity = Number(
        event.detail.quantity
      );

      if (
        !Number.isInteger(
          lineId
        )
        || !Number.isInteger(
          quantity
        )
      ) {
        return;
      }

      const forms = (
        root.querySelectorAll(
          "[data-current-order-quantity-form]"
        )
      );

      const form = Array.from(
        forms
      ).find(
        (candidate) => (
          extractLineId(
            candidate.action
          ) === lineId
        )
      );

      if (!form) {
        return;
      }

      const input = form.querySelector(
        "[data-quantity-input]"
      );

      if (!input) {
        return;
      }

      form.dataset.confirmedQuantity = String(
        quantity
      );

      input.value = String(
        quantity
      );
    }
  );
})();
