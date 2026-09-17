"use strict";


(() => {
  const DISMISSABLE_DETAILS_SELECTOR = (
    "details[data-dismiss-on-outside-click]"
  );


  function openDismissableDetails() {
    return document.querySelectorAll(
      `${DISMISSABLE_DETAILS_SELECTOR}[open]`
    );
  }


  function triggerElement(
    details
  ) {
    return details.querySelector(
      ":scope > summary"
    );
  }


  function closeDetails(
    details,
    {
      restoreFocus = false,
    } = {}
  ) {
    if (
      !details
      || !details.open
    ) {
      return;
    }

    details.open = false;

    if (!restoreFocus) {
      return;
    }

    const trigger = triggerElement(
      details
    );

    if (
      trigger instanceof HTMLElement
    ) {
      trigger.focus();
    }
  }


  document.addEventListener(
    "click",
    (event) => {
      const target = event.target;

      if (!(target instanceof Node)) {
        return;
      }

      for (
        const details
        of openDismissableDetails()
      ) {
        if (
          details.contains(
            target
          )
        ) {
          continue;
        }

        closeDetails(
          details
        );
      }
    }
  );


  document.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key !== "Escape"
      ) {
        return;
      }

      const openDetails = (
        openDismissableDetails()
      );

      if (
        openDetails.length === 0
      ) {
        return;
      }

      event.preventDefault();

      for (
        const details
        of openDetails
      ) {
        closeDetails(
          details,
          {
            restoreFocus: true,
          }
        );
      }
    }
  );
})();
