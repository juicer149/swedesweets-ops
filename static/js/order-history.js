(() => {
  "use strict";

  const historyRoot = document.querySelector(
    "[data-order-history]"
  );

  if (!historyRoot) {
    return;
  }

  const filterButtons = Array.from(
    historyRoot.querySelectorAll(
      "[data-order-filter]"
    )
  );

  const rows = Array.from(
    historyRoot.querySelectorAll(
      "[data-order-row]"
    )
  );

  const cards = Array.from(
    historyRoot.querySelectorAll(
      "[data-order-card]"
    )
  );

  const tableEmptyState = (
    historyRoot.querySelector(
      "[data-order-filter-empty]"
    )
  );

  const cardEmptyState = (
    historyRoot.querySelector(
      "[data-order-card-filter-empty]"
    )
  );

  const filterState = {
    status: "",
  };


  function matchesActiveFilter(
    item
  ) {
    return (
      !filterState.status
      || item.dataset.orderStatus
        === filterState.status
    );
  }


  function renderFilterButtons() {
    filterButtons.forEach(
      (button) => {
        const isActive = (
          button.dataset.orderFilter
          === filterState.status
        );

        button.setAttribute(
          "aria-pressed",
          String(isActive)
        );

        if (isActive) {
          button.setAttribute(
            "aria-current",
            "page"
          );
        } else {
          button.removeAttribute(
            "aria-current"
          );
        }
      }
    );
  }


  function renderOrderItems() {
    let visibleCount = 0;

    rows.forEach(
      (row) => {
        const isVisible = (
          matchesActiveFilter(
            row
          )
        );

        row.hidden = !isVisible;

        if (isVisible) {
          visibleCount += 1;
        }
      }
    );

    cards.forEach(
      (card) => {
        card.hidden = !matchesActiveFilter(
          card
        );
      }
    );

    const hasVisibleOrders = (
      visibleCount > 0
    );

    if (tableEmptyState) {
      tableEmptyState.hidden = (
        hasVisibleOrders
      );
    }

    if (cardEmptyState) {
      cardEmptyState.hidden = (
        hasVisibleOrders
      );
    }
  }


  function applyFilter() {
    renderOrderItems();
    renderFilterButtons();
  }


  function initializeFilters() {
    filterButtons.forEach(
      (button) => {
        button.addEventListener(
          "click",
          () => {
            filterState.status = (
              button.dataset.orderFilter
              || ""
            );

            applyFilter();
          }
        );
      }
    );

    applyFilter();
  }


  initializeFilters();
})();
