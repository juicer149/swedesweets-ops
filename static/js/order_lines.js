document.addEventListener("DOMContentLoaded", () => {
  const orderLinesList = document.querySelector("[data-order-lines-list]");
  const orderLinesWrapper = document.querySelector(
    "[data-order-lines-wrapper]"
  );
  const emptyState = document.querySelector("[data-order-lines-empty]");
  const emptyFormTemplate = document.getElementById(
    "order-line-empty-form-template"
  );
  const addOfferSelect = document.querySelector(
    "[data-add-order-line-select]"
  );
  const totalFormsInput = document.querySelector(
    'input[name="lines-TOTAL_FORMS"]'
  );

  if (
    !orderLinesList ||
    !emptyFormTemplate ||
    !addOfferSelect ||
    !totalFormsInput
  ) {
    return;
  }

  function getOrderLines() {
    return Array.from(
      orderLinesList.querySelectorAll("[data-order-line]")
    );
  }

  function findOrderLineByOfferId(offerId) {
    return orderLinesList.querySelector(
      `[data-order-line][data-commercial-offer-id="${offerId}"]`
    );
  }

  function replaceFormIndex(value, index) {
    return value
      .replace(/lines-(\d+|__prefix__)-/g, `lines-${index}-`)
      .replace(/id_lines-(\d+|__prefix__)-/g, `id_lines-${index}-`);
  }

  function reindexOrderLine(orderLine, index) {
    orderLine.querySelectorAll("[name]").forEach((element) => {
      element.name = replaceFormIndex(element.name, index);
    });

    orderLine.querySelectorAll("[id]").forEach((element) => {
      element.id = replaceFormIndex(element.id, index);
    });

    orderLine.querySelectorAll("label[for]").forEach((label) => {
      label.htmlFor = replaceFormIndex(label.htmlFor, index);
    });

    const number = orderLine.querySelector("[data-order-line-number]");

    if (number) {
      number.textContent = String(index + 1);
    }
  }

  function syncFormsetIndexes() {
    const orderLines = getOrderLines();

    orderLines.forEach((orderLine, index) => {
      reindexOrderLine(orderLine, index);
    });

    totalFormsInput.value = String(orderLines.length);
  }

  function updateEmptyState() {
    const hasLines = getOrderLines().length > 0;

    if (orderLinesWrapper) {
      orderLinesWrapper.hidden = !hasLines;
    }

    if (emptyState) {
      emptyState.hidden = hasLines;
    }
  }

  function buildOrderLine(index) {
    const html = emptyFormTemplate.innerHTML
      .replaceAll("__prefix__", String(index))
      .replaceAll("__line_number__", String(index + 1));

    const wrapper = document.createElement("div");
    wrapper.innerHTML = html.trim();

    return wrapper.firstElementChild;
  }

  function scrollOrderLineIntoView(orderLine) {
    orderLine.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }

  function incrementQuantity(orderLine) {
    const input = orderLine.querySelector("[data-quantity-input]");

    if (!input) {
      return;
    }

    const current = Number(input.value);
    const next = Number.isFinite(current) ? current + 1 : 1;

    input.value = String(next);

    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function clearAddOfferSelect() {
    const tomSelect = addOfferSelect.tomselect;

    if (tomSelect) {
      tomSelect.clear(true);
      return;
    }

    addOfferSelect.value = "";
  }

  function buildOfferLabel(data) {
    const parts = [
      data.code,
      data.name,
      data.weight,
      data.offerDetail,
    ].filter(Boolean);

    return parts.length ? parts.join(" · ") : data.text;
  }

  function readSelectedOffer(value) {
    const tomSelect = addOfferSelect.tomselect;

    if (tomSelect) {
      const data = tomSelect.options[value];

      if (!data) {
        return null;
      }

      return {
        value,
        label: buildOfferLabel(data),
      };
    }

    const option = addOfferSelect.selectedOptions[0];

    if (!option || !option.value) {
      return null;
    }

    return {
      value: option.value,
      label: buildOfferLabel({
        code: option.dataset.code || "",
        name: option.dataset.name || "",
        weight: option.dataset.weight || "",
        offerDetail: option.dataset.offerDetail || "",
        text: option.textContent.trim(),
      }),
    };
  }

  function addOrIncrementLine(offer) {
    if (!offer || !offer.value) {
      return;
    }

    const existingLine = findOrderLineByOfferId(offer.value);

    if (existingLine) {
      incrementQuantity(existingLine);
      clearAddOfferSelect();
      return;
    }

    const index = getOrderLines().length;
    const orderLine = buildOrderLine(index);

    orderLine.dataset.commercialOfferId = offer.value;

    const offerInput = orderLine.querySelector(
      "[data-order-line-offer-input]"
    );
    const labelElement = orderLine.querySelector(
      "[data-order-line-offer-label]"
    );
    const quantityInput = orderLine.querySelector(
      "[data-quantity-input]"
    );

    if (offerInput) {
      offerInput.value = offer.value;
    }

    if (labelElement) {
      labelElement.textContent = offer.label;
    }

    if (quantityInput) {
      quantityInput.value = "1";
    }

    orderLinesList.appendChild(orderLine);
    totalFormsInput.value = String(index + 1);

    clearAddOfferSelect();
    updateEmptyState();
    scrollOrderLineIntoView(orderLine);
  }

  function handleOfferSelected(value) {
    if (!value) {
      return;
    }

    addOrIncrementLine(
      readSelectedOffer(value)
    );
  }

  if (addOfferSelect.tomselect) {
    addOfferSelect.tomselect.on(
      "change",
      handleOfferSelected
    );
  } else {
    addOfferSelect.addEventListener(
      "change",
      () => {
        handleOfferSelected(
          addOfferSelect.value
        );
      }
    );
  }

  orderLinesList.addEventListener("click", (event) => {
    const removeButton = event.target.closest(
      "[data-remove-order-line]"
    );

    if (!removeButton) {
      return;
    }

    const orderLine = removeButton.closest(
      "[data-order-line]"
    );

    if (!orderLine) {
      return;
    }

    orderLine.remove();

    syncFormsetIndexes();
    updateEmptyState();
  });

  updateEmptyState();
});
