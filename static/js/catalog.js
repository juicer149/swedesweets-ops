(() => {
  "use strict";

  const catalog = document.querySelector(
    ".catalog"
  );

  const forms = document.querySelectorAll(
    "[data-catalog-add-form]"
  );

  const feedback = document.querySelector(
    "[data-catalog-feedback]"
  );

  const catalogDataElement = document.getElementById(
    "business-catalog-data"
  );

  const addedLabel =
    catalog?.dataset.catalogAddedLabel
    || "Added";

  const fallbackErrorMessage =
    catalog?.dataset.catalogErrorMessage
    || "Could not add product.";

  if (!forms.length) {
    return;
  }


  function setFeedback(message) {
    if (!feedback) {
      return;
    }

    feedback.textContent = message;
  }


  function notifyDraftChanged() {
    document.dispatchEvent(
      new CustomEvent(
        "draft-order-changed",
        {
          detail: {
            source: "catalog",
          },
        }
      )
    );
  }


  function parseCatalogData() {
    if (!catalogDataElement) {
      return [];
    }

    try {
      const value = JSON.parse(
        catalogDataElement.textContent
      );

      return Array.isArray(value)
        ? value
        : [];
    } catch {
      return [];
    }
  }


  function offerKey(commercialPriceId) {
    return commercialPriceId === null
      ? ""
      : String(commercialPriceId);
  }


  function findOffer(
    catalogProduct,
    commercialPriceId
  ) {
    if (!catalogProduct) {
      return null;
    }

    const requestedKey = offerKey(
      commercialPriceId
    );

    return (
      catalogProduct.offers.find(
        (offer) =>
          offerKey(
            offer.commercial_price_id
          ) === requestedKey
      ) || null
    );
  }


  function selectedCommercialPriceId(card) {
    const select = card.querySelector(
      "[data-catalog-offer-select]"
    );

    if (select) {
      return select.value === ""
        ? null
        : Number(select.value);
    }

    const input = card.querySelector(
      "[data-catalog-offer-input]"
    );

    if (
      !input
      || input.value === ""
    ) {
      return null;
    }

    return Number(
      input.value
    );
  }


  function renderOfferBadge(
    card,
    offer
  ) {
    const badge = card.querySelector(
      "[data-catalog-offer-badge]"
    );

    if (!badge) {
      return;
    }

    const label =
      offer && offer.badge_label
        ? offer.badge_label
        : "";

    badge.textContent = label;
    badge.hidden = !label;
  }


  function initializeOfferControls(
    catalogProducts
  ) {
    const catalogByProductId = new Map(
      catalogProducts.map(
        (catalogProduct) => [
          String(
            catalogProduct.product_id
          ),
          catalogProduct,
        ]
      )
    );

    document
      .querySelectorAll(
        "[data-catalog-product]"
      )
      .forEach((card) => {
        const catalogProduct =
          catalogByProductId.get(
            card.dataset.productId
          );

        if (!catalogProduct) {
          return;
        }

        const renderSelectedOffer = () => {
          const offer = findOffer(
            catalogProduct,
            selectedCommercialPriceId(
              card
            )
          );

          renderOfferBadge(
            card,
            offer
          );
        };

        const select = card.querySelector(
          "[data-catalog-offer-select]"
        );

        if (select) {
          select.addEventListener(
            "change",
            renderSelectedOffer
          );
        }

        renderSelectedOffer();
      });
  }


  function resetQuantityInput(form) {
    const quantityInput = form.querySelector(
      "[data-quantity-input]"
    );

    if (!quantityInput) {
      return;
    }

    quantityInput.value = "1";

    quantityInput.dispatchEvent(
      new Event(
        "input",
        {
          bubbles: true,
        }
      )
    );

    quantityInput.dispatchEvent(
      new Event(
        "change",
        {
          bubbles: true,
        }
      )
    );
  }


  function openQuantityMode(form) {
    const defaultState = form.querySelector(
      "[data-catalog-purchase-default]"
    );

    const quantityState = form.querySelector(
      "[data-catalog-purchase-quantity]"
    );

    const quantityInput = form.querySelector(
      "[data-quantity-input]"
    );

    if (
      !defaultState
      || !quantityState
      || !quantityInput
    ) {
      return;
    }

    defaultState.hidden = true;
    quantityState.hidden = false;

    quantityInput.focus();
    quantityInput.select();
  }


  function closeQuantityMode(
    form,
    {
      resetQuantity = true,
    } = {}
  ) {
    const defaultState = form.querySelector(
      "[data-catalog-purchase-default]"
    );

    const quantityState = form.querySelector(
      "[data-catalog-purchase-quantity]"
    );

    if (
      !defaultState
      || !quantityState
    ) {
      return;
    }

    if (resetQuantity) {
      resetQuantityInput(
        form
      );
    }

    quantityState.hidden = true;
    defaultState.hidden = false;
  }


  function isQuantityModeOpen(form) {
    const quantityState = form.querySelector(
      "[data-catalog-purchase-quantity]"
    );

    return Boolean(
      quantityState
      && !quantityState.hidden
    );
  }


  async function submitAddForm(form) {
    const confirmButton = form.querySelector(
      "[data-catalog-confirm-button]"
    );

    if (!confirmButton) {
      return;
    }

    const originalLabel = (
      confirmButton.textContent.trim()
    );

    confirmButton.disabled = true;

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

      setFeedback(
        payload.message
      );

      confirmButton.textContent =
        addedLabel;

      /*
       * The server has changed the draft.
       *
       * Other components, such as the navbar cart,
       * can now refresh their own server-rendered
       * projection without catalog.js knowing
       * anything about their DOM.
       */
      notifyDraftChanged();

      window.setTimeout(
        () => {
          confirmButton.textContent =
            originalLabel;

          confirmButton.disabled =
            false;

          closeQuantityMode(
            form
          );
        },
        700
      );
    } catch (error) {
      confirmButton.textContent =
        originalLabel;

      confirmButton.disabled = false;

      setFeedback(
        error instanceof Error
          ? error.message
          : fallbackErrorMessage
      );
    }
  }


  function initializePurchaseControls() {
    forms.forEach((form) => {
      const cancelButton = form.querySelector(
        "[data-catalog-cancel-button]"
      );

      if (cancelButton) {
        cancelButton.addEventListener(
          "click",
          () => {
            closeQuantityMode(
              form
            );
          }
        );
      }

      form.addEventListener(
        "submit",
        (event) => {
          event.preventDefault();

          if (
            !isQuantityModeOpen(
              form
            )
          ) {
            openQuantityMode(
              form
            );

            return;
          }

          if (!form.checkValidity()) {
            form.reportValidity();
            return;
          }

          void submitAddForm(
            form
          );
        }
      );
    });
  }


  initializeOfferControls(
    parseCatalogData()
  );

  initializePurchaseControls();
})();
