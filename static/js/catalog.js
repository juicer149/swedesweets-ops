(() => {
  const forms = document.querySelectorAll(
    "[data-catalog-add-form]"
  );
  const feedback = document.querySelector(
    "[data-catalog-feedback]"
  );
  const catalogDataElement = document.getElementById(
    "business-catalog-data"
  );

  if (!forms.length) {
    return;
  }

  function setFeedback(message) {
    if (!feedback) {
      return;
    }

    feedback.textContent = message;
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

    if (!input || input.value === "") {
      return null;
    }

    return Number(input.value);
  }

  function renderOffer(card, offer) {
    const badge = card.querySelector(
      "[data-catalog-offer-badge]"
    );
    const price = card.querySelector(
      "[data-catalog-offer-price]"
    );
    const availability = card.querySelector(
      "[data-catalog-offer-availability]"
    );

    if (badge) {
      badge.textContent =
        offer && offer.badge_label
          ? offer.badge_label
          : "";

      badge.hidden = !(
        offer && offer.badge_label
      );
    }

    if (price) {
      price.textContent =
        offer && offer.price_label
          ? offer.price_label
          : "";
    }

    if (availability) {
      availability.textContent = offer
        ? `${offer.available_units} available`
        : "";
    }
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
        const productId =
          card.dataset.productId;

        const catalogProduct =
          catalogByProductId.get(
            productId
          );

        if (!catalogProduct) {
          return;
        }

        const renderSelectedOffer = () => {
          const commercialPriceId =
            selectedCommercialPriceId(
              card
            );

          const offer = findOffer(
            catalogProduct,
            commercialPriceId
          );

          renderOffer(
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

  async function submitAddForm(form) {
    const button = form.querySelector(
      "[data-catalog-add-button]"
    );

    if (!button) {
      return;
    }

    const originalLabel =
      button.textContent.trim();

    button.disabled = true;

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

      const payload =
        await response.json();

      if (!response.ok || !payload.ok) {
        throw new Error(
          payload.message ||
            "Could not add product."
        );
      }

      button.textContent = "Added";
      setFeedback(
        payload.message
      );

      window.setTimeout(() => {
        button.textContent =
          originalLabel;
        button.disabled = false;
      }, 1000);
    } catch (error) {
      button.textContent =
        originalLabel;
      button.disabled = false;

      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not add product."
      );
    }
  }

  const catalogProducts =
    parseCatalogData();

  initializeOfferControls(
    catalogProducts
  );

  forms.forEach((form) => {
    form.addEventListener(
      "submit",
      (event) => {
        event.preventDefault();

        submitAddForm(
          form
        );
      }
    );
  });
})();
