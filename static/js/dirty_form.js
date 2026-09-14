document.addEventListener("DOMContentLoaded", () => {
  const orderLinesList = document.querySelector("[data-order-lines-list]");
  const orderLinesWrapper = document.querySelector(
    "[data-order-lines-wrapper]"
  );
  const emptyState = document.querySelector("[data-order-lines-empty]");
  const emptyFormTemplate = document.getElementById(
    "order-line-empty-form-template"
  );
  const addProductSelect = document.querySelector(
    "[data-add-order-line-select]"
  );
  const totalFormsInput = document.querySelector(
    'input[name="lines-TOTAL_FORMS"]'
  );

  if (
    !orderLinesList ||
    !emptyFormTemplate ||
    !addProductSelect ||
    !totalFormsInput
  ) {
    return;
  }

  function getOrderLines() {
    return Array.from(orderLinesList.querySelectorAll("[data-order-line]"));
  }

  function findOrderLineByProductId(productId) {
    return orderLinesList.querySelector(
      `[data-order-line][data-product-id="${productId}"]`
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

  /*
   * order_lines.js adds/removes whole fields without firing input/change
   * on anything dirty_form.js's field-level listeners would see (a new
   * line's fields are populated directly, not via user interaction; a
   * removed line just disappears via element.remove()). This lets
   * dirty_form.js, when present on the same <form>, notice those
   * structural changes explicitly.
   */
  function notifyDirtyFormRefresh() {
    const form = orderLinesList.closest("form");

    if (form) {
      form.dispatchEvent(
        new Event("dirty-form:refresh", { bubbles: true })
      );
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

  function clearAddProductSelect() {
    const tomSelect = addProductSelect.tomselect;

    if (tomSelect) {
      tomSelect.clear(true);
      return;
    }

    addProductSelect.value = "";
  }

  /*
   * Reads the currently selected product straight from the TomSelect
   * instance's own option data (already fully loaded client-side by
   * enhanced_selects.js at init - no fetch needed). Falls back to the
   * native <option> element if TomSelect never initialized (e.g. the
   * library failed to load).
   */
  function readSelectedProduct(value) {
    const tomSelect = addProductSelect.tomselect;

    if (tomSelect) {
      const data = tomSelect.options[value];

      if (!data) {
        return null;
      }

      const label = data.name
        ? `${data.code} · ${data.name} · ${data.weight}`.trim()
        : data.text;

      return { value, label };
    }

    const option = addProductSelect.selectedOptions[0];

    if (!option || !option.value) {
      return null;
    }

    const label = option.dataset.name
      ? `${option.dataset.code} · ${option.dataset.name} · ${option.dataset.weight}`
      : option.textContent.trim();

    return { value: option.value, label };
  }

  function addOrIncrementLine(product) {
    if (!product || !product.value) {
      return;
    }

    const existingLine = findOrderLineByProductId(product.value);

    if (existingLine) {
      incrementQuantity(existingLine);
      clearAddProductSelect();
      notifyDirtyFormRefresh();
      return;
    }

    const index = getOrderLines().length;
    const orderLine = buildOrderLine(index);

    orderLine.dataset.productId = product.value;

    const productInput = orderLine.querySelector(
      "[data-order-line-product-input]"
    );
    const labelElement = orderLine.querySelector(
      "[data-order-line-product-label]"
    );
    const quantityInput = orderLine.querySelector(
      "[data-quantity-input]"
    );

    if (productInput) {
      productInput.value = product.value;
    }

    if (labelElement) {
      labelElement.textContent = product.label;
    }

    if (quantityInput) {
      quantityInput.value = "1";
    }

    orderLinesList.appendChild(orderLine);
    totalFormsInput.value = String(index + 1);

    clearAddProductSelect();
    updateEmptyState();
    notifyDirtyFormRefresh();
    scrollOrderLineIntoView(orderLine);
  }

  function handleProductSelected(value) {
    if (!value) {
      return;
    }

    addOrIncrementLine(readSelectedProduct(value));
  }

  /*
   * enhanced_selects.js initializes TomSelect on DOMContentLoaded too,
   * and its script tag loads before this one, so addProductSelect.tomselect
   * is already available here. Prefer TomSelect's own change event
   * (fires with the new value directly) over the native <select> change
   * event, since TomSelect's internal option sync is the source of truth
   * this file should read from.
   */
  if (addProductSelect.tomselect) {
    addProductSelect.tomselect.on("change", handleProductSelected);
  } else {
    addProductSelect.addEventListener("change", () => {
      handleProductSelected(addProductSelect.value);
    });
  }

  orderLinesList.addEventListener("click", (event) => {
    const removeButton = event.target.closest(
      "[data-remove-order-line]"
    );

    if (!removeButton) {
      return;
    }

    const orderLine = removeButton.closest("[data-order-line]");

    if (!orderLine) {
      return;
    }

    orderLine.remove();

    syncFormsetIndexes();
    updateEmptyState();
    notifyDirtyFormRefresh();
  });

  updateEmptyState();
});
