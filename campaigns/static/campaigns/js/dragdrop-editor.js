(function () {
  const canvas = document.getElementById("dd-canvas");
  if (!canvas) return;

  let blocks = EditorShared.initialBlocks();
  if (!blocks.length && EditorShared.initialHtml()) {
    blocks = [{ type: "text", html: EditorShared.initialHtml() }];
  }

  function uid() {
    return "b" + Math.random().toString(36).slice(2, 9);
  }

  function defaultBlock(type) {
    if (type === "heading") return { id: uid(), type: type, text: "Your headline" };
    if (type === "text") return { id: uid(), type: type, html: "<p>Write or paste your message here.</p>" };
    if (type === "image") return { id: uid(), type: type, src: "", alt: "" };
    if (type === "button") return { id: uid(), type: type, text: "Learn more", url: "https://" };
    if (type === "spacer") return { id: uid(), type: type, height: 24 };
    return { id: uid(), type: "divider" };
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function compile() {
    const inner = blocks
      .map(function (block) {
        if (block.type === "heading") {
          return '<h1 style="margin:0 0 12px;font-size:24px;line-height:32px;color:#0f172a;">' + escapeHtml(block.text) + "</h1>";
        }
        if (block.type === "text") {
          return '<div style="font-size:15px;line-height:24px;color:#334155;">' + (block.html || "") + "</div>";
        }
        if (block.type === "image" && block.src) {
          return '<p style="margin:12px 0;"><img src="' + escapeHtml(block.src) + '" alt="' + escapeHtml(block.alt) + '" style="display:block;max-width:100%;height:auto;border:0;"></p>';
        }
        if (block.type === "button") {
          return (
            '<p style="margin:16px 0;"><a href="' +
            escapeHtml(block.url || "#") +
            '" style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;padding:12px 22px;border-radius:8px;">' +
            escapeHtml(block.text || "Learn more") +
            "</a></p>"
          );
        }
        if (block.type === "spacer") {
          return '<div style="height:' + Number(block.height || 24) + 'px;line-height:' + Number(block.height || 24) + 'px;">&nbsp;</div>';
        }
        return '<hr style="border:0;border-top:1px solid #e5e7eb;margin:16px 0;">';
      })
      .join("");
    return inner || "<p></p>";
  }

  function render() {
    if (!blocks.length) {
      canvas.innerHTML = '<div class="dd-empty">Add blocks from the left, or paste an image into an Image block.</div>';
      EditorShared.syncFields(compile(), blocks);
      return;
    }
    canvas.innerHTML = "";
    blocks.forEach(function (block, index) {
      const card = document.createElement("div");
      card.className = "dd-block";
      card.draggable = true;
      card.dataset.index = String(index);
      card.innerHTML = headerHtml(block, index) + bodyHtml(block);
      canvas.appendChild(card);
    });
    bindCanvas();
    EditorShared.syncFields(compile(), blocks);
  }

  function headerHtml(block, index) {
    return (
      '<div class="dd-block-head"><span class="dd-handle">⋮⋮</span><strong>' +
      block.type +
      '</strong><button type="button" class="btn btn-sm btn-outline-danger dd-remove" data-index="' +
      index +
      '">Remove</button></div>'
    );
  }

  function bodyHtml(block) {
    if (block.type === "heading") {
      return '<input class="form-control dd-field" data-key="text" value="' + escapeHtml(block.text) + '">';
    }
    if (block.type === "text") {
      return '<div class="dd-text" contenteditable="true">' + (block.html || "") + "</div>";
    }
    if (block.type === "image") {
      const img = block.src
        ? '<img src="' + escapeHtml(block.src) + '" alt="" class="dd-thumb">'
        : '<div class="dd-drop-img">Drop / paste / upload an image</div>';
      return img + '<input type="file" accept="image/*" class="form-control form-control-sm mt-2 dd-file">';
    }
    if (block.type === "button") {
      return (
        '<div class="row g-2"><div class="col-md-5"><input class="form-control dd-field" data-key="text" value="' +
        escapeHtml(block.text) +
        '" placeholder="Button text"></div><div class="col-md-7"><input class="form-control dd-field" data-key="url" value="' +
        escapeHtml(block.url) +
        '" placeholder="https://"></div></div>'
      );
    }
    if (block.type === "spacer") {
      return '<input type="number" min="8" max="80" class="form-control dd-field" data-key="height" value="' + Number(block.height || 24) + '">';
    }
    return "";
  }

  function bindCanvas() {
    canvas.querySelectorAll(".dd-remove").forEach(function (btn) {
      btn.addEventListener("click", function () {
        blocks.splice(Number(btn.dataset.index), 1);
        render();
      });
    });
    canvas.querySelectorAll(".dd-field").forEach(function (input) {
      input.addEventListener("input", function () {
        const index = Number(input.closest(".dd-block").dataset.index);
        const key = input.dataset.key;
        blocks[index][key] = input.type === "number" ? Number(input.value) : input.value;
        EditorShared.syncFields(compile(), blocks);
      });
    });
    canvas.querySelectorAll(".dd-text").forEach(function (el) {
      el.addEventListener("input", function () {
        const index = Number(el.closest(".dd-block").dataset.index);
        blocks[index].html = el.innerHTML;
        EditorShared.syncFields(compile(), blocks);
      });
      el.addEventListener("paste", async function (event) {
        const file = Array.from(event.clipboardData?.items || [])
          .find(function (item) {
            return item.type.indexOf("image/") === 0;
          })
          ?.getAsFile();
        if (!file) return;
        event.preventDefault();
        const dataUrl = await EditorShared.fileToDataUrl(file);
        document.execCommand("insertHTML", false, '<img src="' + dataUrl + '" alt="" style="max-width:100%;height:auto;">');
      });
    });
    canvas.querySelectorAll(".dd-file").forEach(function (input) {
      input.addEventListener("change", async function () {
        const file = input.files && input.files[0];
        if (!file) return;
        const index = Number(input.closest(".dd-block").dataset.index);
        blocks[index].src = await EditorShared.fileToDataUrl(file);
        render();
      });
    });
    canvas.querySelectorAll(".dd-block").forEach(function (card) {
      card.addEventListener("dragstart", function () {
        card.classList.add("dragging");
      });
      card.addEventListener("dragend", function () {
        card.classList.remove("dragging");
        const ordered = Array.from(canvas.querySelectorAll(".dd-block")).map(function (el) {
          return blocks[Number(el.dataset.index)];
        });
        blocks = ordered.filter(Boolean);
        render();
      });
    });
    canvas.addEventListener("dragover", function (event) {
      event.preventDefault();
      const dragging = canvas.querySelector(".dragging");
      const target = event.target.closest(".dd-block");
      if (!dragging || !target || dragging === target) return;
      const rect = target.getBoundingClientRect();
      const after = event.clientY > rect.top + rect.height / 2;
      target.parentNode.insertBefore(dragging, after ? target.nextSibling : target);
    });
  }

  document.querySelectorAll(".dd-add").forEach(function (btn) {
    btn.addEventListener("click", function () {
      blocks.push(defaultBlock(btn.dataset.type));
      render();
    });
  });

  EditorShared.bindForm(compile, function () {
    return blocks;
  });
  render();
})();
