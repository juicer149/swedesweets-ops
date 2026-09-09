(() => {
  const groups = document.querySelectorAll(
    "[data-tabs]"
  );

  for (const group of groups) {
    initializeTabs(group);
  }

  function initializeTabs(group) {
    const tabs = [
      ...group.querySelectorAll(
        "[data-tab]"
      ),
    ];

    const panels = [
      ...group.querySelectorAll(
        "[data-tab-panel]"
      ),
    ];

    if (
      tabs.length === 0
      || panels.length === 0
    ) {
      return;
    }

    function activateTab(
      tabKey,
      { focus = false } = {}
    ) {
      for (const tab of tabs) {
        const isActive =
          tab.dataset.tab === tabKey;

        tab.classList.toggle(
          "section-nav__link--active",
          isActive
        );

        tab.setAttribute(
          "aria-selected",
          String(isActive)
        );

        tab.tabIndex = isActive ? 0 : -1;

        if (isActive && focus) {
          tab.focus();
        }
      }

      for (const panel of panels) {
        const isActive =
          panel.dataset.tabPanel === tabKey;

        panel.hidden = !isActive;
      }
    }

    function panelContainsErrors(panel) {
      return Boolean(
        panel.querySelector(
          ".form-field--error, .form-errors"
        )
      );
    }

    function initialTabKey() {
      const panelWithErrors = panels.find(
        panelContainsErrors
      );

      if (panelWithErrors) {
        return panelWithErrors.dataset.tabPanel;
      }

      const selectedTab = tabs.find(
        (tab) => (
          tab.getAttribute("aria-selected")
          === "true"
        )
      );

      return (
        selectedTab?.dataset.tab
        ?? tabs[0].dataset.tab
      );
    }

    function moveFocus(
      currentTab,
      eventKey
    ) {
      const currentIndex =
        tabs.indexOf(currentTab);

      let nextIndex = currentIndex;

      if (eventKey === "ArrowRight") {
        nextIndex =
          (currentIndex + 1)
          % tabs.length;
      }

      if (eventKey === "ArrowLeft") {
        nextIndex =
          (
            currentIndex
            - 1
            + tabs.length
          )
          % tabs.length;
      }

      if (eventKey === "Home") {
        nextIndex = 0;
      }

      if (eventKey === "End") {
        nextIndex =
          tabs.length - 1;
      }

      activateTab(
        tabs[nextIndex].dataset.tab,
        {
          focus: true,
        }
      );
    }

    for (const tab of tabs) {
      tab.addEventListener(
        "click",
        () => {
          activateTab(
            tab.dataset.tab
          );
        }
      );

      tab.addEventListener(
        "keydown",
        (event) => {
          const supportedKeys = [
            "ArrowLeft",
            "ArrowRight",
            "Home",
            "End",
          ];

          if (
            !supportedKeys.includes(
              event.key
            )
          ) {
            return;
          }

          event.preventDefault();

          moveFocus(
            tab,
            event.key
          );
        }
      );
    }

    activateTab(
      initialTabKey()
    );
  }
})();
