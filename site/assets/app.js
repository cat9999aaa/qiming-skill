document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  const text = button.getAttribute("data-copy");
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const field = document.createElement("textarea");
    field.value = text;
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.append(field);
    field.select();
    const copied = document.execCommand("copy");
    field.remove();
    if (!copied) return;
  }
  const label = button.querySelector("span:last-child");
  label.textContent = button.getAttribute("data-copied-label");
  button.setAttribute("aria-label", button.getAttribute("data-copied-label"));
  window.setTimeout(() => {
    label.textContent = button.getAttribute("data-default-label");
    button.setAttribute("aria-label", button.getAttribute("data-default-label"));
  }, 2200);
});
