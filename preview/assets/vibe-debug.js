/*
 * vibe-debug — минимальный клиент ревью (заглушка).
 *
 * Что умеет сейчас:
 *   - режим «Комментарий»: клик по странице ставит пин, привязанный к DOM-объекту
 *     под курсором, и открывает композер;
 *   - отправляет запись в POST /__review__/comments (схема — normalize_comment на
 *     сервере, см. schemas/vibe-debug-comment.schema.json);
 *   - показывает существующие пины для текущего маршрута и даёт сменить статус.
 *
 * Чего пока нет (осознанно, до появления реального фронтенда): режимы dev/art,
 * рисование, вложения-скриншоты, перетаскивание тулбара, drag пинов.
 * Docs: docs/VIBE-DEBUG.md
 */
(function () {
  "use strict";

  var API = "/__review__";
  var MODE = "vibe";
  var route = location.pathname || "/";
  var author = "";
  var displayAuthor = "";
  var armed = false;

  function el(tag, attrs, kids) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (k) { node.appendChild(k); });
    return node;
  }

  function cssPath(node) {
    if (!(node instanceof Element)) return ":root";
    if (node === document.documentElement) return ":root";
    if (node.id) return "#" + CSS.escape(node.id);
    var parts = [];
    while (node && node.nodeType === 1 && node !== document.documentElement) {
      var sel = node.nodeName.toLowerCase();
      var parent = node.parentElement;
      if (parent) {
        var sames = Array.prototype.filter.call(parent.children, function (c) {
          return c.nodeName === node.nodeName;
        });
        if (sames.length > 1) {
          sel += ":nth-of-type(" + (sames.indexOf(node) + 1) + ")";
        }
      }
      parts.unshift(sel);
      node = parent;
    }
    return parts.length ? parts.join(" > ") : ":root";
  }

  function targetInfo(node, selector) {
    if (!(node instanceof Element)) {
      return { selector: selector, element: "", sectionId: "", heading: "", label: "", excerpt: "" };
    }
    var section = node.closest("section, article, main, header, footer, nav") || node;
    var headingNode = section.querySelector("h1, h2, h3, h4, h5, h6");
    return {
      selector: selector,
      element: node.nodeName.toLowerCase(),
      sectionId: section.id || "",
      heading: headingNode ? headingNode.textContent.trim().slice(0, 240) : "",
      label: (node.getAttribute("aria-label") || node.getAttribute("alt") || "").slice(0, 240),
      excerpt: (node.textContent || "").replace(/\s+/g, " ").trim().slice(0, 800),
    };
  }

  function api(path, options) {
    return fetch(API + path, Object.assign({ headers: { "Content-Type": "application/json" } }, options))
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || r.status); return j; }); });
  }

  function removeTransient() {
    document.querySelectorAll(".vd-card, .vd-list").forEach(function (n) { n.remove(); });
  }

  function anchorFor(node, clientX, clientY) {
    var rect = node instanceof Element ? node.getBoundingClientRect() : { left: 0, top: 0, width: 1, height: 1 };
    var w = rect.width || 1;
    var h = rect.height || 1;
    return {
      x: Math.min(1, Math.max(0, (clientX - rect.left) / w)),
      y: Math.min(1, Math.max(0, (clientY - rect.top) / h)),
      offsetX: Math.round(clientX - rect.left),
      offsetY: Math.round(clientY - rect.top),
      targetWidth: Math.round(w),
      targetHeight: Math.round(h),
    };
  }

  function placePin(comment) {
    var node = null;
    try { node = document.querySelector(comment.selector); } catch (e) { node = null; }
    var host = node || document.body;
    var rect = host.getBoundingClientRect();
    var a = comment.anchor || {};
    var pin = el("div", { class: "vd-pin", "data-status": comment.status, title: comment.text.slice(0, 120) });
    pin.style.left = window.scrollX + rect.left + (a.x || 0.5) * rect.width + "px";
    pin.style.top = window.scrollY + rect.top + (a.y || 0.5) * rect.height + "px";
    pin.addEventListener("click", function (ev) {
      ev.stopPropagation();
      openCard(comment, ev.clientX, ev.clientY);
    });
    document.body.appendChild(pin);
  }

  function renderPins() {
    document.querySelectorAll(".vd-pin").forEach(function (n) { n.remove(); });
    return api("/comments?route=" + encodeURIComponent(route)).then(function (j) {
      (j.comments || []).forEach(placePin);
      return j.comments || [];
    });
  }

  function openCard(comment, x, y) {
    removeTransient();
    var card = el("div", { class: "vd-card" });
    card.style.left = Math.min(x, window.innerWidth - 340) + "px";
    card.style.top = Math.min(y, window.innerHeight - 200) + "px";
    card.appendChild(el("div", { class: "vd-muted", text: comment.displayAuthor + " · " + comment.status + " · " + comment.id }));
    card.appendChild(el("p", { text: comment.text }));
    var statuses = ["approved", "in_progress", "resolved", "wont_fix"];
    var row = el("div", { class: "vd-row" });
    statuses.forEach(function (s) {
      var b = el("button", { text: s });
      b.addEventListener("click", function () {
        api("/comments/status", { method: "POST", body: JSON.stringify({ id: comment.id, status: s }) })
          .then(function () { removeTransient(); renderPins(); });
      });
      row.appendChild(b);
    });
    card.appendChild(row);
    document.body.appendChild(card);
  }

  function openComposer(node, selector, anchor, x, y) {
    removeTransient();
    var card = el("div", { class: "vd-card" });
    card.style.left = Math.min(x, window.innerWidth - 340) + "px";
    card.style.top = Math.min(y, window.innerHeight - 220) + "px";
    card.appendChild(el("div", { class: "vd-muted", text: selector }));
    var area = el("textarea", { placeholder: "Что не так на этом объекте?" });
    card.appendChild(area);
    var row = el("div", { class: "vd-row" });
    var cancel = el("button", { text: "Отмена" });
    cancel.addEventListener("click", removeTransient);
    var save = el("button", { class: "vd-primary", text: "Сохранить" });
    save.addEventListener("click", function () {
      var text = area.value.trim();
      if (!text) { area.focus(); return; }
      api("/comments", {
        method: "POST",
        body: JSON.stringify({
          route: route,
          selector: selector,
          mode: MODE,
          text: text,
          displayAuthor: displayAuthor || author || "reviewer",
          author: author || displayAuthor || "reviewer",
          pageTitle: document.title,
          url: location.href,
          anchor: anchor,
          target: targetInfo(node, selector),
          viewport: { width: window.innerWidth, height: window.innerHeight },
        }),
      }).then(function () { removeTransient(); renderPins(); })
        .catch(function (e) { alert("Не сохранилось: " + e.message); });
    });
    row.appendChild(cancel);
    row.appendChild(save);
    card.appendChild(row);
    document.body.appendChild(card);
    area.focus();
  }

  function onArmedClick(ev) {
    if (ev.target.closest(".vd-bar, .vd-card, .vd-list, .vd-pin")) return;
    ev.preventDefault();
    ev.stopPropagation();
    var node = ev.target;
    var selector = cssPath(node);
    var anchor = anchorFor(node, ev.clientX, ev.clientY);
    setArmed(false);
    openComposer(node, selector, anchor, ev.clientX, ev.clientY);
  }

  function setArmed(next) {
    armed = next;
    document.documentElement.classList.toggle("vd-armed", armed);
    var btn = document.querySelector(".vd-bar [data-vd='comment']");
    if (btn) btn.setAttribute("aria-pressed", String(armed));
    if (armed) document.addEventListener("click", onArmedClick, true);
    else document.removeEventListener("click", onArmedClick, true);
  }

  function openList() {
    removeTransient();
    var panel = el("div", { class: "vd-list" });
    panel.appendChild(el("div", { class: "vd-row" }, [
      el("strong", { text: "Комментарии · " + route }),
    ]));
    api("/comments?route=" + encodeURIComponent(route)).then(function (j) {
      var items = j.comments || [];
      if (!items.length) {
        panel.appendChild(el("p", { class: "vd-muted", text: "Пока пусто." }));
      }
      items.forEach(function (c) {
        var item = el("div", { class: "vd-item" });
        item.appendChild(el("div", { text: c.text }));
        item.appendChild(el("div", { class: "vd-meta", text: c.displayAuthor + " · " + c.status + " · " + c.id + " · " + c.selector }));
        panel.appendChild(item);
      });
    });
    document.body.appendChild(panel);
  }

  function mountBar() {
    var bar = el("div", { class: "vd-bar" });
    var comment = el("button", { "data-vd": "comment", "aria-pressed": "false", text: "Комментарий" });
    comment.addEventListener("click", function () { removeTransient(); setArmed(!armed); });
    var list = el("button", { "data-vd": "list", text: "Список" });
    list.addEventListener("click", openList);
    bar.appendChild(comment);
    bar.appendChild(list);
    document.body.appendChild(bar);
  }

  api("/session").then(function (j) { author = j.author || ""; }).catch(function () {});
  try { displayAuthor = localStorage.getItem("vd-display-author") || ""; } catch (e) {}
  if (!displayAuthor && author) displayAuthor = author;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { mountBar(); renderPins(); });
  } else {
    mountBar();
    renderPins();
  }
  window.addEventListener("resize", function () { renderPins(); });
})();
