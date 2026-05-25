(function () {
  function enhanceSelects(root = document) {
    if (!window.TomSelect) {
      return;
    }

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
          ? '<input type="text" autocomplete="off" />'
          : null,
        searchField: ["text"],
        sortField: [{ field: "$order", direction: "asc" }],
      });

      tomSelect.wrapper.classList.add(
        hasSearch
          ? "enhanced-select--searchable"
          : "enhanced-select--static"
      );
    });
  }

  window.enhanceSelects = enhanceSelects;

  document.addEventListener("DOMContentLoaded", () => {
    enhanceSelects();
  });
})();
