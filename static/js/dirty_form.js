(() => {
  const form = document.querySelector("[data-dirty-form]");

  if (!form) {
    return;
  }

  let isDirty = false;
  let isSubmitting = false;

  /*
   * Per-field tracking (element -> serialized initial value), instead of
   * one serialized string for the whole form. This lets us both toggle a
   * "changed" marker on the individual field that changed, and correctly
   * treat a removed field (e.g. deleting an existing order line) as dirty
   * even when nothing else in the form was touched.
   */
  let initialValues = new Map();

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

  function getEditableFields() {
    return [...form.querySelectorAll("input, select, textarea")].filter(
      isEditableField
    );
  }

  function fieldValueSignature(field) {
    if (
      field instanceof HTMLInputElement
      && (field.type === "checkbox" || field.type === "radio")
    ) {
      return JSON.stringify({
        type: field.type,
        value: field.value,
        checked: field.checked,
      });
    }

    return JSON.stringify({
      type: field.type,
      value: field.value,
    });
  }

  /*
   * Marks the field's nearest .form-field wrapper as changed, if it has
   * one. Fields outside that wrapper (e.g. order_lines.js's cart-style
   * rows) simply get no visual marker - they already have their own
   * "this line is new/removed" affordance.
   */
  function setFieldChanged(field, changed) {
    const wrapper = field.closest(".form-field");

    if (wrapper) {
      wrapper.classList.toggle("form-field--changed", changed);
    }
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

    const currentFields = getEditableFields();
    const currentFieldSet = new Set(currentFields);
    let anyChanged = false;

    currentFields.forEach((field) => {
      const hadInitialValue = initialValues.has(field);
      const changed = (
        !hadInitialValue
        || initialValues.get(field) !== fieldValueSignature(field)
      );

      setFieldChanged(field, changed);

      if (changed) {
        anyChanged = true;
      }
    });

    initialValues.forEach((_value, field) => {
      if (!currentFieldSet.has(field)) {
        // A field that existed at reset time is gone (e.g. a removed
        // order line) - that's a real change even if nothing else
        // differs.
        anyChanged = true;
      }
    });

    setDirty(anyChanged);
  }

  function resetInitialState() {
    initialValues = new Map();

    getEditableFields().forEach((field) => {
      initialValues.set(field, fieldValueSignature(field));
      setFieldChanged(field, false);
    });

    setDirty(false);
  }

  /*
   * True when this click will not actually navigate away from the
   * current tab (download, new tab/window, a modifier key held, a
   * non-primary mouse button, or another handler already handled it).
   * Dirty state is left untouched in every one of these cases, since
   * the page isn't unloading.
   */
  function isNonNavigatingClick(link, event) {
    if (!link.href) {
      return true;
    }

    if (link.hasAttribute("download")) {
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

  /*
   * Opt-in marker for links that represent an intentional discard, e.g.
   * a form's own Cancel/Back button. These should never show a confirm
   * prompt of any kind - not our styled dialog, and not the browser's
   * own unstyleable beforeunload prompt either.
   */
  function isDirtyIgnoreLink(link) {
    if (link.dataset.dirtyIgnore === "true") {
      return true;
    }

    if (
      link.closest("[data-dirty-ignore='true']")
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

  /*
   * Field-level input/change listeners above can't see structural
   * changes that add or remove whole fields (order_lines.js adding a
   * new cart-style line, or removing one via element.remove()) - no
   * event fires for either. order_lines.js dispatches this event
   * explicitly after such changes so dirty tracking still catches them.
   */
  form.addEventListener(
    "dirty-form:refresh",
    refreshDirtyState
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
    async (event) => {
      const target = event.target;

      if (!(target instanceof Element)) {
        return;
      }

      const link = target.closest("a[href]");

      if (!link || isNonNavigatingClick(link, event)) {
        return;
      }

      if (isDirtyIgnoreLink(link)) {
        // Intentional discard (e.g. Cancel/Back): clear dirty state
        // before the browser navigates, so its own beforeunload prompt
        // never fires either. Default navigation proceeds normally -
        // no preventDefault, no confirm of any kind.
        if (isDirty) {
          isSubmitting = true;
          setDirty(false);
        }

        return;
      }

      if (!isDirty) {
        return;
      }

      event.preventDefault();

      const shouldLeave = window.confirmDialog
        ? await window.confirmDialog(
            "You have unsaved changes. Leave without saving?"
          )
        : window.confirm(
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
