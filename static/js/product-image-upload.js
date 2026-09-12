(() => {
  "use strict";

  const fields = document.querySelectorAll(
    "[data-product-image-field]",
  );

  if (!fields.length) {
    return;
  }

  for (const field of fields) {
    initializeProductImageField(field);
  }

  function initializeProductImageField(root) {
    const input = root.querySelector(
      'input[type="file"]',
    );

    const selectButton = root.querySelector(
      "[data-product-image-select]",
    );

    const selectLabel = root.querySelector(
      "[data-product-image-select-label]",
    );

    const preview = root.querySelector(
      "[data-product-image-preview]",
    );

    const previewImage = root.querySelector(
      "[data-product-image-preview-image]",
    );

    const emptyState = root.querySelector(
      "[data-product-image-empty]",
    );

    const removeInput = root.querySelector(
      'input[name="remove_image"]',
    );

    if (
      !input
      || !selectButton
      || !selectLabel
      || !preview
      || !previewImage
      || !emptyState
    ) {
      return;
    }

    const originalImageUrl =
      previewImage.getAttribute("src") || "";

    let objectUrl = null;

    function revokeObjectUrl() {
      if (!objectUrl) {
        return;
      }

      URL.revokeObjectURL(
        objectUrl,
      );

      objectUrl = null;
    }

    function showPreview(url) {
      previewImage.src = url;
      preview.hidden = false;
      emptyState.hidden = true;
    }

    function showEmptyState() {
      previewImage.removeAttribute(
        "src",
      );

      preview.hidden = true;
      emptyState.hidden = false;
    }

    function showSelectedFile(file) {
      revokeObjectUrl();

      objectUrl = URL.createObjectURL(
        file,
      );

      showPreview(
        objectUrl,
      );

      selectLabel.textContent =
        "Replace image";
    }

    function restoreOriginalState() {
      revokeObjectUrl();

      if (originalImageUrl) {
        showPreview(
          originalImageUrl,
        );

        selectLabel.textContent =
          "Replace image";

        return;
      }

      showEmptyState();

      selectLabel.textContent =
        "Choose image";
    }

    selectButton.addEventListener(
      "click",
      () => {
        input.click();
      },
    );

    input.addEventListener(
      "change",
      () => {
        const [file] = input.files;

        if (!file) {
          restoreOriginalState();
          return;
        }

        if (removeInput) {
          removeInput.checked = false;
        }

        showSelectedFile(
          file,
        );
      },
    );

    if (removeInput) {
      removeInput.addEventListener(
        "change",
        () => {
          if (!removeInput.checked) {
            const [file] = input.files;

            if (file) {
              showSelectedFile(
                file,
              );

              return;
            }

            restoreOriginalState();
            return;
          }

          input.value = "";

          revokeObjectUrl();
          showEmptyState();

          selectLabel.textContent =
            "Choose image";
        },
      );
    }

    window.addEventListener(
      "beforeunload",
      revokeObjectUrl,
    );
  }
})();
