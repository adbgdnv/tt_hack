(function () {
  'use strict';

  var API = '/__review__';
  var route = location.pathname === '/' ? '/index.html' : location.pathname;
  var comments = [];
  var allComments = [];
  var marks = [];
  var accountAuthor = '';
  var selectedTarget = null;
  var pickerActive = false;
  var pickerCandidates = [];
  var pickerHovered = null;
  var pickerPointerTarget = null;
  var pickerAncestors = [];
  var pickerAncestorIndex = 0;
  var pickerPointer = null;
  var lastTrigger = null;
  var mode = readMode();
  var selectedAnchor = null;
  var activeArtCommentId = '';
  var activeTool = 'comment';
  var commentPlacementPending = false;
  var DEFAULT_DRAW_COLOR = '#a96f7b';
  var drawStyle = readDrawStyle();
  var drawing = null;
  var selectedMarkId = '';
  var draggingMark = null;
  var toolbarDrag = null;
  var panelDrag = null;
  var markUndoStack = [];
  var undoBusy = false;
  var pendingAttachments = { dev: [], vibe: [] };
  var attachmentUploads = { dev: 0, vibe: 0 };
  var attachmentGeneration = { dev: 0, vibe: 0 };
  var linkedCommentHandled = false;
  var focusedCommentTarget = null;
  var MAX_ATTACHMENTS = 6;
  var MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;
  var IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

  var statusLabels = {
    'new': 'Новый',
    'approved': 'Подтверждён',
    'in_progress': 'В работе',
    'resolved': 'Исправлен',
    'wont_fix': 'Не исправлять'
  };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (typeof text === 'string') node.textContent = text;
    return node;
  }

  function readMode() {
    return 'view';
  }

  function readDrawStyle() {
    try {
      var saved = JSON.parse(localStorage.getItem('vibe-debug-draw-style') || '{}');
      var color = /^#[0-9a-f]{6}$/i.test(saved.color || '') ? saved.color.toLowerCase() : DEFAULT_DRAW_COLOR;
      if (color === '#7c3aed' || color === '#5b21b6' || color === '#a99563') color = DEFAULT_DRAW_COLOR;
      return {
        color: color,
        thickness: clamp(Number(saved.thickness) || 4, 1, 24)
      };
    } catch {
      return { color: DEFAULT_DRAW_COLOR, thickness: 4 };
    }
  }

  function rememberDrawStyle() {
    try { localStorage.setItem('vibe-debug-draw-style', JSON.stringify(drawStyle)); } catch {}
  }

  function readToolbarPosition() {
    try {
      var saved = JSON.parse(localStorage.getItem('vibe-debug-toolbar-position') || 'null');
      return saved && Number.isFinite(saved.left) && Number.isFinite(saved.top) ? saved : null;
    } catch {
      return null;
    }
  }

  function placeToolbar(position) {
    var toolbar = document.querySelector('.vd-toolbar');
    if (!toolbar) return;
    if (!position) {
      toolbar.style.removeProperty('left');
      toolbar.style.removeProperty('top');
      toolbar.style.removeProperty('right');
      toolbar.style.removeProperty('bottom');
      toolbar.style.removeProperty('transform');
      positionDrawSettings();
      return;
    }
    var left = clamp(position.left, 8, Math.max(8, window.innerWidth - toolbar.offsetWidth - 8));
    var top = clamp(position.top, 8, Math.max(8, window.innerHeight - toolbar.offsetHeight - 8));
    toolbar.style.left = Math.round(left) + 'px';
    toolbar.style.top = Math.round(top) + 'px';
    toolbar.style.right = 'auto';
    toolbar.style.bottom = 'auto';
    toolbar.style.transform = 'none';
    positionDrawSettings();
  }

  function positionDrawSettings() {
    var toolbar = document.querySelector('.vd-toolbar');
    var settings = document.getElementById('vd-draw-settings');
    if (!toolbar || !settings || settings.hidden) return;
    var toolbarRect = toolbar.getBoundingClientRect();
    var width = settings.offsetWidth;
    var height = settings.offsetHeight;
    var left = toolbarRect.left - width - 10;
    if (left < 8) left = toolbarRect.right + 10;
    left = clamp(left, 8, Math.max(8, window.innerWidth - width - 8));
    var top = clamp(toolbarRect.top, 8, Math.max(8, window.innerHeight - height - 8));
    settings.style.left = Math.round(left) + 'px';
    settings.style.top = Math.round(top) + 'px';
    settings.style.bottom = 'auto';
    settings.style.transform = 'none';
  }

  function beginToolbarDrag(event) {
    if (event.button !== 0) return;
    if (event.target.closest('button, input, textarea, select, a, [role="button"]')) return;
    var toolbar = event.currentTarget.closest('.vd-toolbar');
    if (!toolbar) return;
    event.preventDefault();
    var rectangle = toolbar.getBoundingClientRect();
    toolbarDrag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      left: rectangle.left,
      top: rectangle.top,
      handle: toolbar
    };
    toolbar.classList.add('vd-toolbar--dragging');
    if (toolbar.setPointerCapture) toolbar.setPointerCapture(event.pointerId);
  }

  function moveToolbarDrag(event) {
    if (!toolbarDrag || event.pointerId !== toolbarDrag.pointerId) return false;
    event.preventDefault();
    placeToolbar({
      left: toolbarDrag.left + event.clientX - toolbarDrag.startX,
      top: toolbarDrag.top + event.clientY - toolbarDrag.startY
    });
    return true;
  }

  function finishToolbarDrag(event) {
    if (!toolbarDrag || event.pointerId !== toolbarDrag.pointerId) return false;
    var toolbar = document.querySelector('.vd-toolbar');
    toolbarDrag = null;
    if (toolbar) {
      toolbar.classList.remove('vd-toolbar--dragging');
      var rectangle = toolbar.getBoundingClientRect();
      try {
        localStorage.setItem('vibe-debug-toolbar-position', JSON.stringify({
          left: Math.round(rectangle.left),
          top: Math.round(rectangle.top)
        }));
      } catch {}
    }
    return true;
  }

  function readPanelPosition() {
    try {
      var saved = JSON.parse(localStorage.getItem('vibe-debug-panel-position') || 'null');
      return saved && Number.isFinite(saved.left) && Number.isFinite(saved.top) ? saved : null;
    } catch {
      return null;
    }
  }

  function placePanel(position) {
    var panel = document.getElementById('vd-panel');
    if (!panel) return;
    if (!position) {
      panel.style.removeProperty('left');
      panel.style.removeProperty('top');
      panel.style.removeProperty('right');
      panel.style.removeProperty('bottom');
      return;
    }
    var left = clamp(position.left, 8, Math.max(8, window.innerWidth - panel.offsetWidth - 8));
    var top = clamp(position.top, 8, Math.max(8, window.innerHeight - panel.offsetHeight - 8));
    panel.style.left = Math.round(left) + 'px';
    panel.style.top = Math.round(top) + 'px';
    panel.style.right = 'auto';
    panel.style.bottom = 'auto';
  }

  function beginPanelDrag(event) {
    if (event.button !== 0) return;
    if (event.target.closest('button, input, textarea, select, a, [role="button"]')) return;
    var panel = event.currentTarget.closest('.vd-panel');
    if (!panel || panel.hidden) return;
    event.preventDefault();
    var rectangle = panel.getBoundingClientRect();
    panelDrag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      left: rectangle.left,
      top: rectangle.top,
      handle: event.currentTarget
    };
    panel.classList.add('vd-panel--dragging');
    if (event.currentTarget.setPointerCapture) event.currentTarget.setPointerCapture(event.pointerId);
  }

  function movePanelDrag(event) {
    if (!panelDrag || event.pointerId !== panelDrag.pointerId) return false;
    event.preventDefault();
    placePanel({
      left: panelDrag.left + event.clientX - panelDrag.startX,
      top: panelDrag.top + event.clientY - panelDrag.startY
    });
    return true;
  }

  function finishPanelDrag(event) {
    if (!panelDrag || event.pointerId !== panelDrag.pointerId) return false;
    var panel = document.getElementById('vd-panel');
    panelDrag = null;
    if (panel) {
      panel.classList.remove('vd-panel--dragging');
      var rectangle = panel.getBoundingClientRect();
      try {
        localStorage.setItem('vibe-debug-panel-position', JSON.stringify({
          left: Math.round(rectangle.left),
          top: Math.round(rectangle.top)
        }));
      } catch {}
    }
    return true;
  }

  function displayAuthor() {
    var input = document.querySelector('[data-vd-author]');
    return input ? input.value.trim() : '';
  }

  function rememberDisplayAuthor(value) {
    try { localStorage.setItem('vibe-debug-display-author', value); } catch {}
    setAuthorValues(value, false);
  }

  function addStyle() {
    if (document.querySelector('link[data-vibe-debug-style]')) return;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/vibe-debug.css?v=20260828-vibe21';
    link.setAttribute('data-vibe-debug-style', '');
    document.head.appendChild(link);
  }

  function pasteShortcutLabel(userAgent) {
    return /Macintosh|Mac OS X|iPhone|iPad|iPod/i.test(userAgent || '') ? '⌘V' : 'Ctrl+V';
  }

  function ensureDebugId(node, fallbackIndex) {
    if (!node || node.id || node.hasAttribute('data-debug-id')) return;
    var sectionId = node.querySelector(':scope > .section__id');
    var heading = node.matches('h1, h2, h3, h4') ? node : node.querySelector('h1, h2, h3, h4');
    var kind = node.matches('header.hdr') ? 'site-header' :
      node.matches('footer.ftr') ? 'site-footer' :
      node.matches('.empty') ? 'empty-state' :
      node.matches('.card') ? 'card' :
      node.matches('form') ? 'form' :
      node.matches('.wrap') ? 'page-content' : 'block';
    var safeIndex = Math.max(0, fallbackIndex) + 1;
    var source = sectionId ? sectionId.textContent : (heading ? heading.textContent : kind + '-' + safeIndex);
    var slug = (source || kind + '-' + safeIndex)
      .toLowerCase()
      .replace(/[^a-z0-9а-яё]+/gi, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 80);
    node.setAttribute('data-debug-id', slug || kind + '-' + safeIndex);
  }

  function pageTargets() {
    var nodes = Array.prototype.slice.call(document.querySelectorAll(
      'header.hdr, main > .wrap, main .section, main section, main article, main form, main .card, main .empty, main .tabs, main .accordion, footer.ftr'
    ));
    var unique = [];
    nodes.forEach(function (node) {
      if (node.closest('[data-vibe-debug-ui]') || unique.indexOf(node) !== -1) return;
      unique.push(node);
    });
    unique.forEach(function (node, index) {
      ensureDebugId(node, index);
    });
    return unique;
  }

  function elementAtPointer(target) {
    if (!target || !target.closest) return null;
    if (target.closest('[data-vibe-debug-ui], .vd-pin')) return undefined;
    if (target === document.body || target === document.documentElement) return null;
    return target;
  }

  function elementAncestors(node) {
    var ancestors = [];
    var current = node;
    while (current && current.nodeType === 1 && current !== document.body) {
      if (!current.closest('[data-vibe-debug-ui]')) ancestors.push(current);
      if (current.matches('main, header.hdr, footer.ftr')) break;
      current = current.parentElement;
    }
    return ancestors;
  }

  function shortElementName(node) {
    var name = node.tagName.toLowerCase();
    if (node.id) return name + '#' + node.id;
    if (node.hasAttribute('data-debug-id')) {
      return name + '[data-debug-id="' + node.getAttribute('data-debug-id') + '"]';
    }
    if (node.classList && node.classList.length) return name + '.' + node.classList[0];
    return name;
  }

  function cssEscape(value) {
    if (window.CSS && CSS.escape) return CSS.escape(value);
    return value.replace(/[^a-zA-Z0-9_-]/g, function (character) {
      return '\\' + character;
    });
  }

  function cssPath(node) {
    if (!node || node === document.documentElement) return ':root';
    if (node.id) return '#' + cssEscape(node.id);
    if (node.hasAttribute('data-debug-id')) {
      return '[data-debug-id="' + node.getAttribute('data-debug-id').replace(/"/g, '\\"') + '"]';
    }
    var parts = [];
    var current = node;
    while (current && current.nodeType === 1 && current !== document.body) {
      if (current.id) {
        parts.unshift('#' + cssEscape(current.id));
        break;
      }
      if (current.hasAttribute('data-debug-id')) {
        parts.unshift('[data-debug-id="' + current.getAttribute('data-debug-id').replace(/"/g, '\\"') + '"]');
        break;
      }
      var part = current.tagName.toLowerCase();
      var classes = current.classList
        ? Array.prototype.slice.call(current.classList).filter(function (name) {
            return name.indexOf('vd-') !== 0;
          }).slice(0, 2)
        : [];
      if (classes.length) part += '.' + classes.map(cssEscape).join('.');
      var siblings = current.parentElement
        ? Array.prototype.filter.call(current.parentElement.children, function (sibling) {
            return sibling.tagName === current.tagName;
          })
        : [];
      if (siblings.length > 1) part += ':nth-of-type(' + (siblings.indexOf(current) + 1) + ')';
      parts.unshift(part);
      if (current.tagName.toLowerCase() === 'main') break;
      current = current.parentElement;
    }
    return parts.join(' > ') || ':root';
  }

  function cleanText(node) {
    if (!node) return '';
    var clone = node.cloneNode(true);
    clone.querySelectorAll('.note, .spec-bar, script, style, [data-vibe-debug-ui]').forEach(function (item) {
      item.remove();
    });
    return (clone.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 800);
  }

  function targetContext(node) {
    if (!node) {
      return {
        selector: ':root',
        element: 'page',
        sectionId: '',
        heading: document.title || '',
        label: 'Вся страница',
        excerpt: cleanText(document.querySelector('main')).slice(0, 400)
      };
    }
    var heading = node.matches('h1, h2, h3, h4') ? node : node.querySelector('h1, h2, h3, h4');
    var sectionId = node.querySelector(':scope > .section__id');
    var headingText = heading ? heading.textContent.trim() : '';
    var idText = sectionId ? sectionId.textContent.trim() : (node.id || '');
    var friendlyLabel = headingText || idText;
    if (!friendlyLabel && node.matches('header.hdr')) friendlyLabel = 'Шапка сайта';
    if (!friendlyLabel && node.matches('footer.ftr')) friendlyLabel = 'Подвал сайта';
    if (!friendlyLabel && node.matches('.empty')) friendlyLabel = 'Пустое состояние';
    if (!friendlyLabel && node.matches('.card')) friendlyLabel = 'Карточка';
    if (!friendlyLabel && node.matches('form')) friendlyLabel = 'Форма';
    if (!friendlyLabel && node.matches('.wrap')) friendlyLabel = 'Содержимое страницы';
    var ownText = cleanText(node).slice(0, 90);
    if (!friendlyLabel && node.matches('p, span, li, a, button, label, small, strong, em')) {
      friendlyLabel = ownText ? 'Текст: ' + ownText : 'Текстовый элемент';
    }
    if (!friendlyLabel && node.matches('img')) {
      friendlyLabel = node.getAttribute('alt') || 'Изображение';
    }
    if (!friendlyLabel && node.matches('div')) {
      friendlyLabel = node.classList.length ? 'Блок .' + node.classList[0] : 'Блок div';
    }
    return {
      selector: cssPath(node),
      element: node.tagName.toLowerCase(),
      sectionId: idText,
      heading: headingText,
      label: friendlyLabel || node.tagName.toLowerCase(),
      excerpt: cleanText(node)
    };
  }

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
  }

  function anchorContext(node, point) {
    if (!node || !point) return null;
    var rectangle = node.getBoundingClientRect();
    if (!rectangle.width || !rectangle.height) return null;
    var offsetX = clamp(point.clientX - rectangle.left, 0, rectangle.width);
    var offsetY = clamp(point.clientY - rectangle.top, 0, rectangle.height);
    return {
      x: Number((offsetX / rectangle.width).toFixed(4)),
      y: Number((offsetY / rectangle.height).toFixed(4)),
      offsetX: Math.round(offsetX),
      offsetY: Math.round(offsetY),
      targetWidth: Math.round(rectangle.width),
      targetHeight: Math.round(rectangle.height)
    };
  }

  function defaultAnchor(node) {
    if (!node) return null;
    var rectangle = node.getBoundingClientRect();
    return {
      x: 0.94,
      y: Math.min(0.18, 18 / Math.max(rectangle.height, 1)),
      offsetX: Math.round(rectangle.width * 0.94),
      offsetY: Math.min(18, Math.round(rectangle.height * 0.18)),
      targetWidth: Math.round(rectangle.width),
      targetHeight: Math.round(rectangle.height)
    };
  }

  function resolveTarget(selector) {
    if (!selector || selector === ':root') return null;
    try { return document.querySelector(selector); } catch { return null; }
  }

  function anchorPosition(target, anchor) {
    var rectangle = target.getBoundingClientRect();
    var x = anchor && Number.isFinite(Number(anchor.x)) ? Number(anchor.x) : 0.94;
    var y = anchor && Number.isFinite(Number(anchor.y)) ? Number(anchor.y) : 0.08;
    return {
      left: rectangle.left + window.scrollX + rectangle.width * clamp(x, 0, 1),
      top: rectangle.top + window.scrollY + rectangle.height * clamp(y, 0, 1)
    };
  }

  function request(path, options) {
    return fetch(API + path, options).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (payload) {
        if (!response.ok) throw new Error(payload.error || 'Ошибка запроса.');
        return payload;
      });
    });
  }

  function cloneValue(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function announceReview(text) {
    var live = document.querySelector('[data-vd-mode-live]');
    if (live) live.textContent = text;
  }

  function rememberMarkAction(action) {
    markUndoStack.push(action);
    if (markUndoStack.length > 50) markUndoStack.shift();
  }

  function remapUndoMarkId(previousId, nextId) {
    markUndoStack.forEach(function (action) {
      if (action.markId === previousId) action.markId = nextId;
      if (action.mark && action.mark.id === previousId) action.mark.id = nextId;
    });
  }

  function markCreationPayload(mark) {
    return {
      kind: mark.kind,
      route: mark.route,
      pageTitle: mark.page && mark.page.title || document.title,
      url: mark.page && mark.page.url || location.href,
      selector: mark.selector,
      target: mark.target,
      viewport: mark.viewport,
      author: accountAuthor || displayAuthor() || mark.author || 'anonymous',
      displayAuthor: mark.displayAuthor || displayAuthor() || accountAuthor || 'anonymous',
      style: mark.style,
      geometry: mark.geometry
    };
  }

  function undoLastMarkAction() {
    if (undoBusy) {
      announceReview('Отмена уже выполняется');
      return;
    }
    var action = markUndoStack.pop();
    if (!action) {
      announceReview('Нет действий с пометками для отмены');
      return;
    }
    undoBusy = true;
    var operation;
    if (action.kind === 'create') {
      operation = request('/marks/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: action.markId })
      }).then(function () {
        marks = marks.filter(function (mark) { return mark.id !== action.markId; });
        if (selectedMarkId === action.markId) clearMarkSelection();
        renderMarks();
        announceReview('Добавление пометки отменено');
      });
    } else if (action.kind === 'delete') {
      operation = request('/marks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(markCreationPayload(action.mark))
      }).then(function (payload) {
        marks.push(payload.mark);
        remapUndoMarkId(action.mark.id, payload.mark.id);
        selectedMarkId = payload.mark.id;
        renderMarks();
        announceReview('Удаление пометки отменено');
      });
    } else if (action.kind === 'geometry') {
      operation = request('/marks/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: action.markId,
          geometry: action.geometry,
          author: accountAuthor || displayAuthor() || 'anonymous'
        })
      }).then(function (payload) {
        marks = marks.map(function (mark) { return mark.id === payload.mark.id ? payload.mark : mark; });
        selectedMarkId = payload.mark.id;
        renderMarks();
        announceReview('Перемещение пометки отменено');
      });
    } else {
      operation = Promise.reject(new Error('Неизвестное действие отмены'));
    }
    operation.catch(function (error) {
      markUndoStack.push(action);
      announceReview(error.message || 'Не удалось отменить действие');
      return loadMarks();
    }).finally(function () {
      undoBusy = false;
    });
  }

  function setMessage(text, kind) {
    var node = document.querySelector('[data-vd-message]');
    if (!node) return;
    node.textContent = text;
    node.setAttribute('data-kind', kind || 'info');
  }

  function setPanel(open) {
    var panel = document.getElementById('vd-panel');
    var toggle = document.getElementById('vd-list-toggle');
    var title = document.getElementById('vd-panel-title');
    var actions = panel.querySelector('[data-vd-panel-actions]');
    if (open && mode === 'vibe') commentPlacementPending = false;
    title.textContent = mode === 'view' ? 'Все комментарии' : 'Комментарии к странице';
    actions.hidden = mode === 'view';
    panel.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    syncCommentPlacement();
    if (open) placePanel(readPanelPosition());
    if (open) title.focus();
    else {
      clearFocusedComment();
      if (lastTrigger) lastTrigger.focus();
    }
  }

  function openForm(target, anchor) {
    stopPicker();
    resetAttachments('dev', true);
    selectedTarget = target || targetContext(null);
    selectedAnchor = anchor || null;
    var select = document.getElementById('vd-target');
    var targets = [targetContext(null)].concat(pageTargets().map(targetContext));
    if (!targets.some(function (item) { return item.selector === selectedTarget.selector; })) {
      targets.splice(1, 0, selectedTarget);
    }
    select.replaceChildren();
    targets.forEach(function (item, index) {
      var option = document.createElement('option');
      option.value = String(index);
      option.textContent = item.label + (item.sectionId && item.sectionId !== item.label ? ' · ' + item.sectionId : '');
      option.dataset.target = JSON.stringify(item);
      if (item.selector === selectedTarget.selector) option.selected = true;
      select.appendChild(option);
    });
    var dialog = document.getElementById('vd-dialog');
    dialog.showModal();
    document.getElementById('vd-comment').focus();
  }

  function closeForm(discardAttachments) {
    if (discardAttachments !== false) resetAttachments('dev', true);
    var dialog = document.getElementById('vd-dialog');
    if (dialog.open) dialog.close();
    if (mode === 'dev') requestAnimationFrame(function () { startPicker(document.querySelector('[data-vd-mode-value="dev"]')); });
  }

  function setAuthorValues(value, readOnly) {
    document.querySelectorAll('[data-vd-author]').forEach(function (input) {
      input.value = value || '';
      input.readOnly = Boolean(readOnly);
    });
  }

  function positionFloating(surface, position) {
    if (!surface || !position) return;
    var gap = 14;
    var left = clamp(
      position.left + gap,
      window.scrollX + 8,
      window.scrollX + window.innerWidth - surface.offsetWidth - 8
    );
    var top = position.top + gap;
    if (top + surface.offsetHeight > window.scrollY + window.innerHeight - 8) {
      top = position.top - surface.offsetHeight - gap;
    }
    surface.style.left = Math.round(left) + 'px';
    surface.style.top = Math.round(Math.max(window.scrollY + 8, top)) + 'px';
  }

  function syncCommentPlacement() {
    var composer = document.getElementById('vd-art-composer');
    var thread = document.getElementById('vd-art-thread');
    var panel = document.getElementById('vd-panel');
    var reviewSurfaceOpen = Boolean(
      composer && !composer.hidden ||
      thread && !thread.hidden ||
      panel && !panel.hidden
    );
    var active = mode === 'vibe' && activeTool === 'comment' && commentPlacementPending && !reviewSurfaceOpen;
    document.documentElement.setAttribute('data-vd-comment-placement', String(active));
  }

  function closeArtComposer(discardAttachments) {
    if (discardAttachments !== false) resetAttachments('vibe', true);
    var composer = document.getElementById('vd-art-composer');
    if (composer) composer.hidden = true;
    syncCommentPlacement();
  }

  function openArtComposer(target, anchor) {
    stopPicker();
    commentPlacementPending = false;
    resetAttachments('vibe', true);
    selectedTarget = target || targetContext(null);
    selectedAnchor = anchor || null;
    var composer = document.getElementById('vd-art-composer');
    var targetNode = resolveTarget(selectedTarget.selector);
    var position = targetNode
      ? anchorPosition(targetNode, selectedAnchor || defaultAnchor(targetNode))
      : { left: window.scrollX + window.innerWidth / 2, top: window.scrollY + window.innerHeight / 2 };
    composer.querySelector('[data-vd-art-target]').textContent = selectedTarget.label || 'Вся страница';
    composer.hidden = false;
    syncCommentPlacement();
    positionFloating(composer, position);
    document.getElementById('vd-art-comment').focus();
  }

  function closeArtThread() {
    activeArtCommentId = '';
    var thread = document.getElementById('vd-art-thread');
    if (thread) thread.hidden = true;
    document.querySelectorAll('.vd-pin[aria-expanded="true"]').forEach(function (pin) {
      pin.setAttribute('aria-expanded', 'false');
    });
    syncCommentPlacement();
  }

  function setMode(nextMode, announce) {
    mode = nextMode === 'dev' || nextMode === 'vibe' ? nextMode : 'view';
    commentPlacementPending = mode === 'vibe';
    document.documentElement.setAttribute('data-vd-mode', mode);
    document.querySelectorAll('[data-vd-mode-value]').forEach(function (button) {
      var active = button.getAttribute('data-vd-mode-value') === mode;
      button.setAttribute('aria-pressed', String(active));
      button.setAttribute('tabindex', active ? '0' : '-1');
    });
    if (mode === 'view') {
      stopPicker();
      setPanel(false);
      closeForm();
      closeArtComposer();
      closeArtThread();
      clearMarkSelection();
    }
    else if (mode === 'vibe') {
      stopPicker();
      setPanel(false);
    }
    else {
      closeArtComposer();
      closeArtThread();
      clearMarkSelection();
      requestAnimationFrame(function () {
        if (mode === 'dev') startPicker(document.querySelector('[data-vd-mode-value="dev"]'));
      });
    }
    renderPins();
    renderMarks();
    renderList();
    syncCommentPlacement();
    if (mode === 'view') loadAllComments();
    if (announce) {
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = 'Включён режим ' + mode;
    }
  }

  function ensurePickerChrome() {
    if (!document.getElementById('vd-picker-highlight')) {
      var highlight = el('div', 'vd-picker-highlight');
      highlight.id = 'vd-picker-highlight';
      highlight.setAttribute('data-vibe-debug-ui', '');
      highlight.setAttribute('aria-hidden', 'true');
      document.body.appendChild(highlight);
    }
    if (!document.getElementById('vd-picker-label')) {
      var label = el('div', 'vd-picker-label');
      label.id = 'vd-picker-label';
      label.setAttribute('data-vibe-debug-ui', '');
      label.setAttribute('aria-hidden', 'true');
      label.innerHTML = '<strong data-vd-picker-name></strong><code data-vd-picker-selector></code><span data-vd-picker-path></span>';
      document.body.appendChild(label);
    }
  }

  function updatePickerHighlight(node, announce) {
    pickerHovered = node || null;
    var highlight = document.getElementById('vd-picker-highlight');
    var label = document.getElementById('vd-picker-label');
    if (!highlight || !label) return;
    if (!node) {
      highlight.hidden = true;
      label.hidden = true;
      return;
    }
    var context = targetContext(node);
    var rectangle = node.getBoundingClientRect();
    highlight.hidden = false;
    highlight.style.left = (rectangle.left + window.scrollX) + 'px';
    highlight.style.top = (rectangle.top + window.scrollY) + 'px';
    highlight.style.width = rectangle.width + 'px';
    highlight.style.height = rectangle.height + 'px';

    label.hidden = false;
    label.querySelector('[data-vd-picker-name]').textContent = context.element + ' · ' + context.label;
    label.querySelector('[data-vd-picker-selector]').textContent = context.selector;
    var currentIndex = pickerAncestors.indexOf(node);
    var pathNodes = currentIndex >= 0 ? pickerAncestors.slice(currentIndex).reverse() : [node];
    label.querySelector('[data-vd-picker-path]').textContent = pathNodes.map(shortElementName).join(' › ');
    if (announce) {
      var live = document.querySelector('[data-vd-picker-live]');
      if (live) live.textContent = 'Выбран элемент: ' + context.element + ', ' + context.label;
    }
    var labelLeft = Math.max(8, Math.min(rectangle.left + window.scrollX, window.scrollX + window.innerWidth - 328));
    var labelTop = rectangle.top + window.scrollY - label.offsetHeight - 6;
    if (labelTop < window.scrollY + 8) labelTop = rectangle.top + window.scrollY + 8;
    label.style.left = labelLeft + 'px';
    label.style.top = labelTop + 'px';
  }

  function setPickerTarget(node, announce) {
    pickerPointerTarget = node || null;
    pickerAncestors = node ? elementAncestors(node) : [];
    pickerAncestorIndex = 0;
    updatePickerHighlight(node, announce);
  }

  function movePickerLevel(direction) {
    if (!pickerAncestors.length) return;
    pickerAncestorIndex = Math.max(0, Math.min(
      pickerAncestors.length - 1,
      pickerAncestorIndex + direction
    ));
    updatePickerHighlight(pickerAncestors[pickerAncestorIndex], true);
  }

  function startPicker(trigger) {
    if (pickerActive) return;
    lastTrigger = trigger;
    setPanel(false);
    pickerActive = true;
    document.documentElement.setAttribute('data-vd-picking', 'true');
    ensurePickerChrome();
    pickerCandidates = pageTargets();
    pickerCandidates.forEach(function (node) {
      node.setAttribute('data-vd-candidate', 'true');
      if (!node.hasAttribute('tabindex')) {
        node.setAttribute('tabindex', '0');
        node.setAttribute('data-vd-tab-added', 'true');
      }
    });
    var message = el('div', 'vd-picker-message');
    message.innerHTML = '' +
      '<span class="vd-picker-message__item">клик — выбрать элемент</span>' +
      '<span class="vd-picker-message__item">↑ родитель</span>' +
      '<span class="vd-picker-message__item">↓ глубже</span>' +
      '<span class="vd-picker-message__item">tab — следующий блок</span>' +
      '<span class="vd-picker-message__item">enter — выбрать</span>' +
      '<span class="vd-picker-message__item">esc — отмена</span>' +
      '<span class="vd-sr-only" data-vd-picker-live aria-live="polite"></span>';
    message.setAttribute('data-vibe-debug-ui', '');
    message.setAttribute('role', 'status');
    document.body.appendChild(message);
    if (pickerCandidates[0]) {
      pickerCandidates[0].focus();
      setPickerTarget(pickerCandidates[0], true);
    }
  }

  function stopPicker() {
    if (!pickerActive) return;
    pickerActive = false;
    document.documentElement.removeAttribute('data-vd-picking');
    pickerCandidates.forEach(function (node) {
      node.removeAttribute('data-vd-candidate');
      if (node.hasAttribute('data-vd-tab-added')) {
        node.removeAttribute('tabindex');
        node.removeAttribute('data-vd-tab-added');
      }
    });
    pickerCandidates = [];
    pickerHovered = null;
    pickerPointerTarget = null;
    pickerAncestors = [];
    pickerAncestorIndex = 0;
    pickerPointer = null;
    var message = document.querySelector('.vd-picker-message');
    if (message) message.remove();
    var highlight = document.getElementById('vd-picker-highlight');
    var label = document.getElementById('vd-picker-label');
    if (highlight) highlight.remove();
    if (label) label.remove();
  }

  function chooseCandidate(node, point) {
    var target = targetContext(node);
    var anchor = anchorContext(node, point || pickerPointer) || defaultAnchor(node);
    stopPicker();
    if (mode === 'vibe') openArtComposer(target, anchor);
    else openForm(target, anchor);
  }

  function formatDate(value) {
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return value || '';
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
    }).format(date);
  }

  function updateCount() {
    var source = mode === 'view' ? allComments : comments;
    var count = source.filter(function (item) {
      return item.status !== 'resolved' && item.status !== 'wont_fix';
    }).length;
    document.querySelectorAll('[data-vd-count]').forEach(function (node) {
      node.textContent = String(count);
      node.hidden = count === 0;
    });
    var toggle = document.getElementById('vd-list-toggle');
    if (toggle) {
      toggle.setAttribute('aria-label', count
        ? 'Открыть список комментариев, активных: ' + count
        : 'Открыть список комментариев, активных нет');
    }
  }

  function authorLabel(item) {
    return item.displayAuthor || item.author || 'Автор';
  }

  function commentRoute(comment) {
    return comment.route || (comment.page && comment.page.route) || '/index.html';
  }

  function commentHref(comment) {
    var targetRoute = commentRoute(comment);
    return targetRoute + (targetRoute.indexOf('?') === -1 ? '?' : '&') +
      'vibe-comment=' + encodeURIComponent(comment.id);
  }

  function clearFocusedComment() {
    if (focusedCommentTarget) {
      focusedCommentTarget.classList.remove('vd-comment-target--focused');
      focusedCommentTarget = null;
    }
    document.querySelectorAll('.vd-comment--focused').forEach(function (item) {
      item.classList.remove('vd-comment--focused');
    });
  }

  function revealLinkedComment() {
    if (linkedCommentHandled || mode !== 'view') return;
    var commentId = new URLSearchParams(location.search).get('vibe-comment');
    if (!commentId) return;
    var comment = allComments.find(function (item) { return item.id === commentId; });
    if (!comment) {
      linkedCommentHandled = true;
      setPanel(true);
      setMessage('Комментарий ' + commentId + ' не найден.', 'error');
      return;
    }
    linkedCommentHandled = true;
    setPanel(true);
    requestAnimationFrame(function () {
      var target = resolveTarget(comment.selector);
      var card = document.getElementById('vd-' + comment.id);
      if (target && target !== document.documentElement) {
        focusedCommentTarget = target;
        target.classList.add('vd-comment-target--focused');
        target.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'auto' });
      } else {
        window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
      }
      if (card) {
        card.classList.add('vd-comment--focused');
        card.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' });
      }
      setMessage(target || comment.selector === ':root'
        ? 'Показан комментарий ' + comment.id + '.'
        : 'Комментарий открыт, но сохранённый блок больше не найден.', target ? 'info' : 'error');
    });
  }

  function initials(value) {
    var parts = (value || '?').trim().split(/\s+/).filter(Boolean);
    return parts.slice(0, 2).map(function (part) { return part.charAt(0); }).join('').toUpperCase() || '?';
  }

  function showArtThread(comment, pin, force) {
    var thread = document.getElementById('vd-art-thread');
    if (!thread) return;
    if (!force && activeArtCommentId === comment.id && !thread.hidden) {
      closeArtThread();
      return;
    }
    closeArtThread();
    commentPlacementPending = false;
    activeArtCommentId = comment.id;
    pin.setAttribute('aria-expanded', 'true');
    thread.querySelector('[data-vd-thread-avatar]').textContent = initials(authorLabel(comment));
    thread.querySelector('[data-vd-thread-author]').textContent = authorLabel(comment);
    thread.querySelector('[data-vd-thread-date]').textContent = formatDate(comment.createdAt);
    thread.querySelector('[data-vd-thread-text]').textContent = comment.text;
    thread.querySelector('[data-vd-thread-target]').textContent = (comment.target && comment.target.label) || comment.selector;
    thread.querySelector('[data-vd-thread-status]').textContent = statusLabels[comment.status] || comment.status;
    var threadAttachments = thread.querySelector('[data-vd-thread-attachments]');
    threadAttachments.replaceChildren();
    var threadGallery = attachmentGallery(comment.attachments);
    if (threadGallery) threadAttachments.appendChild(threadGallery);
    threadAttachments.hidden = !threadGallery;
    thread.hidden = false;
    syncCommentPlacement();
    var rectangle = pin.getBoundingClientRect();
    positionFloating(thread, {
      left: rectangle.left + window.scrollX + rectangle.width / 2,
      top: rectangle.top + window.scrollY + rectangle.height / 2
    });
  }

  function renderPins() {
    pageTargets();
    document.querySelectorAll('.vd-pin').forEach(function (pin) { pin.remove(); });
    if (mode === 'view') {
      closeArtThread();
      return;
    }
    comments.filter(function (comment) {
      return comment.status !== 'resolved' && comment.selector && comment.selector !== ':root';
    }).forEach(function (comment, index) {
      var target = resolveTarget(comment.selector);
      if (!target) return;
      var position = anchorPosition(target, comment.anchor);
      var pin = el('button', 'vd-pin vd-pin--' + mode, mode === 'vibe' ? initials(authorLabel(comment)) : String(index + 1));
      pin.type = 'button';
      pin.setAttribute('data-vibe-debug-ui', '');
      pin.setAttribute('data-vd-comment-id', comment.id);
      pin.setAttribute('aria-label', 'Открыть комментарий ' + comment.id + ': ' + comment.text.slice(0, 80));
      pin.setAttribute('aria-expanded', String(activeArtCommentId === comment.id));
      pin.setAttribute('aria-controls', 'vd-art-thread');
      pin.style.top = Math.max(0, position.top - 14) + 'px';
      pin.style.left = Math.max(0, position.left - 14) + 'px';
      pin.addEventListener('click', function () {
        lastTrigger = pin;
        if (mode === 'vibe') showArtThread(comment, pin);
        else {
          setPanel(true);
          var item = document.getElementById('vd-' + comment.id);
          if (item) item.scrollIntoView({ block: 'nearest' });
        }
      });
      document.body.appendChild(pin);
    });
    if (activeArtCommentId) {
      var activePin = document.querySelector('[data-vd-comment-id="' + activeArtCommentId + '"]');
      var activeComment = comments.find(function (comment) { return comment.id === activeArtCommentId; });
      if (activePin && activeComment && mode === 'vibe') showArtThread(activeComment, activePin, true);
      else closeArtThread();
    }
  }

  function svgElement(tag) {
    return document.createElementNS('http://www.w3.org/2000/svg', tag);
  }

  function markById(markId) {
    return marks.find(function (mark) { return mark.id === markId; });
  }

  function visibleMarkColor(color) {
    var normalized = String(color || '').toLowerCase();
    return normalized === '#7c3aed' || normalized === '#5b21b6' || normalized === '#a99563' ? DEFAULT_DRAW_COLOR : color;
  }

  function pageDrawingRectangle() {
    var root = document.documentElement;
    var body = document.body;
    return {
      left: -window.scrollX,
      top: -window.scrollY,
      width: Math.max(root.clientWidth, body ? body.clientWidth : 0),
      height: Math.max(window.innerHeight, root.scrollHeight, body ? body.scrollHeight : 0)
    };
  }

  function markTarget(mark) {
    if (mark && mark.kind === 'stroke' && mark.selector === ':root') return document.documentElement;
    return mark ? resolveTarget(mark.selector) : null;
  }

  function markSurfaceRectangle(mark, target) {
    return mark && mark.kind === 'stroke' && mark.selector === ':root'
      ? pageDrawingRectangle()
      : target.getBoundingClientRect();
  }

  function markGeometryBounds(mark) {
    if (!mark || !mark.geometry) return null;
    if (mark.kind === 'rectangle' && mark.geometry.bounds) return mark.geometry.bounds;
    if (mark.kind !== 'stroke' || !Array.isArray(mark.geometry.points) || !mark.geometry.points.length) return null;
    var xs = mark.geometry.points.map(function (point) { return Number(point.x); });
    var ys = mark.geometry.points.map(function (point) { return Number(point.y); });
    var minX = Math.min.apply(Math, xs);
    var minY = Math.min.apply(Math, ys);
    var maxX = Math.max.apply(Math, xs);
    var maxY = Math.max.apply(Math, ys);
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  function setMarkShapeGeometry(mark, shape) {
    if (mark.kind === 'stroke') {
      shape.setAttribute('d', mark.geometry.points.map(function (point, index) {
        return (index ? 'L' : 'M') + point.x + ' ' + point.y;
      }).join(' '));
      return;
    }
    var bounds = mark.geometry.bounds;
    shape.setAttribute('x', bounds.x);
    shape.setAttribute('y', bounds.y);
    shape.setAttribute('width', bounds.width);
    shape.setAttribute('height', bounds.height);
  }

  function moveStrokeGeometry(mark, startGeometry, dx, dy) {
    var startMark = { kind: 'stroke', geometry: startGeometry };
    var bounds = markGeometryBounds(startMark);
    var safeX = clamp(dx, -bounds.x, 1 - bounds.x - bounds.width);
    var safeY = clamp(dy, -bounds.y, 1 - bounds.y - bounds.height);
    mark.geometry.points = startGeometry.points.map(function (point) {
      return {
        x: Number((point.x + safeX).toFixed(5)),
        y: Number((point.y + safeY).toFixed(5))
      };
    });
  }

  function clearMarkSelection() {
    selectedMarkId = '';
    document.querySelectorAll('.vd-mark-layer--selected').forEach(function (layer) {
      layer.classList.remove('vd-mark-layer--selected');
      layer.setAttribute('aria-pressed', 'false');
    });
    var removeButton = document.querySelector('[data-vd-delete-mark]');
    if (removeButton) removeButton.hidden = true;
  }

  function positionMarkDelete(mark, target, button) {
    if (!mark || !target || !button) return;
    var rectangle = markSurfaceRectangle(mark, target);
    var bounds = markGeometryBounds(mark);
    if (!bounds) return;
    button.style.left = Math.round(rectangle.left + window.scrollX + (bounds.x + bounds.width) * rectangle.width - 22) + 'px';
    button.style.top = Math.round(rectangle.top + window.scrollY + bounds.y * rectangle.height - 22) + 'px';
    button.hidden = mode !== 'vibe' || activeTool !== 'comment';
  }

  function selectMark(mark, layer, focus) {
    if (!mark) return;
    stopPicker();
    selectedMarkId = mark.id;
    document.querySelectorAll('.vd-mark-layer--selected').forEach(function (current) {
      current.classList.remove('vd-mark-layer--selected');
      current.setAttribute('aria-pressed', 'false');
    });
    layer.classList.add('vd-mark-layer--selected');
    layer.setAttribute('aria-pressed', 'true');
    var removeButton = document.querySelector('[data-vd-delete-mark]');
    positionMarkDelete(mark, markTarget(mark), removeButton);
    if (focus) layer.focus({ preventScroll: true });
  }

  function persistMarkGeometry(mark, message, undoGeometry) {
    return request('/marks/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: mark.id,
        geometry: mark.geometry,
        author: accountAuthor || displayAuthor() || 'anonymous'
      })
    }).then(function (payload) {
      marks = marks.map(function (item) { return item.id === payload.mark.id ? payload.mark : item; });
      if (undoGeometry) {
        rememberMarkAction({ kind: 'geometry', markId: payload.mark.id, geometry: cloneValue(undoGeometry) });
      }
      selectedMarkId = payload.mark.id;
      renderMarks();
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = message || 'пометка перемещена';
    }).catch(function (error) {
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = error.message || 'не удалось сохранить положение пометки';
      return loadMarks();
    });
  }

  function deleteSelectedMark() {
    if (!selectedMarkId) return;
    var markId = selectedMarkId;
    var deletedMark = markById(markId);
    if (!deletedMark) return;
    deletedMark = cloneValue(deletedMark);
    var removeButton = document.querySelector('[data-vd-delete-mark]');
    if (removeButton) removeButton.disabled = true;
    request('/marks/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: markId })
    }).then(function () {
      marks = marks.filter(function (mark) { return mark.id !== markId; });
      rememberMarkAction({ kind: 'delete', mark: deletedMark });
      clearMarkSelection();
      renderMarks();
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = deletedMark.kind === 'stroke' ? 'штрих удалён' : 'рамка удалена';
    }).catch(function (error) {
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = error.message || 'не удалось удалить рамку';
    }).finally(function () {
      if (removeButton) removeButton.disabled = false;
    });
  }

  function beginMarkDrag(event, mark, layer, shape, target) {
    if (mode !== 'vibe' || activeTool !== 'comment' || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    selectMark(mark, layer, true);
    var rectangle = markSurfaceRectangle(mark, target);
    draggingMark = {
      pointerId: event.pointerId,
      mark: mark,
      layer: layer,
      shape: shape,
      target: target,
      rectangle: rectangle,
      clientX: event.clientX,
      clientY: event.clientY,
      start: cloneValue(mark.geometry),
      moved: false
    };
    layer.classList.add('vd-mark-layer--dragging');
    if (layer.setPointerCapture) layer.setPointerCapture(event.pointerId);
  }

  function moveMarkDrag(event) {
    if (!draggingMark || event.pointerId !== draggingMark.pointerId) return false;
    event.preventDefault();
    var current = draggingMark;
    var dx = (event.clientX - current.clientX) / current.rectangle.width;
    var dy = (event.clientY - current.clientY) / current.rectangle.height;
    if (current.mark.kind === 'stroke') {
      moveStrokeGeometry(current.mark, current.start, dx, dy);
    } else {
      var bounds = current.mark.geometry.bounds;
      bounds.x = Number(clamp(current.start.bounds.x + dx, 0, 1 - bounds.width).toFixed(5));
      bounds.y = Number(clamp(current.start.bounds.y + dy, 0, 1 - bounds.height).toFixed(5));
    }
    current.moved = current.moved || Math.abs(event.clientX - current.clientX) > 1 || Math.abs(event.clientY - current.clientY) > 1;
    setMarkShapeGeometry(current.mark, current.shape);
    positionMarkDelete(current.mark, current.target, document.querySelector('[data-vd-delete-mark]'));
    return true;
  }

  function finishMarkDrag(event) {
    if (!draggingMark || event.pointerId !== draggingMark.pointerId) return false;
    var current = draggingMark;
    draggingMark = null;
    current.layer.classList.remove('vd-mark-layer--dragging');
    if (current.moved) {
      persistMarkGeometry(
        current.mark,
        current.mark.kind === 'stroke' ? 'штрих перемещён' : 'рамка перемещена',
        current.start
      );
    }
    return true;
  }

  function nudgeSelectedMark(event) {
    var mark = markById(selectedMarkId);
    if (!mark) return false;
    var target = markTarget(mark);
    if (!target) return false;
    var rectangle = markSurfaceRectangle(mark, target);
    var step = event.shiftKey ? 10 : 1;
    var dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
    var dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
    if (!dx && !dy) return false;
    var previousGeometry = cloneValue(mark.geometry);
    if (mark.kind === 'stroke') {
      moveStrokeGeometry(mark, previousGeometry, dx / rectangle.width, dy / rectangle.height);
    } else {
      var bounds = mark.geometry.bounds;
      bounds.x = Number(clamp(bounds.x + dx / rectangle.width, 0, 1 - bounds.width).toFixed(5));
      bounds.y = Number(clamp(bounds.y + dy / rectangle.height, 0, 1 - bounds.height).toFixed(5));
    }
    persistMarkGeometry(mark, mark.kind === 'stroke' ? 'штрих перемещён' : 'рамка перемещена', previousGeometry);
    return true;
  }

  function renderMarks() {
    pageTargets();
    document.querySelectorAll('.vd-mark-layer').forEach(function (layer) { layer.remove(); });
    if (mode !== 'vibe') {
      clearMarkSelection();
      return;
    }
    marks.forEach(function (mark) {
      var pageWide = mark.kind === 'stroke' && mark.selector === ':root';
      var target = pageWide ? document.documentElement : resolveTarget(mark.selector);
      if (!target || !mark.geometry || !mark.style) return;
      var rectangle = pageWide ? pageDrawingRectangle() : target.getBoundingClientRect();
      if (!rectangle.width || !rectangle.height) return;
      var layer = svgElement('svg');
      layer.classList.add('vd-mark-layer');
      layer.setAttribute('data-vibe-debug-ui', '');
      layer.setAttribute('data-vd-mark-id', mark.id);
      layer.setAttribute('viewBox', '0 0 1 1');
      layer.setAttribute('preserveAspectRatio', 'none');
      layer.style.left = Math.round(rectangle.left + window.scrollX) + 'px';
      layer.style.top = Math.round(rectangle.top + window.scrollY) + 'px';
      layer.style.width = rectangle.width + 'px';
      layer.style.height = rectangle.height + 'px';
      var shape;
      if (mark.kind === 'stroke' && Array.isArray(mark.geometry.points)) {
        layer.classList.add('vd-mark-layer--stroke');
        shape = svgElement('path');
        shape.setAttribute('fill', 'none');
        shape.setAttribute('stroke-linecap', 'round');
        shape.setAttribute('stroke-linejoin', 'round');
      } else if (mark.kind === 'rectangle' && mark.geometry.bounds) {
        layer.classList.add('vd-mark-layer--rectangle');
        shape = svgElement('rect');
        shape.setAttribute('fill', 'transparent');
      }
      if (!shape) return;
      layer.setAttribute('role', 'button');
      layer.setAttribute('tabindex', '0');
      layer.setAttribute('aria-label', (mark.kind === 'stroke' ? 'штрих' : 'рамка') + ': перетащите или используйте стрелки; Delete — удалить');
      layer.setAttribute('aria-pressed', String(mark.id === selectedMarkId));
      setMarkShapeGeometry(mark, shape);
      shape.classList.add('vd-mark-shape');
      shape.setAttribute('stroke', visibleMarkColor(mark.style.color));
      shape.setAttribute('stroke-width', mark.style.thickness);
      shape.setAttribute('vector-effect', 'non-scaling-stroke');
      layer.appendChild(shape);
      var hit = shape.cloneNode(false);
      hit.classList.remove('vd-mark-shape');
      hit.classList.add('vd-mark-hit');
      hit.setAttribute('fill', mark.kind === 'rectangle' ? 'rgba(0,0,0,0.001)' : 'none');
      hit.setAttribute('stroke', 'transparent');
      hit.setAttribute('stroke-width', String(Math.max(24, Number(mark.style.thickness) + 16)));
      hit.setAttribute('vector-effect', 'non-scaling-stroke');
      layer.appendChild(hit);
      layer.addEventListener('pointerdown', function (event) {
        beginMarkDrag(event, mark, layer, shape, target);
      });
      layer.addEventListener('click', function (event) {
        if (mode !== 'vibe' || activeTool !== 'comment') return;
        event.preventDefault();
        event.stopPropagation();
        selectMark(mark, layer, true);
      });
      layer.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        selectMark(mark, layer, true);
      });
      if (mark.id === selectedMarkId) {
        layer.classList.add('vd-mark-layer--selected');
        positionMarkDelete(mark, target, document.querySelector('[data-vd-delete-mark]'));
      }
      document.body.appendChild(layer);
    });
    if (selectedMarkId && !markById(selectedMarkId)) clearMarkSelection();
  }

  function updateDrawPreview() {
    var preview = document.querySelector('[data-vd-stroke-preview]');
    var thickness = document.getElementById('vd-thickness-value');
    if (!preview || !thickness) return;
    thickness.textContent = String(drawStyle.thickness) + ' px';
    preview.style.setProperty('--vd-draw-color', drawStyle.color);
    preview.style.setProperty('--vd-draw-width', drawStyle.thickness + 'px');
    preview.setAttribute('data-tool', activeTool);
    document.querySelectorAll('[data-vd-color]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.getAttribute('data-vd-color') === drawStyle.color));
    });
    var range = document.getElementById('vd-thickness');
    if (range) range.value = String(drawStyle.thickness);
  }

  function setActiveTool(tool, announce) {
    activeTool = tool === 'pencil' || tool === 'rectangle' ? tool : 'comment';
    if (activeTool !== 'comment') commentPlacementPending = false;
    else if (mode === 'vibe' && announce) commentPlacementPending = true;
    if (activeTool !== 'comment') stopPicker();
    if (activeTool !== 'comment') clearMarkSelection();
    document.documentElement.setAttribute('data-vd-tool', activeTool);
    document.querySelectorAll('[data-vd-tool-value]').forEach(function (button) {
      button.setAttribute('aria-pressed', String(button.getAttribute('data-vd-tool-value') === activeTool));
    });
    var settings = document.getElementById('vd-draw-settings');
    if (settings) settings.hidden = mode !== 'vibe' || activeTool === 'comment';
    if (settings && !settings.hidden) requestAnimationFrame(positionDrawSettings);
    updateDrawPreview();
    syncCommentPlacement();
    if (announce) {
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = activeTool === 'pencil' ? 'Карандаш включён' : activeTool === 'rectangle' ? 'Рамка включена' : 'Инструмент комментариев включён';
    }
  }

  function drawingPoint(event) {
    var rectangle = drawing.rectangle;
    return {
      x: clamp(event.clientX - rectangle.left, 0, rectangle.width),
      y: clamp(event.clientY - rectangle.top, 0, rectangle.height)
    };
  }

  function updateDrawingPreview() {
    if (!drawing) return;
    if (drawing.kind === 'stroke') {
      drawing.shape.setAttribute('d', drawing.points.map(function (point, index) {
        return (index ? 'L' : 'M') + point.x + ' ' + point.y;
      }).join(' '));
    } else {
      var start = drawing.points[0];
      var end = drawing.points[drawing.points.length - 1];
      drawing.shape.setAttribute('x', Math.min(start.x, end.x));
      drawing.shape.setAttribute('y', Math.min(start.y, end.y));
      drawing.shape.setAttribute('width', Math.abs(end.x - start.x));
      drawing.shape.setAttribute('height', Math.abs(end.y - start.y));
    }
  }

  function beginDrawing(event) {
    if (mode !== 'vibe' || (activeTool !== 'pencil' && activeTool !== 'rectangle') || event.button !== 0) return;
    var pointedTarget = elementAtPointer(event.target);
    if (typeof pointedTarget === 'undefined') return;
    var pageWide = activeTool === 'pencil';
    var target = pageWide ? document.documentElement : pointedTarget;
    if (!target) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    closeArtComposer();
    closeArtThread();
    var rectangle = pageWide ? pageDrawingRectangle() : target.getBoundingClientRect();
    if (!rectangle.width || !rectangle.height) return;
    var layer = svgElement('svg');
    layer.classList.add('vd-mark-layer', 'vd-mark-layer--draft');
    layer.setAttribute('data-vibe-debug-ui', '');
    layer.setAttribute('viewBox', '0 0 ' + rectangle.width + ' ' + rectangle.height);
    layer.style.left = Math.round(rectangle.left + window.scrollX) + 'px';
    layer.style.top = Math.round(rectangle.top + window.scrollY) + 'px';
    layer.style.width = rectangle.width + 'px';
    layer.style.height = rectangle.height + 'px';
    var shape = svgElement(activeTool === 'pencil' ? 'path' : 'rect');
    shape.setAttribute('fill', 'none');
    shape.setAttribute('stroke', drawStyle.color);
    shape.setAttribute('stroke-width', drawStyle.thickness);
    shape.setAttribute('stroke-linecap', 'round');
    shape.setAttribute('stroke-linejoin', 'round');
    shape.setAttribute('vector-effect', 'non-scaling-stroke');
    layer.appendChild(shape);
    document.body.appendChild(layer);
    drawing = {
      pointerId: event.pointerId,
      kind: activeTool === 'pencil' ? 'stroke' : 'rectangle',
      target: target,
      context: pageWide ? targetContext(null) : targetContext(target),
      rectangle: rectangle,
      layer: layer,
      shape: shape,
      points: []
    };
    drawing.points.push(drawingPoint(event));
    if (event.target.setPointerCapture) event.target.setPointerCapture(event.pointerId);
    updateDrawingPreview();
  }

  function moveDrawing(event) {
    if (!drawing || event.pointerId !== drawing.pointerId) return;
    event.preventDefault();
    var point = drawingPoint(event);
    var previous = drawing.points[drawing.points.length - 1];
    if (drawing.kind === 'stroke' && Math.hypot(point.x - previous.x, point.y - previous.y) < 1.5) return;
    if (drawing.kind === 'rectangle') drawing.points = [drawing.points[0], point];
    else drawing.points.push(point);
    updateDrawingPreview();
  }

  function markGeometry(current) {
    var width = current.rectangle.width;
    var height = current.rectangle.height;
    if (current.kind === 'stroke') {
      return {
        coordinateSpace: 'target-relative',
        points: current.points.map(function (point) {
          return { x: Number((point.x / width).toFixed(5)), y: Number((point.y / height).toFixed(5)) };
        })
      };
    }
    var start = current.points[0];
    var end = current.points[current.points.length - 1];
    return {
      coordinateSpace: 'target-relative',
      bounds: {
        x: Number((Math.min(start.x, end.x) / width).toFixed(5)),
        y: Number((Math.min(start.y, end.y) / height).toFixed(5)),
        width: Number((Math.abs(end.x - start.x) / width).toFixed(5)),
        height: Number((Math.abs(end.y - start.y) / height).toFixed(5))
      }
    };
  }

  function finishDrawing(event) {
    if (!drawing || event.pointerId !== drawing.pointerId) return;
    var current = drawing;
    drawing = null;
    current.layer.remove();
    var geometry = markGeometry(current);
    var valid = current.kind === 'stroke'
      ? geometry.points.length >= 2
      : geometry.bounds.width * current.rectangle.width >= 3 && geometry.bounds.height * current.rectangle.height >= 3;
    if (!valid) return;
    request('/marks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: current.kind,
        route: route,
        pageTitle: document.title,
        url: location.href,
        selector: current.context.selector,
        target: current.context,
        viewport: { width: window.innerWidth, height: window.innerHeight },
        author: accountAuthor || displayAuthor() || 'anonymous',
        displayAuthor: displayAuthor() || accountAuthor || 'anonymous',
        style: drawStyle,
        geometry: geometry
      })
    }).then(function (payload) {
      marks.push(payload.mark);
      rememberMarkAction({ kind: 'create', markId: payload.mark.id });
      renderMarks();
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = current.kind === 'stroke' ? 'Штрих сохранён' : 'Рамка сохранена';
    }).catch(function (error) {
      var live = document.querySelector('[data-vd-mode-live]');
      if (live) live.textContent = error.message || 'Не удалось сохранить пометку';
    });
  }

  function attachmentErrorNode(mode) {
    return document.getElementById(mode === 'vibe' ? 'vd-art-error' : 'vd-form-error');
  }

  function setAttachmentMessage(mode, message, error) {
    var status = document.querySelector('[data-vd-attachment-status="' + mode + '"]');
    if (status) status.textContent = message || '';
    var errorNode = attachmentErrorNode(mode);
    if (!errorNode) return;
    if (error) {
      errorNode.textContent = message;
      errorNode.hidden = false;
    } else {
      errorNode.hidden = true;
      if (!message) errorNode.textContent = '';
    }
  }

  function updateAttachmentBusy(mode, delta) {
    attachmentUploads[mode] = Math.max(0, attachmentUploads[mode] + delta);
    var busy = attachmentUploads[mode] > 0;
    var input = document.querySelector('[data-vd-attachment-input="' + mode + '"]');
    var form = document.querySelector(mode === 'vibe' ? '[data-vd-art-form]' : '[data-vd-form]');
    if (input) input.disabled = busy;
    if (form) {
      var submit = form.querySelector('[type="submit"]');
      if (submit) submit.disabled = busy;
    }
  }

  function imageDimensions(file) {
    return new Promise(function (resolve) {
      var image = new Image();
      var objectUrl = URL.createObjectURL(file);
      image.onload = function () {
        resolve({ width: image.naturalWidth || 0, height: image.naturalHeight || 0 });
        URL.revokeObjectURL(objectUrl);
      };
      image.onerror = function () {
        resolve({ width: 0, height: 0 });
        URL.revokeObjectURL(objectUrl);
      };
      image.src = objectUrl;
    });
  }

  function fileBase64(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        var result = String(reader.result || '');
        resolve(result.slice(result.indexOf(',') + 1));
      };
      reader.onerror = function () { reject(new Error('Не удалось прочитать изображение.')); };
      reader.readAsDataURL(file);
    });
  }

  function insertAttachmentToken(textarea, token) {
    var start = Number.isFinite(textarea.selectionStart) ? textarea.selectionStart : textarea.value.length;
    var end = Number.isFinite(textarea.selectionEnd) ? textarea.selectionEnd : start;
    var before = textarea.value.slice(0, start);
    var after = textarea.value.slice(end);
    var prefix = before && !/\s$/.test(before) ? ' ' : '';
    var suffix = after && !/^\s/.test(after) ? ' ' : '';
    var insertion = prefix + token + suffix;
    textarea.setRangeText(insertion, start, end, 'end');
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.focus();
  }

  function attachmentPreview(attachment, removable, mode) {
    var item = el('div', removable ? 'vd-attachment vd-attachment--draft' : 'vd-attachment');
    var link = el('a', 'vd-attachment__preview');
    link.href = attachment.url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.setAttribute('aria-label', 'Открыть ' + attachment.token);
    var image = document.createElement('img');
    image.src = attachment.url;
    image.alt = '';
    image.loading = 'lazy';
    link.appendChild(image);
    var token = el('span', 'vd-attachment__token', attachment.token);
    item.append(link, token);
    if (removable) {
      var remove = el('button', 'vd-attachment__remove', '×');
      remove.type = 'button';
      remove.setAttribute('data-vd-remove-attachment', attachment.id);
      remove.setAttribute('data-vd-remove-attachment-mode', mode);
      remove.setAttribute('aria-label', 'Убрать ' + attachment.token);
      item.appendChild(remove);
    }
    return item;
  }

  function renderAttachmentDrafts(mode) {
    var container = document.querySelector('[data-vd-attachments="' + mode + '"]');
    if (!container) return;
    container.replaceChildren();
    pendingAttachments[mode].forEach(function (attachment) {
      container.appendChild(attachmentPreview(attachment, true, mode));
    });
    container.hidden = pendingAttachments[mode].length === 0;
  }

  function attachmentGallery(attachments) {
    if (!Array.isArray(attachments) || !attachments.length) return null;
    var gallery = el('div', 'vd-attachment-gallery');
    attachments.forEach(function (attachment) {
      gallery.appendChild(attachmentPreview(attachment, false, ''));
    });
    return gallery;
  }

  function resetAttachments(mode, removeRemote) {
    attachmentGeneration[mode] += 1;
    var previous = pendingAttachments[mode].slice();
    pendingAttachments[mode] = [];
    renderAttachmentDrafts(mode);
    setAttachmentMessage(mode, '', false);
    if (removeRemote) {
      previous.forEach(function (attachment) {
        request('/attachments/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: attachment.id })
        }).catch(function () {});
      });
    }
  }

  function uploadAttachment(file, mode, textarea) {
    if (IMAGE_TYPES.indexOf(file.type) === -1) {
      setAttachmentMessage(mode, 'Поддерживаются PNG, JPEG и WebP.', true);
      return Promise.resolve();
    }
    if (!file.size || file.size > MAX_ATTACHMENT_BYTES) {
      setAttachmentMessage(mode, 'Изображение должно быть не больше 8 МБ.', true);
      return Promise.resolve();
    }
    if (pendingAttachments[mode].length + attachmentUploads[mode] >= MAX_ATTACHMENTS) {
      setAttachmentMessage(mode, 'К одному комментарию можно прикрепить не более 6 изображений.', true);
      return Promise.resolve();
    }
    var generation = attachmentGeneration[mode];
    updateAttachmentBusy(mode, 1);
    setAttachmentMessage(mode, 'Загружаю скриншот…', false);
    return Promise.all([fileBase64(file), imageDimensions(file)]).then(function (values) {
      return request('/attachments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name || 'скриншот',
          mimeType: file.type,
          size: file.size,
          width: values[1].width,
          height: values[1].height,
          data: values[0]
        })
      });
    }).then(function (payload) {
      if (generation !== attachmentGeneration[mode]) {
        return request('/attachments/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: payload.attachment.id })
        }).catch(function () {});
      }
      pendingAttachments[mode].push(payload.attachment);
      insertAttachmentToken(textarea, payload.attachment.token);
      renderAttachmentDrafts(mode);
      setAttachmentMessage(mode, payload.attachment.token + ' прикреплён', false);
    }).catch(function (error) {
      setAttachmentMessage(mode, error.message || 'Не удалось загрузить скриншот.', true);
    }).finally(function () {
      updateAttachmentBusy(mode, -1);
    });
  }

  function attachFiles(files, mode, textarea) {
    Array.from(files).reduce(function (chain, file) {
      return chain.then(function () { return uploadAttachment(file, mode, textarea); });
    }, Promise.resolve());
  }

  function handleAttachmentInput(event) {
    var input = event.currentTarget;
    var mode = input.getAttribute('data-vd-attachment-input');
    var textarea = document.getElementById(mode === 'vibe' ? 'vd-art-comment' : 'vd-comment');
    attachFiles(input.files || [], mode, textarea);
    input.value = '';
  }

  function handleAttachmentPaste(event) {
    var files = Array.from(event.clipboardData && event.clipboardData.items || [])
      .filter(function (item) { return item.kind === 'file' && IMAGE_TYPES.indexOf(item.type) !== -1; })
      .map(function (item) { return item.getAsFile(); })
      .filter(Boolean);
    if (!files.length) return;
    event.preventDefault();
    var mode = event.currentTarget.id === 'vd-art-comment' ? 'vibe' : 'dev';
    attachFiles(files, mode, event.currentTarget);
  }

  function removePendingAttachment(event) {
    var button = event.target.closest('[data-vd-remove-attachment]');
    if (!button) return;
    var mode = button.getAttribute('data-vd-remove-attachment-mode');
    var attachmentId = button.getAttribute('data-vd-remove-attachment');
    var attachment = pendingAttachments[mode].find(function (item) { return item.id === attachmentId; });
    button.disabled = true;
    request('/attachments/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: attachmentId })
    }).then(function () {
      pendingAttachments[mode] = pendingAttachments[mode].filter(function (item) {
        return item.id !== attachmentId;
      });
      if (attachment) {
        var textarea = document.getElementById(mode === 'vibe' ? 'vd-art-comment' : 'vd-comment');
        textarea.value = textarea.value.replace(attachment.token, '').replace(/ {2,}/g, ' ').trim();
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
      }
      renderAttachmentDrafts(mode);
      setAttachmentMessage(mode, 'Скриншот убран', false);
    }).catch(function (error) {
      button.disabled = false;
      setAttachmentMessage(mode, error.message || 'Не удалось убрать скриншот.', true);
    });
  }

  function renderList() {
    var list = document.getElementById('vd-list');
    var source = mode === 'view' ? allComments : comments;
    list.replaceChildren();
    if (!source.length) {
      list.appendChild(el('p', 'vd-empty', mode === 'view'
        ? 'На сайте комментариев пока нет.'
        : 'На этой странице комментариев пока нет.'));
      updateCount();
      renderPins();
      return;
    }
    source.forEach(function (comment) {
      var item = el('article', 'vd-comment');
      item.id = 'vd-' + comment.id;
      if (mode !== 'view') {
        var deleteButton = el('button', 'vd-comment__delete', '×');
        deleteButton.type = 'button';
        deleteButton.setAttribute('data-vd-delete-comment', comment.id);
        deleteButton.setAttribute('aria-label', 'Удалить комментарий ' + comment.id);
        item.appendChild(deleteButton);
      }
      var meta = el('p', 'vd-comment__meta');
      meta.textContent = authorLabel(comment) + ' · ' + formatDate(comment.createdAt);
      var text = el('p', 'vd-comment__text', comment.text);
      var target = el('p', 'vd-comment__target');
      var context = comment.target || {};
      target.textContent = 'Блок: ' + (context.label || context.heading || comment.selector || 'вся страница');
      if (mode === 'view') {
        var page = el('p', 'vd-comment__route');
        page.textContent = (comment.page && comment.page.title ? comment.page.title + ' · ' : '') + commentRoute(comment);
        item.append(meta, page, text, target);
      } else {
        item.append(meta, text, target);
      }
      var gallery = attachmentGallery(comment.attachments);
      var foot = el('div', 'vd-comment__foot');
      foot.appendChild(el('span', 'vd-comment__id', comment.id));
      if (mode === 'view') {
        foot.appendChild(el('span', 'vd-comment__state', statusLabels[comment.status] || comment.status));
        var jump = el('a', 'vd-comment__jump', 'Перейти к месту');
        jump.href = commentHref(comment);
        jump.setAttribute('aria-label', 'Перейти к комментарию ' + comment.id + ' на странице ' + commentRoute(comment));
        foot.appendChild(jump);
      } else {
        var label = el('label', 'vd-comment__status');
        label.appendChild(el('span', 'vd-sr-only', 'Статус ' + comment.id));
        var status = el('select', 'vd-status-select');
        status.setAttribute('data-vd-status-id', comment.id);
        Object.keys(statusLabels).forEach(function (key) {
          var option = document.createElement('option');
          option.value = key;
          option.textContent = statusLabels[key];
          option.selected = key === comment.status;
          status.appendChild(option);
        });
        label.appendChild(status);
        foot.appendChild(label);
      }
      if (gallery) item.appendChild(gallery);
      item.appendChild(foot);
      list.appendChild(item);
    });
    updateCount();
    renderPins();
  }

  function loadComments() {
    if (mode !== 'view') setMessage('Загружаю комментарии…');
    return request('/comments?route=' + encodeURIComponent(route)).then(function (payload) {
      comments = Array.isArray(payload.comments) ? payload.comments : [];
      renderList();
      if (mode !== 'view') setMessage('Комментарии сохраняются для всех участников демо.');
    }).catch(function () {
      comments = [];
      renderList();
      if (mode !== 'view') setMessage('Не удалось загрузить комментарии. Обновите страницу.', 'error');
    });
  }

  function loadAllComments() {
    if (mode === 'view') setMessage('Загружаю комментарии со всего сайта…');
    return request('/comments').then(function (payload) {
      allComments = Array.isArray(payload.comments) ? payload.comments : [];
      if (mode === 'view') {
        renderList();
        setMessage('Все комментарии сайта. Нажмите «Перейти к месту», чтобы открыть сохранённый блок.');
        revealLinkedComment();
      }
    }).catch(function () {
      allComments = [];
      if (mode === 'view') {
        renderList();
        setMessage('Не удалось загрузить комментарии сайта. Обновите страницу.', 'error');
      }
    });
  }

  function loadMarks() {
    return request('/marks?route=' + encodeURIComponent(route)).then(function (payload) {
      marks = Array.isArray(payload.marks) ? payload.marks : [];
      renderMarks();
    }).catch(function () {
      marks = [];
      renderMarks();
    });
  }

  function loadSession() {
    return request('/session').then(function (payload) {
      accountAuthor = payload.author || '';
      var saved = '';
      try { saved = localStorage.getItem('vibe-debug-display-author') || ''; } catch {}
      setAuthorValues(saved || accountAuthor, false);
    }).catch(function () {
      var saved = '';
      try { saved = localStorage.getItem('vibe-debug-display-author') || ''; } catch {}
      setAuthorValues(saved, false);
    });
  }

  function commentPayload(target, text, visibleAuthor, commentMode) {
    return {
      route: route,
      pageTitle: document.title,
      url: location.href,
      selector: target.selector,
      target: target,
      anchor: selectedAnchor,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      author: accountAuthor || visibleAuthor,
      displayAuthor: visibleAuthor,
      mode: commentMode,
      text: text,
      attachments: pendingAttachments[commentMode].slice()
    };
  }

  function submitComment(event) {
    event.preventDefault();
    var form = event.currentTarget;
    var submit = form.querySelector('[type="submit"]');
    var author = document.getElementById('vd-author').value.trim();
    var text = document.getElementById('vd-comment').value.trim();
    var option = document.getElementById('vd-target').selectedOptions[0];
    var target = option ? JSON.parse(option.dataset.target) : targetContext(null);
    if (!author || !text || attachmentUploads.dev) return;
    rememberDisplayAuthor(author);
    submit.disabled = true;
    submit.textContent = 'Сохраняю…';
    request('/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(commentPayload(target, text, author, 'dev'))
    }).then(function (payload) {
      comments.unshift(payload.comment);
      allComments.unshift(payload.comment);
      renderList();
      form.reset();
      resetAttachments('dev', false);
      setAuthorValues(author, false);
      closeForm(false);
      setPanel(true);
      setMessage('Комментарий сохранён: ' + payload.comment.id + '.');
    }).catch(function (error) {
      var errorNode = document.getElementById('vd-form-error');
      errorNode.textContent = error.message || 'Не удалось сохранить. Проверьте соединение и повторите.';
      errorNode.hidden = false;
    }).finally(function () {
      submit.disabled = false;
      submit.textContent = 'Сохранить комментарий';
    });
  }

  function submitArtComment(event) {
    event.preventDefault();
    var form = event.currentTarget;
    var submit = form.querySelector('[type="submit"]');
    var author = document.getElementById('vd-art-author').value.trim();
    var text = document.getElementById('vd-art-comment').value.trim();
    if (!author || !text || !selectedTarget || attachmentUploads.vibe) return;
    rememberDisplayAuthor(author);
    submit.disabled = true;
    submit.textContent = 'Сохраняю…';
    request('/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(commentPayload(selectedTarget, text, author, 'vibe'))
    }).then(function (payload) {
      comments.unshift(payload.comment);
      allComments.unshift(payload.comment);
      activeArtCommentId = payload.comment.id;
      form.reset();
      resetAttachments('vibe', false);
      setAuthorValues(author, false);
      closeArtComposer(false);
      renderList();
      var pin = document.querySelector('[data-vd-comment-id="' + payload.comment.id + '"]');
      if (pin) showArtThread(payload.comment, pin, true);
    }).catch(function (error) {
      var errorNode = document.getElementById('vd-art-error');
      errorNode.textContent = error.message || 'Не удалось сохранить комментарий.';
      errorNode.hidden = false;
    }).finally(function () {
      submit.disabled = false;
      submit.textContent = 'Отправить';
    });
  }

  function changeStatus(event) {
    var select = event.target.closest('[data-vd-status-id]');
    if (!select) return;
    select.disabled = true;
    request('/comments/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: select.getAttribute('data-vd-status-id'), status: select.value })
    }).then(function (payload) {
      comments = comments.map(function (item) {
        return item.id === payload.comment.id ? payload.comment : item;
      });
      allComments = allComments.map(function (item) {
        return item.id === payload.comment.id ? payload.comment : item;
      });
      renderList();
      setMessage('Статус ' + payload.comment.id + ' обновлён.');
    }).catch(function () {
      setMessage('Не удалось обновить статус. Повторите попытку.', 'error');
      loadComments();
    }).finally(function () {
      select.disabled = false;
    });
  }

  function deleteComment(event) {
    var button = event.target.closest('[data-vd-delete-comment]');
    if (!button) return;
    var commentId = button.getAttribute('data-vd-delete-comment');
    button.disabled = true;
    request('/comments/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: commentId })
    }).then(function () {
      comments = comments.filter(function (item) { return item.id !== commentId; });
      allComments = allComments.filter(function (item) { return item.id !== commentId; });
      if (activeArtCommentId === commentId) closeArtThread();
      renderList();
      setMessage('Комментарий ' + commentId + ' удалён.');
    }).catch(function () {
      button.disabled = false;
      setMessage('Не удалось удалить комментарий. Повторите попытку.', 'error');
    });
  }

  function icon(name) {
    var paths = {
      view: '<path d="M2.8 12s3.4-5.5 9.2-5.5 9.2 5.5 9.2 5.5-3.4 5.5-9.2 5.5S2.8 12 2.8 12Z"/><circle cx="12" cy="12" r="2.5"/>',
      dev: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="m7 10 2 2-2 2M12 15h5"/>',
      vibe: '<path d="m8.5 18.5 8.9-8.9a1.5 1.5 0 0 0 0-2.1l-.9-.9a1.5 1.5 0 0 0-2.1 0l-8.9 8.9v3h3Z"/><path d="m12.8 8.2 3 3M5.7 3.2l.7 1.7 1.7.7-1.7.7L5.7 8l-.7-1.7-1.7-.7L5 4.9l.7-1.7Z"/><path d="M3.5 11.1c-.8 4.8 2.4 9.2 7.2 10.1M15.4 20.8c4.6-1.3 7.2-6.1 5.9-10.7"/>',
      comment: '<path d="M5 5h14v11H9l-4 3V5Z"/>',
      image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m5.5 17 4.2-4.2 2.8 2.7 2.2-2.2 3.8 3.7"/>',
      pencil: '<path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20ZM13.8 7.7l3 3"/>',
      rectangle: '<rect x="4" y="5" width="16" height="14" rx="1"/>',
      list: '<path d="M8 6h12M8 12h12M8 18h12"/><circle cx="4" cy="6" r=".7" fill="currentColor"/><circle cx="4" cy="12" r=".7" fill="currentColor"/><circle cx="4" cy="18" r=".7" fill="currentColor"/>'
    };
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + paths[name] + '</svg>';
  }

  function mount() {
    addStyle();
    var root = el('div');
    root.setAttribute('data-vibe-debug-ui', '');
    root.innerHTML = '' +
      '<div class="vd-toolbar" role="toolbar" aria-label="Режим и инструменты ревью">' +
        '<div class="vd-toolbar__grip" aria-hidden="true"><span></span></div>' +
        '<div class="vd-mode-switch" role="group" aria-label="Режим ревью">' +
          '<button class="vd-mode-button" type="button" data-vd-mode-value="view" aria-pressed="false">' + icon('view') + '<span>view</span></button>' +
          '<button class="vd-mode-button" type="button" data-vd-mode-value="dev" aria-pressed="false">' + icon('dev') + '<span>dev</span></button>' +
          '<button class="vd-mode-button" type="button" data-vd-mode-value="vibe" aria-pressed="false">' + icon('vibe') + '<span>vibe</span></button>' +
        '</div>' +
        '<span class="vd-toolbar__separator" aria-hidden="true"></span>' +
        '<button class="vd-tool-button" type="button" data-vd-tool-value="comment" aria-pressed="true" aria-label="Комментарий по объекту">' + icon('comment') + '</button>' +
        '<button class="vd-tool-button vd-art-only" type="button" data-vd-tool-value="pencil" aria-pressed="false" aria-label="Карандаш">' + icon('pencil') + '</button>' +
        '<button class="vd-tool-button vd-art-only" type="button" data-vd-tool-value="rectangle" aria-pressed="false" aria-label="Рамка">' + icon('rectangle') + '</button>' +
        '<button class="vd-tool-button" id="vd-list-toggle" type="button" aria-expanded="false" aria-controls="vd-panel" aria-label="Открыть список комментариев, активных нет">' + icon('list') + '<span class="vd-tool-count" data-vd-count hidden>0</span></button>' +
        '<span class="vd-sr-only" data-vd-mode-live role="status" aria-live="polite"></span>' +
      '</div>' +
      '<section class="vd-draw-settings" id="vd-draw-settings" aria-label="Настройки инструмента" hidden>' +
        '<div class="vd-draw-settings__row"><span>цвет</span><div class="vd-colors">' +
          '<button type="button" data-vd-color="#a96f7b" style="--vd-swatch:#a96f7b" aria-label="приглушённый розовый" aria-pressed="false"></button>' +
          '<button type="button" data-vd-color="#718e99" style="--vd-swatch:#718e99" aria-label="серо-голубой" aria-pressed="false"></button>' +
          '<button type="button" data-vd-color="#a46f61" style="--vd-swatch:#a46f61" aria-label="терракотовый" aria-pressed="false"></button>' +
          '<button type="button" data-vd-color="#405762" style="--vd-swatch:#405762" aria-label="графитово-голубой" aria-pressed="false"></button>' +
          '<label class="vd-color-custom" aria-label="другой цвет"><input id="vd-color" type="color" value="#a96f7b"><span aria-hidden="true">+</span></label>' +
        '</div></div>' +
        '<label class="vd-draw-settings__range" for="vd-thickness"><span>толщина</span><output id="vd-thickness-value" for="vd-thickness">4 px</output><input id="vd-thickness" type="range" min="1" max="24" step="1" value="4"></label>' +
        '<div class="vd-stroke-preview" data-vd-stroke-preview data-tool="pencil" aria-label="Предпросмотр реальной толщины 1 к 1"><span></span></div>' +
      '</section>' +
      '<button class="vd-mark-delete" type="button" data-vd-delete-mark aria-label="удалить выбранную пометку" hidden>×</button>' +
      '<aside class="vd-panel" id="vd-panel" aria-labelledby="vd-panel-title" hidden>' +
        '<div class="vd-panel__head"><h2 id="vd-panel-title" tabindex="-1">Комментарии к странице</h2><button class="vd-icon-button" type="button" data-vd-close-panel aria-label="Закрыть панель">×</button></div>' +
        '<div class="vd-panel__actions" data-vd-panel-actions><button class="vd-button vd-button--primary" type="button" data-vd-page>К странице</button><button class="vd-button" type="button" data-vd-pick>Выбрать блок</button></div>' +
        '<p class="vd-panel__status" data-vd-message role="status" aria-live="polite">Загружаю комментарии…</p>' +
        '<div class="vd-list" id="vd-list"></div>' +
      '</aside>' +
      '<dialog class="vd-dialog" id="vd-dialog" aria-labelledby="vd-dialog-title">' +
        '<form method="dialog" data-vd-form>' +
          '<div class="vd-dialog__head"><h2 id="vd-dialog-title">Новый комментарий</h2><button class="vd-icon-button" type="button" data-vd-close-dialog aria-label="Закрыть форму">×</button></div>' +
          '<div class="vd-dialog__body">' +
            '<label class="vd-field"><span>Имя в комментариях</span><input id="vd-author" data-vd-author name="author" maxlength="80" autocomplete="name" required><small>Можно изменить — имя сохранится только в этом браузере.</small></label>' +
            '<label class="vd-field"><span>Страница или блок</span><select id="vd-target" name="target"></select></label>' +
            '<label class="vd-field"><span>Что нужно изменить</span><textarea id="vd-comment" name="comment" maxlength="4000" placeholder="Например: сократить текст и оставить один основной призыв" required></textarea></label>' +
            '<div class="vd-attachment-tools"><label class="vd-attachment-button">' + icon('image') + '<span>скриншот</span><input class="vd-sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple data-vd-attachment-input="dev"></label><small>или вставьте <span data-vd-paste-shortcut></span></small><span class="vd-attachment-status" data-vd-attachment-status="dev" role="status" aria-live="polite"></span></div>' +
            '<div class="vd-attachment-drafts" data-vd-attachments="dev" hidden></div>' +
            '<p class="vd-panel__status" id="vd-form-error" role="alert" hidden></p>' +
          '</div>' +
          '<div class="vd-dialog__actions"><button class="vd-button" type="button" data-vd-close-dialog>Отмена</button><button class="vd-button vd-button--primary" type="submit">Сохранить комментарий</button></div>' +
        '</form>' +
      '</dialog>' +
      '<section class="vd-art-composer" id="vd-art-composer" role="dialog" aria-labelledby="vd-art-title" hidden>' +
        '<form data-vd-art-form>' +
          '<div class="vd-art-surface__head"><div><strong id="vd-art-title">Новый комментарий</strong><span data-vd-art-target></span></div><button class="vd-art-close" type="button" data-vd-close-art aria-label="Закрыть">×</button></div>' +
          '<label class="vd-art-field"><span>Имя</span><input id="vd-art-author" data-vd-author maxlength="80" autocomplete="name" required></label>' +
          '<label class="vd-art-field"><span class="vd-sr-only">Комментарий</span><textarea id="vd-art-comment" maxlength="4000" placeholder="Напишите комментарий…" required></textarea></label>' +
          '<div class="vd-attachment-tools"><label class="vd-attachment-button">' + icon('image') + '<span>скриншот</span><input class="vd-sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple data-vd-attachment-input="vibe"></label><small>или вставьте <span data-vd-paste-shortcut></span></small><span class="vd-attachment-status" data-vd-attachment-status="vibe" role="status" aria-live="polite"></span></div>' +
          '<div class="vd-attachment-drafts" data-vd-attachments="vibe" hidden></div>' +
          '<p class="vd-art-error" id="vd-art-error" role="alert" hidden></p>' +
          '<div class="vd-art-actions"><button type="button" data-vd-close-art>Отмена</button><button type="submit">Отправить</button></div>' +
        '</form>' +
      '</section>' +
      '<article class="vd-art-thread" id="vd-art-thread" aria-live="polite" hidden>' +
        '<div class="vd-art-surface__head"><div class="vd-art-thread__author"><span class="vd-art-avatar" data-vd-thread-avatar></span><span><strong data-vd-thread-author></strong><small data-vd-thread-date></small></span></div><button class="vd-art-close" type="button" data-vd-close-thread aria-label="Свернуть комментарий">×</button></div>' +
        '<p class="vd-art-thread__text" data-vd-thread-text></p>' +
        '<div data-vd-thread-attachments hidden></div>' +
        '<div class="vd-art-thread__foot"><span data-vd-thread-target></span><span data-vd-thread-status></span></div>' +
      '</article>';
    document.body.appendChild(root);
    root.querySelectorAll('[data-vd-paste-shortcut]').forEach(function (node) {
      node.textContent = pasteShortcutLabel(navigator.userAgent);
    });

    root.querySelector('.vd-toolbar').addEventListener('pointerdown', beginToolbarDrag);
    root.querySelector('.vd-panel__head').addEventListener('pointerdown', beginPanelDrag);

    var toggle = document.getElementById('vd-list-toggle');
    toggle.addEventListener('click', function () {
      lastTrigger = toggle;
      setPanel(document.getElementById('vd-panel').hidden);
    });
    root.querySelectorAll('[data-vd-mode-value]').forEach(function (button) {
      button.addEventListener('click', function (event) {
        lastTrigger = event.currentTarget;
        setMode(event.currentTarget.getAttribute('data-vd-mode-value'), true);
        setActiveTool('comment', false);
      });
      button.addEventListener('keydown', function (event) {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
        event.preventDefault();
        var modeButtons = Array.from(root.querySelectorAll('[data-vd-mode-value]'));
        var currentIndex = modeButtons.indexOf(event.currentTarget);
        var direction = event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 1;
        var nextButton = modeButtons[(currentIndex + direction + modeButtons.length) % modeButtons.length];
        var next = nextButton.getAttribute('data-vd-mode-value');
        setMode(next, true);
        setActiveTool('comment', false);
        nextButton.focus();
      });
    });
    root.querySelectorAll('[data-vd-tool-value]').forEach(function (button) {
      button.addEventListener('click', function (event) {
        var tool = event.currentTarget.getAttribute('data-vd-tool-value');
        if (tool === 'comment') {
          setActiveTool('comment', true);
          stopPicker();
        } else {
          setActiveTool(tool, true);
        }
      });
    });
    root.querySelector('[data-vd-close-panel]').addEventListener('click', function (event) {
      lastTrigger = event.currentTarget;
      setPanel(false);
    });
    root.querySelector('[data-vd-page]').addEventListener('click', function (event) {
      lastTrigger = event.currentTarget;
      if (mode === 'vibe') openArtComposer(targetContext(null), null);
      else openForm(targetContext(null));
    });
    root.querySelector('[data-vd-pick]').addEventListener('click', function (event) {
      if (mode === 'vibe') {
        setPanel(false);
        setActiveTool('comment', true);
        stopPicker();
      } else {
        startPicker(event.currentTarget);
      }
    });
    root.querySelectorAll('[data-vd-close-dialog]').forEach(function (button) {
      button.addEventListener('click', closeForm);
    });
    root.querySelectorAll('[data-vd-close-art]').forEach(function (button) {
      button.addEventListener('click', closeArtComposer);
    });
    root.querySelector('[data-vd-close-thread]').addEventListener('click', closeArtThread);
    root.querySelector('[data-vd-delete-mark]').addEventListener('click', deleteSelectedMark);
    root.querySelector('[data-vd-form]').addEventListener('submit', submitComment);
    root.querySelector('[data-vd-art-form]').addEventListener('submit', submitArtComment);
    document.getElementById('vd-list').addEventListener('change', changeStatus);
    document.getElementById('vd-list').addEventListener('click', deleteComment);
    root.addEventListener('click', removePendingAttachment);
    root.querySelectorAll('[data-vd-attachment-input]').forEach(function (input) {
      input.addEventListener('change', handleAttachmentInput);
    });
    document.getElementById('vd-comment').addEventListener('paste', handleAttachmentPaste);
    document.getElementById('vd-art-comment').addEventListener('paste', handleAttachmentPaste);
    document.getElementById('vd-target').addEventListener('change', function (event) {
      selectedTarget = JSON.parse(event.target.selectedOptions[0].dataset.target);
      selectedAnchor = null;
    });
    root.querySelectorAll('[data-vd-author]').forEach(function (input) {
      input.addEventListener('input', function (event) {
        rememberDisplayAuthor(event.currentTarget.value);
      });
    });
    root.querySelectorAll('[data-vd-color]').forEach(function (button) {
      button.addEventListener('click', function (event) {
        drawStyle.color = event.currentTarget.getAttribute('data-vd-color');
        document.getElementById('vd-color').value = drawStyle.color;
        rememberDrawStyle();
        updateDrawPreview();
      });
    });
    document.getElementById('vd-color').addEventListener('input', function (event) {
      drawStyle.color = event.currentTarget.value;
      rememberDrawStyle();
      updateDrawPreview();
    });
    document.getElementById('vd-thickness').addEventListener('input', function (event) {
      drawStyle.thickness = Number(event.currentTarget.value);
      rememberDrawStyle();
      updateDrawPreview();
    });
    document.getElementById('vd-color').value = drawStyle.color;
    setMode(mode, false);
    setActiveTool('comment', false);
    requestAnimationFrame(function () { placeToolbar(readToolbarPosition()); });
    Promise.all([loadSession(), loadComments(), loadMarks()]);
  }

  function chooseFromPickerEvent(event) {
    if (!pickerActive) return;
    var exact = elementAtPointer(event.target);
    if (typeof exact === 'undefined' || !exact) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    chooseCandidate(exact === pickerPointerTarget && pickerHovered ? pickerHovered : exact, event);
  }

  function placeVibeComment(event) {
    if (mode !== 'vibe' || activeTool !== 'comment' || pickerActive ||
      document.documentElement.getAttribute('data-vd-comment-placement') !== 'true') return;
    var exact = elementAtPointer(event.target);
    if (typeof exact === 'undefined') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    chooseCandidate(exact, event);
  }

  document.addEventListener('click', chooseFromPickerEvent, true);
  document.addEventListener('click', placeVibeComment, true);

  document.addEventListener('pointermove', function (event) {
    if (moveToolbarDrag(event)) return;
    if (movePanelDrag(event)) return;
    if (moveMarkDrag(event)) return;
    if (drawing) {
      moveDrawing(event);
      return;
    }
    if (!pickerActive) return;
    pickerPointer = { clientX: event.clientX, clientY: event.clientY };
    var exact = elementAtPointer(event.target);
    if (typeof exact === 'undefined') return;
    if (exact !== pickerPointerTarget) setPickerTarget(exact, false);
  }, true);

  document.addEventListener('pointerdown', function (event) {
    if (pickerActive) {
      chooseFromPickerEvent(event);
      return;
    }
    beginDrawing(event);
  }, true);
  document.addEventListener('pointerup', function (event) {
    if (finishToolbarDrag(event)) return;
    if (finishPanelDrag(event)) return;
    if (!finishMarkDrag(event)) finishDrawing(event);
  }, true);
  document.addEventListener('pointercancel', function (event) {
    if (finishToolbarDrag(event)) return;
    if (finishPanelDrag(event)) return;
    if (!finishMarkDrag(event)) finishDrawing(event);
  }, true);

  document.addEventListener('focusin', function (event) {
    if (!pickerActive) return;
    var candidate = event.target.closest('[data-vd-candidate="true"]');
    if (candidate) setPickerTarget(candidate, true);
  }, true);

  document.addEventListener('keydown', function (event) {
    var editable = event.target.closest && event.target.closest('input, textarea, select, [contenteditable="true"]');
    var undoShortcut = (event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey &&
      (String(event.key).toLowerCase() === 'z' || event.code === 'KeyZ');
    if (undoShortcut && !editable && mode === 'vibe') {
      event.preventDefault();
      event.stopImmediatePropagation();
      undoLastMarkAction();
      return;
    }
    if (!pickerActive) {
      if (!editable && selectedMarkId && mode === 'vibe' && activeTool === 'comment') {
        if (event.key === 'Delete' || event.key === 'Backspace') {
          event.preventDefault();
          deleteSelectedMark();
          return;
        }
        if (nudgeSelectedMark(event)) {
          event.preventDefault();
          return;
        }
      }
      if (event.key === 'Escape') {
        if (drawing) {
          drawing.layer.remove();
          drawing = null;
        }
        closeArtComposer();
        closeArtThread();
        clearMarkSelection();
        if (activeTool !== 'comment') setActiveTool('comment', true);
      }
      return;
    }
    if (event.key === 'Escape') {
      stopPicker();
      setPanel(true);
      return;
    }
    if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      event.preventDefault();
      movePickerLevel(1);
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault();
      movePickerLevel(-1);
      return;
    }
    if (event.key === 'Tab' && pickerCandidates.length) {
      event.preventDefault();
      var current = event.target.closest('[data-vd-candidate="true"]');
      var currentIndex = pickerCandidates.indexOf(current);
      var direction = event.shiftKey ? -1 : 1;
      var nextIndex = (currentIndex + direction + pickerCandidates.length) % pickerCandidates.length;
      pickerCandidates[nextIndex].focus();
      setPickerTarget(pickerCandidates[nextIndex], true);
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      var candidate = pickerHovered || event.target.closest('[data-vd-candidate="true"]');
      if (!candidate) return;
      event.preventDefault();
      chooseCandidate(candidate);
    }
  }, true);

  var redrawTimer = null;
  function schedulePins() {
    if (redrawTimer) cancelAnimationFrame(redrawTimer);
    redrawTimer = requestAnimationFrame(function () {
      renderPins();
      renderMarks();
    });
  }
  window.addEventListener('scroll', function () {
    if (pickerActive && pickerHovered) updatePickerHighlight(pickerHovered);
  }, { passive: true });
  window.addEventListener('resize', function () {
    schedulePins();
    var toolbar = document.querySelector('.vd-toolbar');
    if (!toolbar) return;
    var saved = readToolbarPosition();
    if (saved) placeToolbar(saved);
    else positionDrawSettings();
    var panel = document.getElementById('vd-panel');
    if (panel && !panel.hidden) {
      var savedPanel = readPanelPosition();
      if (savedPanel) placePanel(savedPanel);
    }
  });
  window.addEventListener('load', schedulePins);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
