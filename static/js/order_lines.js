document.addEventListener("DOMContentLoaded", () => {
  const orderLinesList = document.querySelector("[data-order-lines-list]");
  const emptyFormTemplate = document.getElementById(
    "order-line-empty-form-template"
  );
  const addProductButton = document.querySelector("[data-add-order-line]");
  const totalFormsInput = document.querySelector(
    'input[name="lines-TOTAL_FORMS"]'
  );

  if (
    !orderLinesList ||
    !emptyFormTemplate ||
    !addProductButton ||
    !totalFormsInput
  ) {
    return;
  }

  function getOrderLines() {
    return Array.from(orderLinesList.querySelectorAll("[data-order-line]"));
  }

  function fieldKey(element) {
    const match = element.name.match(/^lines-(?:\d+|__prefix__)-(.+)$/);
    return match ? match[1] : element.name;
  }

  function readFieldValue(element) {
    if (element.type === "radio") {
      return element.checked ? element.value : null;
    }

    if (element.type === "checkbox") {
      return element.checked;
    }

    if (element.tomselect) {
      return element.tomselect.getValue();
    }

    return element.value;
  }

  function writeFieldValue(element, value) {
    if (value === undefined || value === null) {
      return;
    }

    if (element.type === "radio") {
      element.checked = element.value === value;
      return;
    }

    if (element.type === "checkbox") {
      element.checked = Boolean(value);
      return;
    }

    if (element.tomselect) {
      element.tomselect.setValue(value, true);
      return;
    }

    element.value = value;

    if (element.tagName === "SELECT") {
      Array.from(element.options).forEach((option) => {
        option.selected = option.value === value;
      });
    }
  }

  function readOrderLineState(orderLine) {
    const state = {};

    orderLine
      .querySelectorAll("select[name], textarea[name], input[name]")
      .forEach((element) => {
        const key = fieldKey(element);
        const value = readFieldValue(element);

        if (element.type === "radio") {
          if (value !== null) {
            state[key] = value;
          }

          return;
        }

        state[key] = value;
      });

    return state;
  }

  function writeOrderLineState(orderLine, state) {
    orderLine
      .querySelectorAll("select[name], textarea[name], input[name]")
      .forEach((element) => {
        writeFieldValue(element, state[fieldKey(element)]);
      });
  }

  function destroyEnhancedSelects(root) {
    root.querySelectorAll("select[data-enhanced-select]").forEach((select) => {
      if (select.tomselect) {
        select.tomselect.destroy();
      }
    });
  }

  function enhanceOrderLine(orderLine) {
    window.enhanceSelects?.(orderLine);
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
    const states = orderLines.map(readOrderLineState);

    orderLines.forEach(destroyEnhancedSelects);

    orderLines.forEach((orderLine, index) => {
      reindexOrderLine(orderLine, index);
      writeOrderLineState(orderLine, states[index]);
    });

    totalFormsInput.value = String(orderLines.length);

    orderLines.forEach((orderLine, index) => {
      enhanceOrderLine(orderLine);
      writeOrderLineState(orderLine, states[index]);
    });

    updateRemoveButtons();
  }

  function updateRemoveButtons() {
    const orderLines = getOrderLines();
    const canRemove = orderLines.length > 1;

    orderLines.forEach((orderLine) => {
      const removeButton = orderLine.querySelector("[data-remove-order-line]");

      if (removeButton) {
        removeButton.hidden = !canRemove;
      }
    });
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

  addProductButton.addEventListener("click", () => {
    const index = getOrderLines().length;
    const orderLine = buildOrderLine(index);

    orderLinesList.appendChild(orderLine);
    totalFormsInput.value = String(index + 1);

    enhanceOrderLine(orderLine);
    updateRemoveButtons();
    scrollOrderLineIntoView(orderLine);
  });

  orderLinesList.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-order-line]");

    if (!removeButton) {
      return;
    }

    const orderLines = getOrderLines();

    if (orderLines.length <= 1) {
      return;
    }

    const orderLine = removeButton.closest("[data-order-line]");

    if (!orderLine) {
      return;
    }

    destroyEnhancedSelects(orderLine);
    orderLine.remove();

    syncFormsetIndexes();
  });

  updateRemoveButtons();
});
