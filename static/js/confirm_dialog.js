"use strict";

/*
 * Native <dialog>-based replacement for window.confirm(), styled to match
 * the site instead of the browser's unstyleable native prompt.
 *
 * Usage: const left = await window.confirmDialog("Are you sure?", {
 *   title: "Leave page",
 *   confirmLabel: "Leave without saving",
 *   cancelLabel: "Stay on this page",
 * });
 */

(() => {
  if (window.confirmDialog) {
    return;
  }

  let dialogElement = null;
  let titleElement = null;
  let messageElement = null;
  let confirmButton = null;
  let cancelButton = null;
  let activeResolve = null;

  function settle(value) {
    if (!activeResolve) {
      return;
    }

    const resolve = activeResolve;
    activeResolve = null;
    resolve(value);
  }

  function buildDialog() {
    const dialog = document.createElement("dialog");
    dialog.className = "confirm-dialog";

    dialog.innerHTML = `
      <div class="confirm-dialog__card">
        <h2 class="confirm-dialog__title" data-confirm-dialog-title></h2>
        <p class="confirm-dialog__message" data-confirm-dialog-message></p>
        <div class="confirm-dialog__actions">
          <button
            type="button"
            class="button button--md button--ghost button--tone-neutral"
            data-confirm-dialog-cancel
          ></button>
          <button
            type="button"
            class="button button--md button--solid button--tone-danger"
            data-confirm-dialog-confirm
          ></button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    /*
     * Fires on Escape (native <dialog> default cancel behavior) before
     * the dialog actually closes - resolve false here so Escape behaves
     * the same as clicking "Stay".
     */
    dialog.addEventListener("cancel", () => {
      settle(false);
    });

    /*
     * Clicking the backdrop (the dialog element itself, outside
     * .confirm-dialog__card) closes without confirming.
     */
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) {
        dialog.close();
      }
    });

    return dialog;
  }

  function ensureDialog() {
    if (dialogElement) {
      return dialogElement;
    }

    dialogElement = buildDialog();
    titleElement = dialogElement.querySelector(
      "[data-confirm-dialog-title]"
    );
    messageElement = dialogElement.querySelector(
      "[data-confirm-dialog-message]"
    );
    confirmButton = dialogElement.querySelector(
      "[data-confirm-dialog-confirm]"
    );
    cancelButton = dialogElement.querySelector(
      "[data-confirm-dialog-cancel]"
    );

    confirmButton.addEventListener("click", () => {
      dialogElement.close();
      settle(true);
    });

    cancelButton.addEventListener("click", () => {
      dialogElement.close();
      settle(false);
    });

    return dialogElement;
  }

  window.confirmDialog = function confirmDialog(message, options = {}) {
    const dialog = ensureDialog();

    titleElement.textContent = options.title || "Unsaved changes";
    messageElement.textContent = message;
    confirmButton.textContent = (
      options.confirmLabel || "Leave without saving"
    );
    cancelButton.textContent = options.cancelLabel || "Stay on this page";

    return new Promise((resolve) => {
      activeResolve = resolve;
      dialog.showModal();
    });
  };
})();
