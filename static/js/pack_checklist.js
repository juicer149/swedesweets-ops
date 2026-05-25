document.addEventListener("DOMContentLoaded", () => {
  const checklist = document.querySelector("[data-pack-checklist]");
  const confirmButton = document.querySelector(
    '[data-action-behavior="pack-checklist"]'
  );

  if (!checklist || !confirmButton) {
    return;
  }

  const checkboxes = Array.from(
    checklist.querySelectorAll("[data-pack-line-checkbox]")
  );

  if (checkboxes.length === 0) {
    confirmButton.disabled = true;
    return;
  }

  function allLinesChecked() {
    return checkboxes.every((checkbox) => checkbox.checked);
  }

  function syncConfirmButton() {
    confirmButton.disabled = !allLinesChecked();
  }

  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", syncConfirmButton);
  });

  syncConfirmButton();
});
