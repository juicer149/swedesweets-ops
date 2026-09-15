document.addEventListener("DOMContentLoaded", () => {
  const checklist = document.querySelector("[data-pack-checklist]");

  if (!checklist) {
    return;
  }

  const urlBase = checklist.dataset.checklistToggleUrlBase;

  if (!urlBase) {
    return;
  }

  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
  }

  async function toggleMark(checkbox) {
    const allocationId = checkbox.dataset.allocationId;

    if (!allocationId) {
      return;
    }

    if (checkbox.dataset.updateInProgress === "true") {
      // A request is already in flight for this checkbox - the DOM
      // checked state is already what the user wants next, so let the
      // in-flight request settle and don't stack a second one.
      return;
    }

    checkbox.dataset.updateInProgress = "true";
    checkbox.disabled = true;

    const previousChecked = !checkbox.checked;

    try {
      const response = await fetch(
        `${urlBase}${allocationId}/toggle/`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          credentials: "same-origin",
        }
      );

      const payload = await response.json();

      if (!response.ok || !payload.ok) {
        throw new Error(
          payload.message || "Could not update checklist."
        );
      }

      checkbox.checked = Boolean(payload.checked);
    } catch {
      // Revert to the pre-click state on any failure (network error,
      // permission change mid-session, stale allocation).
      checkbox.checked = previousChecked;
    } finally {
      checkbox.dataset.updateInProgress = "false";
      checkbox.disabled = false;
    }
  }

  checklist.addEventListener("change", (event) => {
    const checkbox = event.target.closest(
      "[data-pack-line-checkbox]"
    );

    if (!checkbox) {
      return;
    }

    void toggleMark(checkbox);
  });
});
