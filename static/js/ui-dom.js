"use strict";


(() => {
  window.SwedeSweets = (
    window.SwedeSweets || {}
  );


  function closest(
    element,
    selector
  ) {
    if (
      !element
      || !selector
    ) {
      return null;
    }

    return element.closest(
      selector
    );
  }


  function setHidden(
    element,
    hidden
  ) {
    if (!element) {
      return;
    }

    element.hidden = Boolean(
      hidden
    );
  }


  function show(
    element
  ) {
    setHidden(
      element,
      false
    );
  }


  function hide(
    element
  ) {
    setHidden(
      element,
      true
    );
  }


  function remove(
    element
  ) {
    if (!element) {
      return;
    }

    element.remove();
  }


  function replaceHtml(
    element,
    html
  ) {
    if (!element) {
      return;
    }

    element.innerHTML = html;
  }


  window.SwedeSweets.dom = Object.freeze({
    closest,
    setHidden,
    show,
    hide,
    remove,
    replaceHtml,
  });
})();
