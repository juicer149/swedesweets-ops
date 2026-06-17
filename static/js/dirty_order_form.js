(() => {
  const form = document.querySelector("[data-dirty-order-form]");

  if (!form) {
    return;
  }

  const dialog = document.querySelector("[data-dirty-dialog]");
  const nextInput = form.querySelector("[data-dirty-next-url]");
  const saveSubmitButton = form.querySelector("[data-dirty-save-submit]");
  const saveContinueButton = document.querySelector("[data-dirty-save-continue]");
  const leaveButton = document.querySelector("[data-dirty-leave]");
  const stayButton = document.querySelector("[data-dirty-stay]");

  let isDirty = false;
  let isSubmitting = false;
  let pendingHref = "";
  let initialOrderState = "";

  function orderLineState() {
    return [...form.querySelectorAll("[data-order-line]")]
      .map((row) => {
        const product = row.querySelector('select[name$="-product"]')?.value ?? "";
        const quantity = row.querySelector('input[name$="-quantity"]')?.value ?? "";

        return {
          product: product.trim(),
          quantity: quantity.trim(),
        };
      })
      .filter((line) => line.product || line.quantity);
  }

  function serializedOrderState() {
    return JSON.stringify(orderLineState());
  }

  function handleBeforeUnload(event) {
    if (!isDirty || isSubmitting) {
      return;
    }

    event.preventDefault();
    event.returnValue = "";
  }

  function setDirty(value) {
    if (isDirty === value) {
      return;
    }

    isDirty = value;

    if (isDirty) {
      window.addEventListener("beforeunload", handleBeforeUnload);
    } else {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    }
  }

  function refreshDirtyState() {
    if (isSubmitting) {
      return;
    }

    setDirty(serializedOrderState() !== initialOrderState);
  }

  function resetInitialState() {
    initialOrderState = serializedOrderState();
    setDirty(false);
  }

  function isEditableOrderField(element) {
    if (!(element instanceof HTMLElement)) {
      return false;
    }

    if (!form.contains(element)) {
      return false;
    }

    if (!element.matches("input, select, textarea")) {
      return false;
    }

    if (
      element.matches(
        '[type="hidden"], [name="csrfmiddlewaretoken"], [name="next"]'
      )
    ) {
      return false;
    }

    return true;
  }

  function shouldIgnoreLink(link, event) {
    if (!link.href) {
      return true;
    }

    if (link.hasAttribute("download")) {
      return true;
    }

    if (link.dataset.dirtyIgnore === "true") {
      return true;
    }

    if (link.closest("[data-dirty-ignore='true']")) {
      return true;
    }

    if (link.target && link.target !== "_self") {
      return true;
    }

    if (event.defaultPrevented) {
      return true;
    }

    if (event.button !== 0) {
      return true;
    }

    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return true;
    }

    return false;
  }

  function sameOriginPathFromHref(href) {
    const url = new URL(href, window.location.href);

    if (url.origin !== window.location.origin) {
      return "";
    }

    return `${url.pathname}${url.search}${url.hash}`;
  }

  function showDirtyDialogForLink(link) {
    pendingHref = link.href;

    if (!dialog || typeof dialog.showModal !== "function") {
      return false;
    }

    dialog.showModal();
    return true;
  }

  function refreshAfterDomUpdate() {
    window.requestAnimationFrame(refreshDirtyState);
  }

  resetInitialState();

  document.addEventListener("submit", (event) => {
    const submittedForm = event.target;

    if (!(submittedForm instanceof HTMLFormElement)) {
      return;
    }

    if (submittedForm === form) {
      return;
    }

    if (submittedForm.closest("[data-dirty-ignore='true']")) {
      isSubmitting = true;
      setDirty(false);
    }
  });

  form.addEventListener("input", (event) => {
    if (isEditableOrderField(event.target)) {
      refreshDirtyState();
    }
  });

  form.addEventListener("change", (event) => {
    if (isEditableOrderField(event.target)) {
      refreshDirtyState();
    }
  });

  form.addEventListener("click", (event) => {
    const target = event.target;

    if (!(target instanceof Element)) {
      return;
    }

    if (
      target.closest("[data-add-order-line]") ||
      target.closest("[data-remove-order-line]")
    ) {
      refreshAfterDomUpdate();
    }
  });

  form.addEventListener("submit", () => {
    isSubmitting = true;
    setDirty(false);
  });

  document.addEventListener("click", (event) => {
    const target = event.target;

    if (!(target instanceof Element)) {
      return;
    }

    const link = target.closest("a[href]");

    if (!link || shouldIgnoreLink(link, event)) {
      return;
    }

    if (!isDirty) {
      return;
    }

    event.preventDefault();

    const opened = showDirtyDialogForLink(link);

    if (!opened) {
      const shouldLeave = window.confirm(
        "You have unsaved changes. Leave without saving?"
      );

      if (shouldLeave) {
        isSubmitting = true;
        setDirty(false);
        window.location.assign(link.href);
      }
    }
  });

  saveContinueButton?.addEventListener("click", () => {
    if (!pendingHref || !nextInput || !saveSubmitButton) {
      return;
    }

    const safeNext = sameOriginPathFromHref(pendingHref);

    if (!safeNext) {
      return;
    }

    nextInput.value = safeNext;
    isSubmitting = true;
    setDirty(false);

    form.requestSubmit(saveSubmitButton);
  });

  leaveButton?.addEventListener("click", () => {
    if (!pendingHref) {
      return;
    }

    isSubmitting = true;
    setDirty(false);

    window.location.assign(pendingHref);
  });

  stayButton?.addEventListener("click", () => {
    pendingHref = "";

    if (dialog?.open) {
      dialog.close();
    }
  });

  dialog?.addEventListener("cancel", () => {
    pendingHref = "";
  });
})();
