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
          if (frame) frame.srcdoc = html;
          const copy = function (fromName, toId) {
            const src = form.querySelector('[name="' + fromName + '"]');
            const dest = document.getElementById(toId);
            if (src && dest) dest.value = src.value;
          };
          copy("name", "test-name");
          copy("subject", "test-subject");
          copy("preheader", "test-preheader");
          const testHtml = document.getElementById("test-html");
          const testBlocks = document.getElementById("test-blocks");
          if (testHtml) testHtml.value = getHtml() || "";
          if (testBlocks) testBlocks.value = JSON.stringify(getBlocks ? getBlocks() : []);
        });
      }
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
