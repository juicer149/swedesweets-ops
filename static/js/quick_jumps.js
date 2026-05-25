(function () {
  function setupQuickJumps(root = document) {
    const quickJumps = root.querySelectorAll("select[data-quick-jump]");

    quickJumps.forEach((select) => {
      if (select.dataset.quickJumpReady === "true") {
        return;
      }

      select.dataset.quickJumpReady = "true";

      select.addEventListener("change", () => {
        const targetUrl = select.value;

        if (targetUrl) {
          window.location.href = targetUrl;
        }
      });
    });
  }

  window.setupQuickJumps = setupQuickJumps;

  document.addEventListener("DOMContentLoaded", () => {
    setupQuickJumps();
  });
})();
