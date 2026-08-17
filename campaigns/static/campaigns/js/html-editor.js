(function () {
  const source = document.getElementById("html-source");
  const frame = document.getElementById("html-live-frame");
  if (!source) return;

  source.value = EditorShared.initialHtml() || "";

  function html() {
    return source.value;
  }

  function refresh() {
    if (frame) frame.srcdoc = source.value || "<p></p>";
    EditorShared.syncFields(source.value, []);
  }

  source.addEventListener("input", refresh);
  EditorShared.bindForm(html);
  refresh();
})();
