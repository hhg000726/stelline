window.Stelline = {
  api(path, options = {}) {
    return fetch(`/api/${path.replace(/^\//, "")}`, options);
  },
  goBack() {
    window.location.href = "../";
  },
  escapeHtml(value) {
    const node = document.createElement("span");
    node.textContent = value ?? "";
    return node.innerHTML;
  },
};
