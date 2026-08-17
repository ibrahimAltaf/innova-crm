(function () {
  const editor = document.getElementById("rte-editor");
  const toolbar = document.getElementById("rte-toolbar");
  const fileInput = document.getElementById("rte-file");
  const coverFile = document.getElementById("cover-file");
  const coverBtn = document.getElementById("blog-cover");
  const coverImg = document.getElementById("blog-cover-img");
  const coverEmpty = document.getElementById("blog-cover-empty");
  const coverRemove = document.getElementById("blog-cover-remove");
  const title = document.getElementById("blog-title");
  const dek = document.getElementById("blog-dek");
  const subjectSync = document.getElementById("blog-subject-sync");
  const preheaderSync = document.getElementById("blog-preheader-sync");
  const countEl = document.getElementById("blog-count");
  if (!editor || !toolbar) return;

  function setCover(src) {
    if (!coverImg) return;
    if (src) {
      coverImg.src = src;
      coverImg.hidden = false;
      if (coverEmpty) coverEmpty.hidden = true;
      if (coverRemove) coverRemove.hidden = false;
      coverBtn?.classList.add("has-image");
    } else {
      coverImg.removeAttribute("src");
      coverImg.hidden = true;
      if (coverEmpty) coverEmpty.hidden = false;
      if (coverRemove) coverRemove.hidden = true;
      coverBtn?.classList.remove("has-image");
    }
  }

  function loadStarter(raw) {
    if (!raw) return;
    const parsed = new DOMParser().parseFromString(raw, "text/html");
    const cover = parsed.querySelector("img.blog-cover-img");
    if (cover) {
      setCover(cover.getAttribute("src"));
      const parent = cover.closest("p");
      (parent || cover).remove();
    }
    editor.innerHTML = ((parsed.body && parsed.body.innerHTML) || raw).trim();
  }

  loadStarter(EditorShared.initialHtml());

  function html() {
    const body = editor.innerHTML.trim();
    const src = coverImg && !coverImg.hidden ? coverImg.getAttribute("src") : "";
    if (!src) return body;
    return (
      '<p><img class="blog-cover-img" src="' +
      src +
      '" alt="" style="display:block;width:100%;max-width:600px;height:auto;border:0;"></p>' +
      body
    );
  }

  function syncTitle() {
    if (title && subjectSync) subjectSync.value = title.value;
    if (dek && preheaderSync) preheaderSync.value = dek.value;
    const nameInput = document.querySelector(".editor-name");
    if (nameInput && !(nameInput.value || "").trim() && title && title.value) {
      nameInput.value = title.value;
    }
    const text = (editor.innerText || "").replace(/\s+/g, " ").trim();
    const words = text ? text.split(" ").length : 0;
    if (countEl) countEl.textContent = words + (words === 1 ? " word" : " words");
  }

  title?.addEventListener("input", syncTitle);
  dek?.addEventListener("input", syncTitle);
  editor.addEventListener("input", syncTitle);
  syncTitle();

  document.getElementById("previewTestModal")?.addEventListener("show.bs.modal", syncTitle);
  EditorShared.bindForm(html);
  document.getElementById("editor-form")?.addEventListener("submit", syncTitle);

  toolbar.addEventListener("click", function (event) {
    const btn = event.target.closest("button[data-cmd]");
    if (!btn) return;
    event.preventDefault();
    const cmd = btn.getAttribute("data-cmd");
    if (cmd === "createLink") {
      const url = window.prompt("Link URL", "https://");
      if (url) document.execCommand("createLink", false, url);
      editor.focus();
      return;
    }
    document.execCommand(cmd, false, null);
    editor.focus();
  });

  toolbar.addEventListener("change", function (event) {
    const select = event.target.closest("select[data-cmd]");
    if (!select) return;
    const cmd = select.getAttribute("data-cmd");
    let value = select.value;
    if (cmd === "formatBlock") value = "<" + value + ">";
    document.execCommand(cmd, false, value);
    editor.focus();
  });

  document.getElementById("rte-color")?.addEventListener("input", function (event) {
    document.execCommand("foreColor", false, event.target.value);
    editor.focus();
  });

  document.getElementById("rte-image")?.addEventListener("click", function () {
    fileInput?.click();
  });

  fileInput?.addEventListener("change", async function () {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    await insertImage(file);
  });

  coverBtn?.addEventListener("click", function (event) {
    if (event.target.id === "blog-cover-remove") {
      event.preventDefault();
      event.stopPropagation();
      setCover("");
      return;
    }
    coverFile?.click();
  });

  coverRemove?.addEventListener("click", function (event) {
    event.preventDefault();
    event.stopPropagation();
    setCover("");
  });

  coverFile?.addEventListener("change", async function () {
    const file = coverFile.files && coverFile.files[0];
    coverFile.value = "";
    if (!file) return;
    setCover(await EditorShared.fileToDataUrl(file));
  });

  async function insertImage(file) {
    const dataUrl = await EditorShared.fileToDataUrl(file);
    document.execCommand(
      "insertHTML",
      false,
      '<p><img src="' + dataUrl + '" alt="" style="max-width:100%;height:auto;"></p>'
    );
    editor.focus();
    syncTitle();
  }

  async function handlePaste(event, targetCover) {
    const clipboard = event.clipboardData;
    if (!clipboard) return false;
    const files = Array.from(clipboard.items || [])
      .filter(function (item) {
        return item.type.indexOf("image/") === 0;
      })
      .map(function (item) {
        return item.getAsFile();
      })
      .filter(Boolean);
    const pastedHtml = clipboard.getData("text/html");
    if (targetCover && files[0]) {
      event.preventDefault();
      setCover(await EditorShared.fileToDataUrl(files[0]));
      return true;
    }
    if (pastedHtml) {
      event.preventDefault();
      const cleaned = await normalizeHtml(pastedHtml, files);
      document.execCommand("insertHTML", false, cleaned);
      syncTitle();
      return true;
    }
    if (files.length) {
      event.preventDefault();
      for (const file of files) await insertImage(file);
      return true;
    }
    return false;
  }

  editor.addEventListener("paste", function (event) {
    handlePaste(event, false);
  });
  coverBtn?.addEventListener("paste", function (event) {
    handlePaste(event, true);
  });

  ["dragenter", "dragover"].forEach(function (name) {
    document.getElementById("blog-paper")?.addEventListener(name, function (event) {
      event.preventDefault();
      event.currentTarget.classList.add("is-drop");
    });
  });
  document.getElementById("blog-paper")?.addEventListener("dragleave", function (event) {
    event.currentTarget.classList.remove("is-drop");
  });
  document.getElementById("blog-paper")?.addEventListener("drop", async function (event) {
    event.preventDefault();
    event.currentTarget.classList.remove("is-drop");
    const file = event.dataTransfer?.files && event.dataTransfer.files[0];
    if (!file || file.type.indexOf("image/") !== 0) return;
    const onCover = event.target.closest("#blog-cover");
    if (onCover) setCover(await EditorShared.fileToDataUrl(file));
    else await insertImage(file);
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
