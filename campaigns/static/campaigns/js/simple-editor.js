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
  const form = document.getElementById("editor-form");
  const slash = document.getElementById("slash-menu");
  const imgBar = document.getElementById("img-toolbar");
  const DRAFT_KEY = "innova-simple-draft";
  if (!editor || !toolbar) return;

  let savedRange = null;
  let selectedImg = null;
  let dirty = false;
  let saveTimer = null;

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
    markDirty();
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

  const initial = EditorShared.initialHtml();
  loadStarter(initial);
  if (!initial && !form.dataset.campaignId) {
    try {
      const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
      if (draft && (draft.title || draft.html)) {
        if (draft.title) title.value = draft.title;
        if (draft.dek) dek.value = draft.dek;
        if (draft.name) {
          const nameInput = document.querySelector(".editor-name");
          if (nameInput && !nameInput.value) nameInput.value = draft.name;
        }
        if (draft.cover) setCover(draft.cover);
        if (draft.html) editor.innerHTML = draft.html;
        setPill("Restored unsaved draft");
      }
    } catch (err) {}
  }

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

  function setPill(text) {
    const pill = document.getElementById("save-pill");
    if (pill) pill.textContent = text;
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
    const liveSub = document.getElementById("inbox-live-subject");
    const livePre = document.getElementById("inbox-live-pre");
    const subCount = document.getElementById("subject-count");
    if (liveSub) liveSub.textContent = title.value || "Title will show here";
    if (livePre) livePre.textContent = dek.value || "Short intro shows next to the subject in Gmail";
    if (subCount) {
      const n = (title.value || "").length;
      subCount.textContent = n + " / 50";
      subCount.classList.toggle("is-warn", n > 50);
    }
  }

  function markDirty() {
    dirty = true;
    setPill("Unsaved");
    try {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          title: title?.value || "",
          dek: dek?.value || "",
          name: document.querySelector(".editor-name")?.value || "",
          cover: coverImg && !coverImg.hidden ? coverImg.src : "",
          html: editor.innerHTML,
        })
      );
    } catch (err) {}
    clearTimeout(saveTimer);
    saveTimer = setTimeout(autosave, 12000);
  }

  async function autosave() {
    if (!dirty) return;
    const hasContent = (title?.value || "").trim() || (editor.innerText || "").trim() || (coverImg && !coverImg.hidden);
    if (!hasContent) return;
    syncTitle();
    EditorShared.syncFields(html(), []);
    const data = new FormData(form);
    data.set("action", "autosave");
    setPill("Saving…");
    try {
      const res = await fetch(form.dataset.autosaveUrl || window.location.pathname, {
        method: "POST",
        body: data,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const json = await res.json();
      if (json.url) {
        form.dataset.autosaveUrl = json.url;
        form.dataset.campaignId = String(json.id || "");
        if (window.location.pathname !== json.url) history.replaceState({}, "", json.url);
      }
      dirty = false;
      try {
        localStorage.removeItem(DRAFT_KEY);
      } catch (err) {}
      setPill("Saved " + (json.saved_at || ""));
    } catch (err) {
      setPill("Save failed — try Save");
    }
  }

  title?.addEventListener("input", function () {
    syncTitle();
    markDirty();
  });
  dek?.addEventListener("input", function () {
    syncTitle();
    markDirty();
  });
  editor.addEventListener("input", function () {
    syncTitle();
    markDirty();
    maybeSlash();
  });
  document.querySelector(".editor-name")?.addEventListener("input", markDirty);
  syncTitle();

  document.getElementById("previewTestModal")?.addEventListener("show.bs.modal", syncTitle);
  EditorShared.bindForm(html);
  document.getElementById("editor-form")?.addEventListener("submit", function () {
    syncTitle();
    try {
      localStorage.removeItem(DRAFT_KEY);
    } catch (err) {}
  });

  document.addEventListener("keydown", function (event) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      autosave();
    }
  });

  function saveRange() {
    const sel = window.getSelection();
    if (sel && sel.rangeCount) savedRange = sel.getRangeAt(0).cloneRange();
  }
  function restoreRange() {
    if (!savedRange) return;
    editor.focus();
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(savedRange);
  }
  function insertHtml(snippet) {
    restoreRange();
    editor.focus();
    document.execCommand("insertHTML", false, snippet);
    markDirty();
    syncTitle();
  }

  toolbar.addEventListener("mousedown", saveRange);
  editor.addEventListener("mouseup", function () {
    saveRange();
    updateActive();
  });
  editor.addEventListener("keyup", updateActive);

  function updateActive() {
    toolbar.querySelectorAll("button[data-cmd]").forEach(function (btn) {
      const cmd = btn.getAttribute("data-cmd");
      try {
        btn.classList.toggle("is-on", document.queryCommandState(cmd));
      } catch (err) {}
    });
  }

  toolbar.addEventListener("click", function (event) {
    const btn = event.target.closest("button[data-cmd]");
    if (!btn) return;
    event.preventDefault();
    restoreRange();
    document.execCommand(btn.getAttribute("data-cmd"), false, null);
    editor.focus();
    updateActive();
    markDirty();
  });

  toolbar.addEventListener("change", function (event) {
    const select = event.target.closest("select[data-cmd]");
    if (!select) return;
    restoreRange();
    const cmd = select.getAttribute("data-cmd");
    let value = select.value;
    if (cmd === "formatBlock") value = "<" + value + ">";
    document.execCommand(cmd, false, value);
    editor.focus();
    markDirty();
  });

  document.getElementById("rte-color")?.addEventListener("input", function (event) {
    restoreRange();
    document.execCommand("foreColor", false, event.target.value);
    editor.focus();
    markDirty();
  });

  document.getElementById("rte-image")?.addEventListener("click", function () {
    fileInput?.click();
  });
  document.getElementById("chip-photo")?.addEventListener("click", function () {
    fileInput?.click();
  });
  document.getElementById("rte-link")?.addEventListener("click", function () {
    saveRange();
    bootstrap.Modal.getOrCreateInstance(document.getElementById("linkModal")).show();
  });
  document.getElementById("rte-cta")?.addEventListener("click", openCta);
  document.getElementById("chip-button")?.addEventListener("click", openCta);

  function openCta() {
    saveRange();
    bootstrap.Modal.getOrCreateInstance(document.getElementById("ctaModal")).show();
  }

  document.getElementById("link-apply")?.addEventListener("click", function () {
    const url = document.getElementById("link-url").value.trim();
    bootstrap.Modal.getInstance(document.getElementById("linkModal"))?.hide();
    if (!url) return;
    restoreRange();
    document.execCommand("createLink", false, url);
    markDirty();
  });

  document.getElementById("cta-apply")?.addEventListener("click", function () {
    const text = document.getElementById("cta-text").value.trim() || "Learn more";
    const url = document.getElementById("cta-url").value.trim() || "#";
    bootstrap.Modal.getInstance(document.getElementById("ctaModal"))?.hide();
    insertHtml(
      '<p><a class="email-cta" href="' +
        url.replace(/"/g, "") +
        '" style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 22px;border-radius:8px;">' +
        text.replace(/</g, "") +
        "</a></p>"
    );
  });

  document.querySelectorAll(".chip[data-token]").forEach(function (chip) {
    chip.addEventListener("click", function () {
      saveRange();
      insertHtml(" " + chip.dataset.token + " ");
    });
  });
  document.getElementById("chip-greeting")?.addEventListener("click", function () {
    saveRange();
    insertHtml("<p>Hi {{name}},</p>");
  });

  fileInput?.addEventListener("change", async function () {
    const file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    await insertImage(file);
  });

  coverBtn?.addEventListener("click", function (event) {
    if (event.target.id === "blog-cover-remove") return;
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
    insertHtml('<p><img src="' + dataUrl + '" alt="" style="max-width:100%;height:auto;"></p>');
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
      markDirty();
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
    if (event.target.closest("#blog-cover")) setCover(await EditorShared.fileToDataUrl(file));
    else await insertImage(file);
  });

  function maybeSlash() {
    if (!slash) return;
    const sel = window.getSelection();
    if (!sel || !sel.anchorNode) {
      slash.hidden = true;
      return;
    }
    const block = sel.anchorNode.nodeType === 3 ? sel.anchorNode.parentElement : sel.anchorNode;
    const text = (block && block.textContent) || "";
    if (text.trim() === "/") {
      const rect = (block.getBoundingClientRect && block.getBoundingClientRect()) || editor.getBoundingClientRect();
      slash.style.top = window.scrollY + rect.bottom + 6 + "px";
      slash.style.left = rect.left + "px";
      slash.hidden = false;
    } else slash.hidden = true;
  }

  slash?.addEventListener("mousedown", function (event) {
    event.preventDefault();
    const type = event.target.closest("button")?.dataset.slash;
    slash.hidden = true;
    if (!type) return;
    document.execCommand("delete");
    if (type === "h2") document.execCommand("formatBlock", false, "<h2>");
    if (type === "quote") document.execCommand("formatBlock", false, "<blockquote>");
    if (type === "hr") document.execCommand("insertHorizontalRule");
    if (type === "photo") fileInput?.click();
    if (type === "button") openCta();
    if (type === "name") insertHtml("{{name}}");
    markDirty();
  });

  editor.addEventListener("click", function (event) {
    const img = event.target.closest(".blog-body img");
    if (!img || !imgBar) {
      if (imgBar) imgBar.hidden = true;
      selectedImg = null;
      return;
    }
    selectedImg = img;
    const rect = img.getBoundingClientRect();
    imgBar.style.top = window.scrollY + rect.top - 42 + "px";
    imgBar.style.left = rect.left + "px";
    imgBar.hidden = false;
  });
  document.addEventListener("click", function (event) {
    if (!event.target.closest(".blog-body img, #img-toolbar") && imgBar) imgBar.hidden = true;
  });
  imgBar?.addEventListener("click", function (event) {
    const act = event.target.closest("button")?.dataset.img;
    if (!act || !selectedImg) return;
    if (act === "delete") selectedImg.remove();
    if (act === "left") selectedImg.style.cssText = "max-width:48%;height:auto;float:left;margin:0 16px 12px 0;";
    if (act === "center") selectedImg.style.cssText = "max-width:100%;height:auto;display:block;margin:12px auto;";
    if (act === "full") selectedImg.style.cssText = "max-width:100%;height:auto;display:block;";
    imgBar.hidden = true;
    markDirty();
  });

  document.getElementById("blog-help-close")?.addEventListener("click", function () {
    document.getElementById("blog-help")?.remove();
    try {
      localStorage.setItem("innova-hide-blog-help", "1");
    } catch (err) {}
  });
  try {
    if (localStorage.getItem("innova-hide-blog-help")) document.getElementById("blog-help")?.remove();
  } catch (err) {}

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
