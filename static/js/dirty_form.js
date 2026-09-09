(() => {
  const form = document.querySelector("[data-dirty-form]");

  if (!form) {
    return;
  }

  let isDirty = false;
  let isSubmitting = false;
  let initialState = "";

  function isEditableField(element) {
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
        '[type="hidden"], [name="csrfmiddlewaretoken"]'
      )
    ) {
      return false;
    }

    return true;
  }

  function fieldState() {
    return [...form.querySelectorAll("input, select, textarea")]
      .filter(isEditableField)
      .map((field) => {
        if (
          field instanceof HTMLInputElement
          && (
            field.type === "checkbox"
            || field.type === "radio"
          )
        ) {
          return {
            name: field.name,
            type: field.type,
            value: field.value,
            checked: field.checked,
          };
        }

        return {
          name: field.name,
          type: field.type,
          value: field.value,
        };
      });
  }

  function serializedState() {
    return JSON.stringify(fieldState());
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

    form.toggleAttribute(
      "data-dirty",
      isDirty
    );

    if (isDirty) {
      window.addEventListener(
        "beforeunload",
        handleBeforeUnload
      );
    } else {
      window.removeEventListener(
        "beforeunload",
        handleBeforeUnload
      );
    }
  }

  function refreshDirtyState() {
    if (isSubmitting) {
      return;
    }

    setDirty(
      serializedState() !== initialState
    );
  }

  function resetInitialState() {
    initialState = serializedState();
    setDirty(false);
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

    if (
      link.closest("[data-dirty-ignore='true']")
    ) {
      return true;
    }

    if (
      link.target
      && link.target !== "_self"
    ) {
      return true;
    }

    if (event.defaultPrevented) {
      return true;
    }

    if (event.button !== 0) {
      return true;
    }

    if (
      event.metaKey
      || event.ctrlKey
      || event.shiftKey
      || event.altKey
    ) {
      return true;
    }

    return false;
  }

  resetInitialState();

  form.addEventListener(
    "input",
    (event) => {
      if (isEditableField(event.target)) {
        refreshDirtyState();
      }
    }
  );

  form.addEventListener(
    "change",
    (event) => {
      if (isEditableField(event.target)) {
        refreshDirtyState();
      }
    }
  );

  form.addEventListener(
    "submit",
    () => {
      isSubmitting = true;
      setDirty(false);
    }
  );

  document.addEventListener(
    "click",
    (event) => {
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

      const shouldLeave = window.confirm(
        "You have unsaved changes. Leave without saving?"
      );

      if (!shouldLeave) {
        return;
      }

      isSubmitting = true;
      setDirty(false);

      window.location.assign(link.href);
    }
  );
})();
