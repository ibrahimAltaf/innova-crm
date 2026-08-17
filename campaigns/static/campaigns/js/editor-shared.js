(function () {
  function readJson(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    try {
      return JSON.parse(el.textContent);
    } catch (err) {
      return fallback;
    }
  }

  window.EditorShared = {
    initialHtml: function () {
      const value = readJson("initial-html", "");
      return typeof value === "string" ? value : "";
    },
    initialBlocks: function () {
      const value = readJson("initial-blocks", []);
      return Array.isArray(value) ? value : [];
    },
    syncFields: function (html, blocks) {
      const htmlField = document.getElementById("id_html_content");
      const blockField = document.getElementById("id_blocks_json");
      if (htmlField) htmlField.value = html || "";
      if (blockField) blockField.value = JSON.stringify(blocks || []);
    },
    previewDoc: function (html) {
      return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>" +
        "body{margin:0;padding:20px 12px;background:#f4f6fb;font-family:Arial,Helvetica,sans-serif;color:#1e293b;}" +
        ".wrap{max-width:600px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;padding:24px;font-size:16px;line-height:1.65;}" +
        "img{max-width:100%;height:auto;border:0;} h1,h2,h3{font-family:Inter,Arial,sans-serif;}" +
        "a.email-cta{display:inline-block;background:#4f46e5;color:#fff!important;text-decoration:none;font-weight:700;padding:12px 22px;border-radius:8px;}" +
        "</style></head><body><div class='wrap'>" +
        (html || "<p></p>") +
        "</div></body></html>"
      );
    },
    bindForm: function (getHtml, getBlocks) {
      const form = document.getElementById("editor-form");
      if (!form) return;
      form.addEventListener("submit", function () {
        EditorShared.syncFields(getHtml(), getBlocks ? getBlocks() : []);
      });
      const previewModal = document.getElementById("previewTestModal");
      if (previewModal) {
        previewModal.addEventListener("show.bs.modal", function () {
          const frame = document.getElementById("live-preview-frame");
          const html = getHtml() || "<p></p>";
          if (frame) frame.srcdoc = EditorShared.previewDoc(html);
          const copy = function (fromName, toId) {
            const src = form.querySelector('[name="' + fromName + '"]');
            const dest = document.getElementById(toId);
            if (src && dest) dest.value = src.value;
          };
          copy("name", "test-name");
          copy("subject", "test-subject");
          copy("preheader", "test-preheader");
          const subject = form.querySelector('[name="subject"]');
          const pre = form.querySelector('[name="preheader"]');
          const subjEl = document.getElementById("inbox-mock-subject");
          const preEl = document.getElementById("inbox-mock-pre");
          if (subjEl) subjEl.textContent = (subject && subject.value) || "Untitled";
          if (preEl) preEl.textContent = (pre && pre.value) || "";
          const testHtml = document.getElementById("test-html");
          const testBlocks = document.getElementById("test-blocks");
          if (testHtml) testHtml.value = html;
          if (testBlocks) testBlocks.value = JSON.stringify(getBlocks ? getBlocks() : []);
        });
      }
      document.getElementById("preview-desktop")?.addEventListener("click", function () {
        document.getElementById("preview-stage")?.classList.remove("is-mobile");
        this.classList.add("active");
        document.getElementById("preview-mobile")?.classList.remove("active");
      });
      document.getElementById("preview-mobile")?.addEventListener("click", function () {
        document.getElementById("preview-stage")?.classList.add("is-mobile");
        this.classList.add("active");
        document.getElementById("preview-desktop")?.classList.remove("active");
      });
    },
    fileToDataUrl: function (file) {
      return new Promise(function (resolve, reject) {
        const reader = new FileReader();
        reader.onload = function () {
          resolve(reader.result);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    },
  };
})();
