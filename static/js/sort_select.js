document.addEventListener("change", function (event) {
  if (!event.target.matches(".sort-select")) {
    return;
  }

  const href = event.target.value;

  if (href) {
    window.location.href = href;
  }
});
