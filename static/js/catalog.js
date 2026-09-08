(() => {
  const forms = document.querySelectorAll("[data-catalog-add-form]");
  const feedback = document.querySelector("[data-catalog-feedback]");

  if (!forms.length) {
    return;
  }

  function setFeedback(message) {
    if (!feedback) {
      return;
    }

    feedback.textContent = message;
  }

  async function submitAddForm(form) {
    const button = form.querySelector("[data-catalog-add-button]");

    if (!button) {
      return;
    }

    const originalLabel = button.textContent.trim();

    button.disabled = true;

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          Accept: "application/json",
        },
        credentials: "same-origin",
      });

      const payload = await response.json();

      if (!response.ok || !payload.ok) {
        throw new Error(
          payload.message || "Could not add product."
        );
      }

      button.textContent = "Added";
      setFeedback(payload.message);

      window.setTimeout(() => {
        button.textContent = originalLabel;
        button.disabled = false;
      }, 1000);
    } catch (error) {
      button.textContent = originalLabel;
      button.disabled = false;

      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not add product."
      );
    }
  }

  forms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submitAddForm(form);
    });
  });
})();
