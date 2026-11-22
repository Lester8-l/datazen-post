(() => {
  "use strict";
  const deck = document.querySelector(".deck");
  const editButton = document.getElementById("btn-edit");
  const exportButton = document.getElementById("btn-png");
  if (!deck) return;

  const planElement = document.getElementById("dz-font-plan");
  const plan = planElement ? JSON.parse(planElement.textContent) : null;
  const fontStyle = document.getElementById("dz-edit-fonts");
  const compactChars = new Set(plan ? [...plan.compactChars] : []);
  const excluded = ".ruler, .ovf, [aria-hidden='true'], [data-noedit], a, button, script, style";
  const formatless = /[\s\u200B-\u200D\uFE0E\uFE0F]/u;
  const frames = [...deck.querySelectorAll(".card .frame")];
  let editing = false;
  let active = null;

  function families(element) {
    return getComputedStyle(element).fontFamily.split(",").map(font =>
      font.trim().replace(/^['"]|['"]$/g, "").toLowerCase()
    );
  }

  function covers(family, char) {
    const point = char.codePointAt(0);
    return plan.coverage[family]?.some(([first, last]) => point >= first && point <= last) ?? false;
  }

  function fontIssues(text, element) {
    if (!plan || !element) return [];
    const stack = families(element);
    if (!stack.some(family => plan.coverage[family])) return [];
    return [...new Set(text)].filter(char => !formatless.test(char) && !stack.some(family => covers(family, char)));
  }

  function exportFonts(card) {
    if (!plan) return window.__EMBED_CSS || "";
    const needed = new Set();
    for (const node of makeTextNodes(card.querySelector(".frame"))) {
      const newChars = [...new Set(node.data)].filter(char => !formatless.test(char) && !compactChars.has(char));
      if (!newChars.length) continue;
      const stack = families(node.parentElement);
      for (const char of newChars) {
        const face = stack.find(family => covers(family, char));
        if (face) needed.add(face);
      }
    }
    const extraCSS = [...(fontStyle?.sheet?.cssRules ?? [])].filter(rule =>
      rule.type === CSSRule.FONT_FACE_RULE && needed.has(rule.style.getPropertyValue("font-family").replace(/^['"]|['"]$/g, "").toLowerCase())
    ).map(rule => rule.cssText).join("\n");
    return plan.compactCSS + "\n" + extraCSS;
  }

  function makeTextNodes(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        return node.data.trim() && !node.parentElement?.closest(excluded)
          ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    return nodes;
  }

  function visibleRects(node) {
    const range = document.createRange();
    range.selectNodeContents(node);
    return [...range.getClientRects()].filter(rect => rect.width > 0 && rect.height > 0);
  }

  function atPoint(event, frame) {
    const position = document.caretPositionFromPoint?.(event.clientX, event.clientY);
    const range = position ? null : document.caretRangeFromPoint?.(event.clientX, event.clientY);
    const node = position?.offsetNode || range?.startContainer;
    const valid = candidate => candidate?.nodeType === Node.TEXT_NODE && candidate.data.trim() &&
      frame.contains(candidate) && !candidate.parentElement?.closest(excluded) &&
      visibleRects(candidate).some(rect => event.clientX >= rect.left - 2 && event.clientX <= rect.right + 2 &&
        event.clientY >= rect.top - 2 && event.clientY <= rect.bottom + 2);
    if (valid(node)) return node;
    return makeTextNodes(event.target).find(valid) ?? null;
  }

  function overflow(frame, focusNode) {
    const card = frame.closest(".card");
    const edge = card.getBoundingClientRect();
    const zoom = edge.width / card.offsetWidth || 1;
    const metrics = [
      Math.max(0, frame.scrollHeight - frame.clientHeight),
      Math.max(0, frame.scrollWidth - frame.clientWidth),
      0, 0, 0,
    ];
    for (const node of makeTextNodes(frame)) {
      for (const rect of visibleRects(node)) {
        metrics[2] = Math.max(metrics[2], (rect.right - edge.right) / zoom,
          (edge.left - rect.left) / zoom, (rect.bottom - edge.bottom) / zoom, (edge.top - rect.top) / zoom);
      }
    }
    const main = frame.querySelector(":scope > .main, :scope > .blk");
    const footer = frame.querySelector(":scope > .final-foot, :scope > .ruler, :scope > .meta, :scope > .src");
    if (main && footer && footer.getBoundingClientRect().height) {
      metrics[3] = Math.max(0, (main.getBoundingClientRect().bottom - footer.getBoundingClientRect().top) / zoom);
    }
    const parent = focusNode?.parentElement?.closest(".branch, .cmp .col, .right-table .tr > div, .row-copy");
    if (parent) {
      const box = parent.getBoundingClientRect();
      for (const rect of visibleRects(focusNode)) {
        metrics[4] = Math.max(metrics[4], (rect.right - box.right) / zoom);
      }
    }
    return metrics;
  }

  function plainText(value) {
    return value.normalize("NFC").replace(/[\t\r\n\u2028\u2029]+/gu, " ").trim();
  }

  if (editButton) {
    const style = document.createElement("style");
    style.textContent = "" +
      ".dz-editing .card .frame{cursor:text;outline:1px dashed #e5bb99;outline-offset:-5px}" +
      ".dz-edit-dialog{background:#fffdf8;color:#25382e;border:1px solid #c3c9bd;border-radius:12px;" +
      "padding:22px;width:min(510px,calc(100vw - 32px));font:16px/1.55 system-ui,sans-serif}" +
      ".dz-edit-dialog::backdrop{background:rgba(13,27,20,.68)}" +
      ".dz-edit-dialog h2{margin:0 0 8px;font:700 21px/1.35 system-ui,sans-serif}" +
      ".dz-edit-dialog p{margin:0 0 12px;font-size:14px}" +
      ".dz-edit-dialog textarea{box-sizing:border-box;width:100%;min-height:5em;resize:vertical;" +
      "padding:10px 12px;font:inherit;color:inherit;border:1px solid #acb8a9;border-radius:6px;background:#fff}" +
      ".dz-edit-dialog .dz-edit-error{color:#993d2c;min-height:1.45em;margin:6px 0}" +
      ".dz-edit-actions{display:flex;justify-content:flex-end;gap:10px}" +
      ".dz-edit-actions button{cursor:pointer;padding:7px 13px;font:inherit;border-radius:6px;" +
      "border:1px solid #526753;background:white;color:#25382e}" +
      ".dz-edit-actions button[type=submit]{background:#2c4838;color:white}";
    document.head.append(style);
    const dialog = document.createElement("dialog");
    dialog.className = "dz-edit-dialog";
    dialog.dataset.noexport = "";
    dialog.setAttribute("aria-labelledby", "dz-edit-title");
    dialog.innerHTML =
      '<form><h2 id="dz-edit-title">編輯字句</h2>' +
      '<p>點中嘅字句會沿用卡片上嘅字型、大小同顏色。</p>' +
      '<textarea aria-label="字句內容" rows="3"></textarea>' +
      '<p class="dz-edit-error" role="alert"></p>' +
      '<div class="dz-edit-actions"><button type="button" data-cancel>取消</button><button type="submit">套用文字</button></div></form>';
    document.body.append(dialog);
    const form = dialog.querySelector("form");
    const input = dialog.querySelector("textarea");
    const error = dialog.querySelector(".dz-edit-error");
    const save = form.querySelector('button[type="submit"]');

    editButton.setAttribute("aria-pressed", "false");
    editButton.addEventListener("click", () => {
      editing = !editing;
      deck.classList.toggle("dz-editing", editing);
      editButton.classList.toggle("on", editing);
      editButton.setAttribute("aria-pressed", String(editing));
      editButton.textContent = editing ? "完成編輯" : "編輯文字";
      editButton.title = editing ? "點一下卡片上要修改嘅字句" : "開啟改字模式";
    });
    deck.addEventListener("click", event => {
      if (!editing || dialog.open || !(event.target instanceof Element)) return;
      const frame = event.target.closest(".card .frame");
      if (!frame || event.target.closest(excluded)) return;
      const selected = atPoint(event, frame);
      if (!selected) return;
      event.preventDefault();
      active = { node: selected, frame };
      input.value = selected.data.trim();
      error.textContent = "";
      dialog.showModal();
      input.focus();
      input.select();
    });
    dialog.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => { active = null; });
    input.addEventListener("input", () => { error.textContent = ""; });
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!active || save.disabled) return;
      const { node, frame } = active;
      const value = plainText(input.value);
      if (!value) {
        error.textContent = "請輸入要套用嘅文字。";
        return;
      }
      const missing = fontIssues(value, node.parentElement);
      if (value.includes("\uFFFD") || missing.length) {
        error.textContent = "目前字型未收錄：" + (missing.slice(0, 4).join("、") || "貼上時損壞嘅字元");
        return;
      }
      const previous = node.data;
      const leading = previous.match(/^\s*/u)[0];
      const trailing = previous.match(/\s*$/u)[0];
      const before = overflow(frame, node);
      save.disabled = true;
      try {
        node.data = leading + value + trailing;
        await document.fonts?.ready;
        const after = overflow(frame, node);
        if (after.some((amount, index) => amount > Math.max(2, before[index] + 1))) {
          node.data = previous;
          error.textContent = "字句超出原有版面，縮短少少再套用。";
          return;
        }
        dialog.close();
      } catch (problem) {
        node.data = previous;
        error.textContent = "暫時未能套用呢句文字，請再試。";
        console.error(problem);
      } finally {
        save.disabled = false;
      }
    });
  }

  if (exportButton) exportButton.addEventListener("click", async () => {
    if (exportButton.disabled || typeof window.htmlToImage?.toPng !== "function") return;
    const label = exportButton.textContent;
    exportButton.disabled = true;
    try {
      await document.fonts?.ready;
      for (const [index, frame] of frames.entries()) {
        const card = frame.closest(".card");
        const bad = new Set(makeTextNodes(frame).flatMap(node => fontIssues(node.data, node.parentElement)));
        if (bad.size) throw Error("第 " + (index + 1) + " 張有未收錄字元 " + [...bad].slice(0, 4).join("、"));
        const css = exportFonts(card) || await window.htmlToImage.getFontEmbedCSS(card);
        exportButton.textContent = "匯出 " + (index + 1) + " / " + frames.length;
        const width = card.offsetWidth;
        const height = card.offsetHeight;
        const png = await window.htmlToImage.toPng(card, {
          width, height, canvasWidth: width, canvasHeight: height,
          pixelRatio: 1, fontEmbedCSS: css,
          filter: node => !(node.dataset?.noexport !== undefined || node.classList?.contains("ovf")),
        });
        const link = document.createElement("a");
        link.href = png;
        link.download = (card.dataset.filename || "card-" + (index + 1)) + ".png";
        document.body.append(link);
        link.click();
        link.remove();
        await new Promise(resolve => setTimeout(resolve, 250));
      }
      exportButton.textContent = "已匯出 " + frames.length + " 張";
    } catch (error) {
      console.error(error);
      exportButton.textContent = "匯出中斷";
      exportButton.title = String(error.message || error);
    } finally {
      setTimeout(() => {
        exportButton.textContent = label;
        exportButton.disabled = false;
      }, 1600);
    }
  });
})();

