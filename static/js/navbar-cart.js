"use strict";


(() => {
  const app = window.SwedeSweets;

  if (
    !app
    || !app.dom
  ) {
    console.error(
      "navbar-cart.js requires ui-dom.js"
    );

    return;
  }

  const container = document.querySelector(
    "[data-navbar-cart-container]"
  );

  if (!container) {
    return;
  }

  const fragmentUrl = (
    container.dataset.navbarCartUrl
  );

  if (!fragmentUrl) {
    return;
  }

  const {
    closest,
    hide,
    remove,
    replaceHtml,
    show,
  } = app.dom;


  let refreshInProgress = false;
  let refreshPending = false;


  /*
   * DOM lookup API
   * ------------------------------------------------------------------
   */


  function cartElement() {
    return container.querySelector(
      ".site-nav-cart"
    );
  }


  function cartTriggerElement() {
    const cart = cartElement();

    if (!cart) {
      return null;
    }

    return cart.querySelector(
      ".site-nav-cart__trigger"
    );
  }


  function lineFromElement(
    element
  ) {
    return closest(
      element,
      "[data-navbar-cart-line]"
    );
  }


  function lineIdFromElement(
    element
  ) {
    const line = lineFromElement(
      element
    );

    if (!line) {
      return null;
    }

    const lineId = Number(
      line.dataset.lineId
    );

    return Number.isInteger(
      lineId
    )
      ? lineId
      : null;
  }


  /*
   * Navbar-cart presentation API
   * ------------------------------------------------------------------
   */


  function closeNavbarCart({
    restoreFocus = false,
  } = {}) {
    const cart = cartElement();

    if (
      !cart
      || !cart.open
    ) {
      return;
    }

    cart.open = false;

    if (restoreFocus) {
      cartTriggerElement()?.focus();
    }
  }


  function navbarCartLineShow(
    element
  ) {
    show(
      lineFromElement(
        element
      )
    );
  }


  function navbarCartLineHide(
    element
  ) {
    hide(
      lineFromElement(
        element
      )
    );
  }


  function navbarCartLineRemove(
    element
  ) {
    remove(
      lineFromElement(
        element
      )
    );
  }


  /*
   * Cross-component event
   * ------------------------------------------------------------------
   */


  function dispatchDraftChanged(
    detail = {}
  ) {
    document.dispatchEvent(
      new CustomEvent(
        "draft-order-changed",
        {
          detail,
        }
      )
    );
  }


  /*
   * Cart fragment refresh
   * ------------------------------------------------------------------
   *
   * The server remains source of truth.
   */


  async function refreshNavbarCart({
    preserveOpenState = false,
  } = {}) {
    if (refreshInProgress) {
      refreshPending = true;
      return;
    }

    refreshInProgress = true;

    const currentCart = (
      cartElement()
    );

    const wasOpen = Boolean(
      preserveOpenState
      && currentCart?.open
    );

    try {
      const response = await fetch(
        fragmentUrl,
        {
          method: "GET",
          headers: {
            Accept: "text/html",
          },
          credentials: "same-origin",
        }
      );

      if (!response.ok) {
        throw new Error(
          "Could not refresh current order."
        );
      }

      const html = await response.text();

      replaceHtml(
        container,
        html
      );

      if (wasOpen) {
        const refreshedCart = (
          cartElement()
        );

        if (refreshedCart) {
          refreshedCart.open = true;
        }
      }
    } catch (error) {
      console.error(
        "Navbar cart refresh failed:",
        error
      );
    } finally {
      refreshInProgress = false;

      if (refreshPending) {
        refreshPending = false;

        void refreshNavbarCart({
          preserveOpenState: true,
        });
      }
    }
  }


  /*
   * Quantity mutation
   * ------------------------------------------------------------------
   */


  async function updateQuantity(
    form
  ) {
    const input = form.querySelector(
      "[data-quantity-input]"
    );

    const status = form.querySelector(
      "[data-navbar-cart-quantity-status]"
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

    const buttons = (
      form.querySelectorAll(
        "button"
      )
    );

    buttons.forEach(
      (button) => {
        button.disabled = true;
      }
    );

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

      const payload = (
        await response.json()
      );

      if (
        !response.ok
        || !payload.ok
      ) {
        throw new Error(
          payload.message
          || "Could not update quantity."
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

      dispatchDraftChanged({
        source: "navbar-cart",
        mutation: "quantity",
        lineId: lineIdFromElement(
          form
        ),
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
            : "Could not update quantity."
        );
      }
    } finally {
      form.dataset.updateInProgress = "false";

      buttons.forEach(
        (button) => {
          button.disabled = false;
        }
      );

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


  /*
   * Remove mutation
   * ------------------------------------------------------------------
   *
   * The line is first hidden optimistically.
   *
   * Success:
   *   hidden -> removed -> server fragment refresh
   *
   * Failure:
   *   hidden -> shown again
   */


  async function removeNavbarCartLine(
    form
  ) {
    const line = lineFromElement(
      form
    );

    if (!line) {
      return;
    }

    if (
      form.dataset.removeInProgress
      === "true"
    ) {
      return;
    }

    const lineId = lineIdFromElement(
      form
    );

    const submitButton = (
      form.querySelector(
        'button[type="submit"]'
      )
    );

    form.dataset.removeInProgress = "true";

    if (submitButton) {
      submitButton.disabled = true;
    }

    navbarCartLineHide(
      form
    );

    try {
      const response = await fetch(
        form.action,
        {
          method: "POST",
          body: new FormData(form),
          headers: {
            Accept: "application/json",
          },
          credentials: "same-origin",
        }
      );

      const payload = (
        await response.json()
      );

      if (
        !response.ok
        || !payload.ok
      ) {
        throw new Error(
          payload.message
          || "Could not remove product."
        );
      }

      navbarCartLineRemove(
        form
      );

      dispatchDraftChanged({
        source: "navbar-cart",
        mutation: "remove",
        lineId,
      });

      await refreshNavbarCart({
        preserveOpenState: true,
      });
    } catch (error) {
      navbarCartLineShow(
        line
      );

      form.dataset.removeInProgress = "false";

      if (submitButton) {
        submitButton.disabled = false;
      }

      console.error(
        "Navbar cart remove failed:",
        error
      );
    }
  }


  /*
   * Event delegation
   * ------------------------------------------------------------------
   *
   * Delegation is required because navbar contents can
   * be replaced by server-rendered fragments.
   */


  document.addEventListener(
    "change",
    (event) => {
      const input = closest(
        event.target,
        [
          "[data-navbar-cart-quantity-form]",
          "[data-quantity-input]",
        ].join(" ")
      );

      if (!input) {
        return;
      }

      const form = closest(
        input,
        "[data-navbar-cart-quantity-form]"
      );

      if (!form) {
        return;
      }

      void updateQuantity(
        form
      );
    }
  );


  document.addEventListener(
    "submit",
    (event) => {
      const quantityForm = closest(
        event.target,
        "[data-navbar-cart-quantity-form]"
      );

      if (quantityForm) {
        event.preventDefault();

        void updateQuantity(
          quantityForm
        );

        return;
      }

      const removeForm = closest(
        event.target,
        "[data-navbar-cart-remove-form]"
      );

      if (!removeForm) {
        return;
      }

      event.preventDefault();

      void removeNavbarCartLine(
        removeForm
      );
    }
  );


  /*
   * Close the cart when the user clicks outside it.
   *
   * Because the check is against the whole <details>
   * element, every present and future control inside
   * the cart counts as an inside click automatically.
   */


  document.addEventListener(
    "click",
    (event) => {
      const cart = cartElement();

      if (
        !cart
        || !cart.open
      ) {
        return;
      }

      if (
        cart.contains(
          event.target
        )
      ) {
        return;
      }

      closeNavbarCart();
    }
  );


  /*
   * Escape follows normal popup/dropdown keyboard
   * behaviour and restores focus to the trigger.
   */


  document.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key !== "Escape"
      ) {
        return;
      }

      const cart = cartElement();

      if (
        !cart
        || !cart.open
      ) {
        return;
      }

      event.preventDefault();

      closeNavbarCart({
        restoreFocus: true,
      });
    }
  );


  document.addEventListener(
    "draft-order-changed",
    (event) => {
      if (
        event.detail?.source
        === "navbar-cart"
      ) {
        return;
      }

      void refreshNavbarCart({
        preserveOpenState: true,
      });
    }
  );


  /*
   * Public navbar-cart UI API
   * ------------------------------------------------------------------
   */


  app.navbarCart = Object.freeze({
    close: closeNavbarCart,
    refresh: refreshNavbarCart,

    line: Object.freeze({
      show: navbarCartLineShow,
      hide: navbarCartLineHide,
      remove: navbarCartLineRemove,
    }),
  });
})();
