(function () {
  function isTouchLikeDevice() {
    return (
      window.matchMedia("(pointer: coarse)").matches ||
      window.matchMedia("(hover: none)").matches
    );
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
        create: false,
        allowEmptyOption: true,
        closeAfterSelect: true,
        maxOptions: 500,
        placeholder: select.getAttribute("placeholder") || "",
        controlInput: hasSearch
          ? '<input type="text" autocomplete="off" autocapitalize="none" spellcheck="false" />'
          : null,
        searchField: ["text"],
        sortField: [{ field: "$order", direction: "asc" }],
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
