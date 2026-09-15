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

    /*
     * order_lines.js's product picker is a transient UI control, not
     * real order data - it's always reset to empty right after a
     * selection is made, and the real change (a new/incremented line)
     * is already reported separately via the dirty-form:refresh event.
     * Tracking this field produces a false "changed" marker on the
     * picker itself instead of on the line that actually changed.
     */
    if (
      element.matches("[data-add-order-line-select]")
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
   * a destructive action's own link (Cancel order), which already has
   * its own confirmation flow via data-confirm-message. These should
   * never show a second, generic prompt - neither our styled dialog,
   * nor the browser's own beforeunload prompt. Plain "go back without
   * saving" links (e.g. order_form.html's Back) are NOT marked this
   * way - they behave like any other navigation and should trigger the
   * normal unsaved-changes prompt below.
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

  /*
   * A dirty-ignore link may separately opt into its own confirmation
   * prompt via data-confirm-message (e.g. "Are you sure you want to
   * cancel this order?") - distinct from the unsaved-changes prompt
   * below. Handled in the same click handler as dirty-ignore links so
   * there is one single owner of "what happens when this link is
   * clicked", rather than a second listener racing this one over
   * preventDefault() and dirty-state cleanup.
   */
  async function confirmAndNavigate(link) {
    const confirmed = window.confirmDialog
      ? await window.confirmDialog(
          link.dataset.confirmMessage,
          {
            title: link.dataset.confirmTitle || "Please confirm",
            confirmLabel: link.dataset.confirmLabel || "Confirm",
            cancelLabel: link.dataset.confirmCancelLabel || "Cancel",
          }
        )
      : window.confirm(link.dataset.confirmMessage);

    if (!confirmed) {
      return;
    }

    isSubmitting = true;
    setDirty(false);

    window.location.assign(link.href);
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
        if (link.dataset.confirmMessage) {
          event.preventDefault();
          await confirmAndNavigate(link);
          return;
        }

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
