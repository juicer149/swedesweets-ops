(() => {
  "use strict";

  const catalog = document.querySelector(
    ".catalog"
  );

  if (!catalog) {
    return;
  }

  const forms = document.querySelectorAll(
    "[data-catalog-add-form]"
  );

  const cards = Array.from(
    document.querySelectorAll(
      "[data-catalog-product]"
    )
  );

  const categoryButtons = Array.from(
    document.querySelectorAll(
      "[data-catalog-category]"
    )
  );

  const searchInput = document.querySelector(
    "[data-catalog-search]"
  );

  const noResults = document.querySelector(
    "[data-catalog-no-results]"
  );

  const feedback = document.querySelector(
    "[data-catalog-feedback]"
  );

  const catalogDataElement = document.getElementById(
    "business-catalog-data"
  );

  const addedLabel =
    catalog.dataset.catalogAddedLabel
    || "Added";

  const fallbackErrorMessage =
    catalog.dataset.catalogErrorMessage
    || "Could not add product.";

  const filterState = {
    category: "all",
    query: "",
  };


  function setFeedback(message) {
    if (!feedback) {
      return;
    }

    feedback.textContent = message;
  }


  function normalizeSearchValue(
    value
  ) {
    return String(
      value || ""
    )
      .trim()
      .toLocaleLowerCase();
  }


  function cardMatchesCategory(
    card
  ) {
    return (
      filterState.category === "all"
      || card.dataset.productCategory
        === filterState.category
    );
  }


  function cardMatchesSearch(
    card
  ) {
    if (!filterState.query) {
      return true;
    }

    const searchText = normalizeSearchValue(
      card.dataset.productSearch
    );

    return searchText.includes(
      filterState.query
    );
  }


  function cardShouldBeVisible(
    card
  ) {
    return (
      cardMatchesCategory(
        card
      )
      && cardMatchesSearch(
        card
      )
    );
  }


  function renderCategoryButtons() {
    categoryButtons.forEach(
      (button) => {
        const isActive = (
          button.dataset.catalogCategory
          === filterState.category
        );

        button.classList.toggle(
          "section-nav__link--active",
          isActive
        );

        button.setAttribute(
          "aria-pressed",
          String(isActive)
        );
      }
    );
  }


  function applyCatalogFilters() {
    let visibleCount = 0;

    cards.forEach(
      (card) => {
        const visible = (
          cardShouldBeVisible(
            card
          )
        );

        card.hidden = !visible;

        if (visible) {
          visibleCount += 1;
        }
      }
    );

    if (noResults) {
      noResults.hidden = (
        visibleCount !== 0
      );
    }

    renderCategoryButtons();
  }


  function initializeCatalogFilters() {
    categoryButtons.forEach(
      (button) => {
        button.addEventListener(
          "click",
          () => {
            filterState.category = (
              button.dataset.catalogCategory
              || "all"
            );

            applyCatalogFilters();
          }
        );
      }
    );

    if (searchInput) {
      searchInput.addEventListener(
        "input",
        () => {
          filterState.query = (
            normalizeSearchValue(
              searchInput.value
            )
          );

          applyCatalogFilters();
        }
      );
    }

    applyCatalogFilters();
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


  function offerKey(
    commercialPriceId
  ) {
    return commercialPriceId === null
      ? ""
      : String(
          commercialPriceId
        );
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


  function selectedCommercialPriceId(
    card
  ) {
    const select = card.querySelector(
      "[data-catalog-offer-select]"
    );

    if (select) {
      return select.value === ""
        ? null
        : Number(
            select.value
          );
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

    cards.forEach(
      (card) => {
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
      }
    );
  }


  function resetQuantityInput(
    form
  ) {
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


  function openQuantityMode(
    form
  ) {
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


  function isQuantityModeOpen(
    form
  ) {
    const quantityState = form.querySelector(
      "[data-catalog-purchase-quantity]"
    );

    return Boolean(
      quantityState
      && !quantityState.hidden
    );
  }


  async function submitAddForm(
    form
  ) {
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
          body: new FormData(
            form
          ),
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

      confirmButton.disabled =
        false;

      setFeedback(
        error instanceof Error
          ? error.message
          : fallbackErrorMessage
      );
    }
  }


  function initializePurchaseControls() {
    forms.forEach(
      (form) => {
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

            if (
              !form.checkValidity()
            ) {
              form.reportValidity();
              return;
            }

            void submitAddForm(
              form
            );
          }
        );
      }
    );
  }


  initializeCatalogFilters();

  initializeOfferControls(
    parseCatalogData()
  );

  initializePurchaseControls();
})();
