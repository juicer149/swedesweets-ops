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

  const sortButtons = Array.from(
    historyRoot.querySelectorAll(
      "[data-order-sort]"
    )
  );

  const sortHeadings = Array.from(
    historyRoot.querySelectorAll(
      "[data-order-sort-heading]"
    )
  );

  const sortSelect = historyRoot.querySelector(
    "[data-order-sort-select]"
  );

  const sortDirectionButton = (
    historyRoot.querySelector(
      "[data-order-sort-direction]"
    )
  );

  const tableBody = historyRoot.querySelector(
    "[data-order-table-body]"
  );

  const cardList = historyRoot.querySelector(
    "[data-order-card-list]"
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

  const sortState = {
    field: "status",
    direction: "asc",
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


  function renderOrderVisibility() {
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


  function numericValue(
    value
  ) {
    const number = Number(
      value
    );

    if (Number.isFinite(number)) {
      return number;
    }

    return 0;
  }


  function createdValue(
    item
  ) {
    const timestamp = Date.parse(
      item.dataset.orderCreated
    );

    if (Number.isFinite(timestamp)) {
      return timestamp;
    }

    return 0;
  }


  function primarySortValue(
    item
  ) {
    switch (sortState.field) {
      case "order":
        return numericValue(
          item.dataset.orderId
        );

      case "created":
        return createdValue(
          item
        );

      case "status":
        return numericValue(
          item.dataset.orderStatusRank
        );

      case "quantity":
        return numericValue(
          item.dataset.orderQuantity
        );

      default:
        return 0;
    }
  }


  function compareValues(
    left,
    right
  ) {
    if (left < right) {
      return -1;
    }

    if (left > right) {
      return 1;
    }

    return 0;
  }


  function compareOrderItems(
    left,
    right
  ) {
    const directionMultiplier = (
      sortState.direction === "asc"
        ? 1
        : -1
    );

    const primaryComparison = (
      compareValues(
        primarySortValue(left),
        primarySortValue(right)
      )
    );

    if (primaryComparison !== 0) {
      return (
        primaryComparison
        * directionMultiplier
      );
    }

    const leftId = numericValue(
      left.dataset.orderId
    );

    const rightId = numericValue(
      right.dataset.orderId
    );

    const idComparison = (
      compareValues(
        leftId,
        rightId
      )
    );

    if (sortState.field === "status") {
      return -idComparison;
    }

    return (
      idComparison
      * directionMultiplier
    );
  }


  function placeItemsInOrder(
    items,
    parent,
    emptyState
  ) {
    if (!parent) {
      return;
    }

    const sortedItems = (
      [...items].sort(
        compareOrderItems
      )
    );

    sortedItems.forEach(
      (item) => {
        if (emptyState) {
          parent.insertBefore(
            item,
            emptyState
          );
        } else {
          parent.appendChild(
            item
          );
        }
      }
    );
  }


  function renderSortButtons() {
    sortButtons.forEach(
      (button) => {
        const isActive = (
          button.dataset.orderSort
          === sortState.field
        );

        const arrow = (
          button.querySelector(
            "[data-order-sort-arrow]"
          )
        );

        button.classList.toggle(
          "text-link--active",
          isActive
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

        if (arrow) {
          arrow.textContent = (
            isActive
              ? (
                  sortState.direction
                    === "asc"
                    ? "↑"
                    : "↓"
                )
              : ""
          );
        }
      }
    );
  }


  function renderSortHeadings() {
    sortHeadings.forEach(
      (heading) => {
        const isActive = (
          heading.dataset.orderSortHeading
          === sortState.field
        );

        if (isActive) {
          heading.setAttribute(
            "aria-sort",
            sortState.direction
              === "asc"
              ? "ascending"
              : "descending"
          );
        } else {
          heading.removeAttribute(
            "aria-sort"
          );
        }
      }
    );
  }


  function renderMobileSortControls() {
    if (sortSelect) {
      sortSelect.value = (
        sortState.field
      );
    }

    if (sortDirectionButton) {
      sortDirectionButton.textContent = (
        sortState.direction === "asc"
          ? "↓"
          : "↑"
      );
    }
  }


  function renderSortControls() {
    renderSortButtons();
    renderSortHeadings();
    renderMobileSortControls();
  }


  function applyFilter() {
    renderOrderVisibility();
    renderFilterButtons();
  }


  function applySort() {
    placeItemsInOrder(
      rows,
      tableBody,
      tableEmptyState
    );

    placeItemsInOrder(
      cards,
      cardList,
      cardEmptyState
    );

    renderSortControls();
  }


  function setSortField(
    field
  ) {
    if (field === sortState.field) {
      sortState.direction = (
        sortState.direction === "asc"
          ? "desc"
          : "asc"
      );
    } else {
      sortState.field = field;
      sortState.direction = "asc";
    }

    applySort();
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
  }


  function initializeDesktopSort() {
    sortButtons.forEach(
      (button) => {
        button.addEventListener(
          "click",
          () => {
            setSortField(
              button.dataset.orderSort
            );
          }
        );
      }
    );
  }


  function initializeMobileSort() {
    if (sortSelect) {
      sortSelect.addEventListener(
        "change",
        () => {
          sortState.field = (
            sortSelect.value
          );

          applySort();
        }
      );
    }

    if (sortDirectionButton) {
      sortDirectionButton.addEventListener(
        "click",
        () => {
          sortState.direction = (
            sortState.direction === "asc"
              ? "desc"
              : "asc"
          );

          applySort();
        }
      );
    }
  }


  function initializeOrderHistory() {
    initializeFilters();
    initializeDesktopSort();
    initializeMobileSort();

    applySort();
    applyFilter();
  }


  initializeOrderHistory();
})();
