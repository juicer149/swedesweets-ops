(() => {
  "use strict";

  const ASYNC_TRIGGER_SELECTOR = [
    "[data-async-list] .filter-chip",
    "[data-async-list] .text-link--table-sort",
  ].join(", ");

  function findAsyncSection(node) {
    return node.closest("[data-async-list]");
  }

  function reinitializeSection(section) {
    if (window.enhanceSelects) {
      window.enhanceSelects(section);
    }

    if (window.setupQuickJumps) {
      window.setupQuickJumps(section);
    }
  }

  async function swapSection(section, url) {
    section.setAttribute("aria-busy", "true");

    let html;

    try {
      const response = await fetch(url, {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      if (!response.ok) {
        window.location.href = url;
        return;
      }

      html = await response.text();
    } catch {
      window.location.href = url;
      return;
    }

    const nextDocument = new DOMParser().parseFromString(
      html,
      "text/html"
    );

    const nextSection = nextDocument.getElementById(section.id);

    if (!nextSection) {
      window.location.href = url;
      return;
    }

    section.replaceWith(nextSection);
    reinitializeSection(nextSection);
  }

  function navigate(url, { pushState = true } = {}) {
    const section = document.querySelector("[data-async-list]");

    if (!section) {
      return;
    }

    if (pushState) {
      window.history.pushState({ asyncList: true }, "", url);
    }

    swapSection(section, url);
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest(ASYNC_TRIGGER_SELECTOR);

    if (!trigger) {
      return;
    }

    event.preventDefault();
    navigate(trigger.href);
  });

  document.addEventListener("change", (event) => {
    const select = event.target.closest(
      "[data-async-list] select.sort-select"
    );

    if (!select || !select.value) {
      return;
    }

    event.preventDefault();
    navigate(select.value);
  });

  document.addEventListener("click", (event) => {
    const directionButton = event.target.closest(
      "[data-async-list] .sort-direction-button"
    );

    if (!directionButton) {
      return;
    }

    event.preventDefault();
    navigate(directionButton.href);
  });

  window.addEventListener("popstate", () => {
    const section = document.querySelector("[data-async-list]");

    if (!section) {
      return;
    }

    swapSection(section, window.location.href);
  });
})();
