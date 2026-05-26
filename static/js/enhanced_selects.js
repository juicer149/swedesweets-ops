(function () {
  function isTouchLikeDevice() {
    return (
      window.matchMedia("(pointer: coarse)").matches ||
      window.matchMedia("(hover: none)").matches
    );
  }

  function optionText(option) {
    return option.textContent.trim();
  }

  function optionSearchText(option) {
    return option.getAttribute("search") || option.dataset.search || optionText(option);
  }

  function buildOptionData(option) {
    return {
      value: option.value,
      text: optionText(option),
      code: option.dataset.code || "",
      name: option.dataset.name || "",
      weight: option.dataset.weight || "",
      search: optionSearchText(option),
    };
  }

  function buildOptions(select) {
    return Array.from(select.options).map(buildOptionData);
  }

  function buildItems(select) {
    return select.value ? [select.value] : [];
  }

  function hasProductData(data) {
    return Boolean(data.code || data.name || data.weight);
  }

  function productTitle(data, escape) {
    const code = data.code || "";
    const name = data.name || data.text || "";

    if (code && name) {
      return `${escape(code)} · ${escape(name)}`;
    }

    return escape(code || name);
  }

  function renderOption(data, escape) {
    if (!hasProductData(data)) {
      return `<div class="enhanced-select-option">${escape(data.text)}</div>`;
    }

    return `
      <div class="enhanced-product-option">
        <div class="enhanced-product-option__main">
          ${productTitle(data, escape)}
        </div>

        ${
          data.weight
            ? `<div class="enhanced-product-option__meta">${escape(data.weight)}</div>`
            : ""
        }
      </div>
    `;
  }

  function renderItem(data, escape) {
    if (!hasProductData(data)) {
      return `<div>${escape(data.text)}</div>`;
    }

    return `
      <div class="enhanced-product-selected">
        <span>${productTitle(data, escape)}</span>
      </div>
    `;
  }

  function enhanceSelects(root = document, options = {}) {
    if (!window.TomSelect) {
      return;
    }

    const shouldOpenAfterEnhance = options.openAfterEnhance === true;
    const selects = root.querySelectorAll("select[data-enhanced-select]");

    selects.forEach((select) => {
      if (select.tomselect) {
        return;
      }

      const hasSearch = select.dataset.enhancedSelectSearch !== "false";

      const tomSelect = new TomSelect(select, {
        options: buildOptions(select),
        items: buildItems(select),
        create: false,
        allowEmptyOption: true,
        closeAfterSelect: true,
        maxOptions: 500,
        placeholder: select.getAttribute("placeholder") || "",
        controlInput: hasSearch
          ? '<input type="text" autocomplete="off" autocapitalize="none" spellcheck="false" />'
          : null,
        searchField: ["search"],
        sortField: [{ field: "$order", direction: "asc" }],
        render: {
          option: renderOption,
          item: renderItem,
        },
      });

      tomSelect.wrapper.classList.add(
        hasSearch
          ? "enhanced-select--searchable"
          : "enhanced-select--static"
      );

      if (!shouldOpenAfterEnhance) {
        tomSelect.close();

        if (isTouchLikeDevice()) {
          tomSelect.blur();
        }
      }
    });
  }

  window.enhanceSelects = enhanceSelects;

  document.addEventListener("DOMContentLoaded", () => {
    enhanceSelects();
  });
})();
