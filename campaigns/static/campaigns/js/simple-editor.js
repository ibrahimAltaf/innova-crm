(function () {
  const editor = document.getElementById("rte-editor");
  const toolbar = document.getElementById("rte-toolbar");
  const fileInput = document.getElementById("rte-file");
  if (!editor || !toolbar) return;

  const starter = EditorShared.initialHtml();
  if (starter) editor.innerHTML = starter;

  function html() {
    return editor.innerHTML.trim();
  }

  EditorShared.bindForm(html);

  toolbar.addEventListener("click", function (event) {
    const btn = event.target.closest("button[data-cmd]");
    if (!btn) return;
    event.preventDefault();
    const cmd = btn.getAttribute("data-cmd");
    if (cmd === "createLink") {
      const url = window.prompt("Link URL", "https://");
      if (url) document.execCommand("createLink", false, url);
      return;
    }
    document.execCommand(cmd, false, null);
    editor.focus();
  });

  toolbar.addEventListener("change", function (event) {
    const select = event.target.closest("select[data-cmd]");
    if (!select) return;
    document.execCommand(select.getAttribute("data-cmd"), false, select.value);
    editor.focus();
  });

  document.getElementById("rte-image")?.addEventListener("click", function () {
    fileInput?.click();
  });

  fileInput?.addEventListener("change", async function () {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    const dataUrl = await EditorShared.fileToDataUrl(file);
    document.execCommand("insertHTML", false, '<img src="' + dataUrl + '" alt="" style="max-width:100%;height:auto;">');
  });

  editor.addEventListener("paste", async function (event) {
    const clipboard = event.clipboardData;
    if (!clipboard) return;
    const files = Array.from(clipboard.items || [])
      .filter(function (item) {
        return item.type.indexOf("image/") === 0;
      })
      .map(function (item) {
        return item.getAsFile();
      })
      .filter(Boolean);
    const pastedHtml = clipboard.getData("text/html");
    if (pastedHtml) {
      event.preventDefault();
      const cleaned = await normalizeHtml(pastedHtml, files);
      document.execCommand("insertHTML", false, cleaned);
      return;
    }
    if (files.length) {
      event.preventDefault();
      for (const file of files) {
        const dataUrl = await EditorShared.fileToDataUrl(file);
        document.execCommand(
          "insertHTML",
          false,
          '<img src="' + dataUrl + '" alt="" style="max-width:100%;height:auto;">'
        );
      }
    }
  });

  async function normalizeHtml(raw, files) {
    const parsed = new DOMParser().parseFromString(raw, "text/html");
    parsed.querySelectorAll("img").forEach(function (img) {
      img.style.maxWidth = "100%";
      img.style.height = "auto";
      img.removeAttribute("width");
      img.removeAttribute("height");
    });
    parsed.querySelectorAll("script,style,meta,link").forEach(function (node) {
      node.remove();
    });
    let out = parsed.body ? parsed.body.innerHTML : raw;
    if (files && files.length && !parsed.querySelector("img")) {
      for (const file of files) {
        const dataUrl = await EditorShared.fileToDataUrl(file);
        out += '<p><img src="' + dataUrl + '" alt="" style="max-width:100%;height:auto;"></p>';
      }
    }
    return out;
  }
})();
