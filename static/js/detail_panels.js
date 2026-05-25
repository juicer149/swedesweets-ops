document.addEventListener("DOMContentLoaded", () => {
  const groups = document.querySelectorAll("[data-detail-panels]");

  groups.forEach((group) => {
    const triggers = Array.from(
      group.querySelectorAll("[data-detail-panel-trigger]")
    );

    const bodies = Array.from(
      group.querySelectorAll("[data-detail-panel-body]")
    );

    function closeAllPanels() {
      triggers.forEach((trigger) => {
        trigger.classList.remove("detail-panel-trigger--active");
        trigger.setAttribute("aria-expanded", "false");
      });

      bodies.forEach((body) => {
        body.classList.remove("detail-panel-body--active");
        body.hidden = true;
      });
    }

    function openPanel(activeKey) {
      triggers.forEach((trigger) => {
        const isActive = trigger.dataset.detailPanelKey === activeKey;

        trigger.classList.toggle("detail-panel-trigger--active", isActive);
        trigger.setAttribute("aria-expanded", String(isActive));
      });

      bodies.forEach((body) => {
        const isActive = body.dataset.detailPanelKey === activeKey;

        body.classList.toggle("detail-panel-body--active", isActive);
        body.hidden = !isActive;
      });
    }

    triggers.forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const isOpen = trigger.getAttribute("aria-expanded") === "true";

        if (isOpen) {
          closeAllPanels();
          return;
        }

        openPanel(trigger.dataset.detailPanelKey);
      });
    });
  });
});
