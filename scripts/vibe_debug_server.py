#!/usr/bin/env python3
"""Persistent review API and local static server for current wireframes."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(os.environ.get("VIBE_DEBUG_ROOT", REPO_ROOT / "preview"))
DATA_PATH = Path(
    os.environ.get("VIBE_DEBUG_DATA", REPO_ROOT / ".vibe-debug" / "comments.json")
)
MARKS_PATH = Path(
    os.environ.get("VIBE_DEBUG_MARKS", DATA_PATH.with_name("marks.json"))
)
ATTACHMENTS_PATH = Path(
    os.environ.get("VIBE_DEBUG_ATTACHMENTS", DATA_PATH.with_name("attachments"))
)
HOST = os.environ.get("VIBE_DEBUG_HOST", "127.0.0.1")
PORT = int(os.environ.get("VIBE_DEBUG_PORT", "8788"))
MAX_BODY_BYTES = 32_768
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_ATTACHMENT_BODY_BYTES = 12 * 1024 * 1024
MAX_ATTACHMENTS_PER_COMMENT = 6
STATUSES = {"new", "approved", "in_progress", "resolved", "wont_fix"}
MARK_KINDS = {"stroke", "rectangle"}
ATTACHMENT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class ValidationError(ValueError):
    """A request field is absent or malformed."""


def _clean_string(value: Any, field: str, maximum: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        if required:
            raise ValidationError(f"Поле «{field}» обязательно.")
        return ""
    cleaned = value.strip()
    if required and not cleaned:
        raise ValidationError(f"Поле «{field}» обязательно.")
    if len(cleaned) > maximum:
        raise ValidationError(f"Поле «{field}» слишком длинное.")
    return cleaned


def _number(value: Any, field: str, minimum: float, maximum: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Поле «{field}» указано неверно.") from exc
    return max(minimum, min(result, maximum))


def _target(payload: dict[str, Any], selector: str) -> dict[str, str]:
    raw_target = payload.get("target") or {}
    if not isinstance(raw_target, dict):
        raise ValidationError("Поле «target» должно быть объектом.")
    return {
        "selector": selector,
        "element": _clean_string(raw_target.get("element", ""), "элемент", 80, required=False),
        "sectionId": _clean_string(
            raw_target.get("sectionId", ""), "идентификатор секции", 160, required=False
        ),
        "heading": _clean_string(raw_target.get("heading", ""), "заголовок блока", 240, required=False),
        "label": _clean_string(raw_target.get("label", ""), "название блока", 240, required=False),
        "excerpt": _clean_string(raw_target.get("excerpt", ""), "фрагмент блока", 800, required=False),
    }


def _page(payload: dict[str, Any], route: str) -> dict[str, str]:
    return {
        "route": route,
        "title": _clean_string(payload.get("pageTitle", ""), "заголовок страницы", 240, required=False),
        "url": _clean_string(payload.get("url", ""), "URL", 1_000, required=False),
    }


def _anchor(payload: dict[str, Any]) -> dict[str, float | int]:
    raw = payload.get("anchor") or {}
    if not isinstance(raw, dict):
        raise ValidationError("Поле «anchor» должно быть объектом.")
    if not raw:
        return {}
    return {
        "x": round(_number(raw.get("x", 0.94), "позиция X", 0, 1), 4),
        "y": round(_number(raw.get("y", 0.08), "позиция Y", 0, 1), 4),
        "offsetX": round(_number(raw.get("offsetX", 0), "смещение X", 0, 20_000)),
        "offsetY": round(_number(raw.get("offsetY", 0), "смещение Y", 0, 20_000)),
        "targetWidth": round(_number(raw.get("targetWidth", 0), "ширина объекта", 0, 20_000)),
        "targetHeight": round(_number(raw.get("targetHeight", 0), "высота объекта", 0, 20_000)),
    }


def _valid_image_bytes(mime_type: str, data: bytes) -> bool:
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _attachment_filename(attachment_id: str, mime_type: str) -> str:
    return attachment_id + ATTACHMENT_TYPES[mime_type]


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_attachments = payload.get("attachments") or []
    if not isinstance(raw_attachments, list):
        raise ValidationError("Поле «attachments» должно быть массивом.")
    if len(raw_attachments) > MAX_ATTACHMENTS_PER_COMMENT:
        raise ValidationError("К одному комментарию можно прикрепить не более 6 изображений.")
    attachments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_attachments:
        if not isinstance(raw, dict):
            raise ValidationError("Вложение должно быть объектом.")
        attachment_id = _clean_string(raw.get("id"), "id вложения", 10)
        if not re.fullmatch(r"[A-F0-9]{10}", attachment_id) or attachment_id in seen:
            raise ValidationError("Некорректный id вложения.")
        mime_type = _clean_string(raw.get("mimeType"), "тип вложения", 40)
        if mime_type not in ATTACHMENT_TYPES:
            raise ValidationError("Поддерживаются PNG, JPEG и WebP.")
        filename = _attachment_filename(attachment_id, mime_type)
        attachment_path = ATTACHMENTS_PATH / filename
        if not attachment_path.is_file():
            raise ValidationError(f"Вложение {attachment_id} не найдено.")
        seen.add(attachment_id)
        attachments.append(
            {
                "id": attachment_id,
                "token": f"[скриншот#{attachment_id}]",
                "filename": _clean_string(
                    raw.get("filename", "скриншот"), "имя файла", 240, required=False
                )
                or "скриншот",
                "mimeType": mime_type,
                "size": attachment_path.stat().st_size,
                "width": round(_number(raw.get("width", 0), "ширина изображения", 0, 20_000)),
                "height": round(_number(raw.get("height", 0), "высота изображения", 0, 20_000)),
                "url": f"/__review__/attachments/{filename}",
            }
        )
    return attachments


def normalize_comment(payload: dict[str, Any], trusted_author: str = "") -> dict[str, Any]:
    route = _clean_string(payload.get("route", payload.get("page")), "страница", 240)
    if not route.startswith("/"):
        route = "/" + route

    author = _clean_string(trusted_author or payload.get("author"), "автор", 80)
    display_author = _clean_string(
        payload.get("displayAuthor", payload.get("author", author)), "отображаемое имя", 80
    )
    text = _clean_string(payload.get("text", payload.get("comment")), "комментарий", 4_000)
    attachments = _attachments(payload)
    for attachment in attachments:
        if attachment["token"] not in text:
            text += "\n" + attachment["token"]
    text = _clean_string(text, "комментарий", 4_000)
    raw_target = payload.get("target") or {}
    if not isinstance(raw_target, dict):
        raise ValidationError("Поле «target» должно быть объектом.")
    selector = _clean_string(
        payload.get("selector", raw_target.get("selector", ":root")), "объект", 800
    )

    raw_viewport = payload.get("viewport") or {}
    if not isinstance(raw_viewport, dict):
        raise ValidationError("Поле «viewport» должно быть объектом.")
    try:
        width = max(0, min(int(raw_viewport.get("width", 0)), 20_000))
        height = max(0, min(int(raw_viewport.get("height", 0)), 20_000))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Размер viewport указан неверно.") from exc

    created_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    target = _target(payload, selector)
    mode = _clean_string(payload.get("mode", "dev"), "режим", 12)
    if mode not in {"dev", "vibe", "art"}:
        raise ValidationError("Неизвестный режим комментария.")

    return {
        "id": "DBG-" + uuid.uuid4().hex[:10].upper(),
        "status": "new",
        "createdAt": created_at,
        "updatedAt": created_at,
        "author": author,
        "displayAuthor": display_author,
        "text": text,
        "mode": mode,
        "route": route,
        "selector": selector,
        "page": _page(payload, route),
        "target": target,
        "anchor": _anchor(payload),
        "viewport": {"width": width, "height": height},
        "attachments": attachments,
        "history": [{"at": created_at, "by": author, "action": "created", "status": "new"}],
    }


def normalize_mark_geometry(kind: str, raw_geometry: Any) -> dict[str, Any]:
    if not isinstance(raw_geometry, dict):
        raise ValidationError("Поле «geometry» должно быть объектом.")
    geometry: dict[str, Any] = {"coordinateSpace": "target-relative"}
    if kind == "stroke":
        raw_points = raw_geometry.get("points") or []
        if not isinstance(raw_points, list) or len(raw_points) < 2 or len(raw_points) > 2_000:
            raise ValidationError("Штрих должен содержать от 2 до 2000 точек.")
        geometry["points"] = [
            {
                "x": round(_number(point.get("x"), "точка X", 0, 1), 5),
                "y": round(_number(point.get("y"), "точка Y", 0, 1), 5),
            }
            for point in raw_points
            if isinstance(point, dict)
        ]
        if len(geometry["points"]) < 2:
            raise ValidationError("Штрих содержит некорректные точки.")
    else:
        raw_bounds = raw_geometry.get("bounds") or {}
        if not isinstance(raw_bounds, dict):
            raise ValidationError("Рамка должна содержать bounds.")
        width = _number(raw_bounds.get("width"), "ширина рамки", 0, 1)
        height = _number(raw_bounds.get("height"), "высота рамки", 0, 1)
        x = min(_number(raw_bounds.get("x"), "рамка X", 0, 1), 1 - width)
        y = min(_number(raw_bounds.get("y"), "рамка Y", 0, 1), 1 - height)
        geometry["bounds"] = {
            "x": round(x, 5),
            "y": round(y, 5),
            "width": round(width, 5),
            "height": round(height, 5),
        }
    return geometry


def normalize_mark(payload: dict[str, Any], trusted_author: str = "") -> dict[str, Any]:
    route = _clean_string(payload.get("route"), "страница", 240)
    if not route.startswith("/"):
        route = "/" + route
    kind = _clean_string(payload.get("kind"), "тип пометки", 20)
    if kind not in MARK_KINDS:
        raise ValidationError("Неизвестный тип графической пометки.")
    author = _clean_string(trusted_author or payload.get("author"), "автор", 80)
    display_author = _clean_string(
        payload.get("displayAuthor", payload.get("author", author)), "отображаемое имя", 80
    )
    raw_target = payload.get("target") or {}
    if not isinstance(raw_target, dict):
        raise ValidationError("Поле «target» должно быть объектом.")
    selector = _clean_string(
        payload.get("selector", raw_target.get("selector")), "объект", 800
    )
    raw_style = payload.get("style") or {}
    if not isinstance(raw_style, dict):
        raise ValidationError("Поле «style» должно быть объектом.")
    color = _clean_string(raw_style.get("color"), "цвет", 16)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValidationError("Цвет должен быть записан как #RRGGBB.")
    style = {
        "color": color.lower(),
        "thickness": round(_number(raw_style.get("thickness"), "толщина", 1, 32), 2),
    }
    geometry = normalize_mark_geometry(kind, payload.get("geometry"))
    created_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return {
        "id": "VIBE-" + uuid.uuid4().hex[:10].upper(),
        "kind": kind,
        "createdAt": created_at,
        "updatedAt": created_at,
        "author": author,
        "displayAuthor": display_author,
        "route": route,
        "selector": selector,
        "page": _page(payload, route),
        "target": _target(payload, selector),
        "style": style,
        "geometry": geometry,
        "viewport": payload.get("viewport") if isinstance(payload.get("viewport"), dict) else {},
        "history": [{"at": created_at, "by": author, "action": "created"}],
    }


class CommentStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Хранилище комментариев повреждено.") from exc
        if not isinstance(data, list):
            raise RuntimeError("Хранилище комментариев имеет неверный формат.")
        return [item for item in data if isinstance(item, dict)]

    def _write_unlocked(self, comments: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(comments, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def list(self, route: str = "") -> list[dict[str, Any]]:
        with self._lock:
            comments = self._read_unlocked()
        if route:
            comments = [item for item in comments if item.get("route") == route]
        return sorted(comments, key=lambda item: str(item.get("createdAt", "")), reverse=True)

    def add(self, payload: dict[str, Any], trusted_author: str = "") -> dict[str, Any]:
        comment = normalize_comment(payload, trusted_author)
        with self._lock:
            comments = self._read_unlocked()
            comments.append(comment)
            self._write_unlocked(comments)
        return comment

    def get(self, comment_id: str) -> dict[str, Any] | None:
        with self._lock:
            comments = self._read_unlocked()
        return next((item for item in comments if item.get("id") == comment_id), None)

    def set_status(self, comment_id: str, status: str, actor: str = "") -> dict[str, Any]:
        if status == "done":
            status = "resolved"
        if status not in STATUSES:
            raise ValidationError("Неизвестный статус комментария.")
        with self._lock:
            comments = self._read_unlocked()
            for item in comments:
                if item.get("id") == comment_id:
                    changed_at = (
                        datetime.now(timezone.utc)
                        .replace(microsecond=0)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                    item["status"] = status
                    item["updatedAt"] = changed_at
                    history = item.setdefault("history", [])
                    if isinstance(history, list):
                        history.append(
                            {
                                "at": changed_at,
                                "by": actor or "system",
                                "action": "status_changed",
                                "status": status,
                            }
                        )
                    self._write_unlocked(comments)
                    return item
        raise KeyError(comment_id)

    def delete(self, comment_id: str) -> bool:
        with self._lock:
            comments = self._read_unlocked()
            remaining = [item for item in comments if item.get("id") != comment_id]
            if len(remaining) == len(comments):
                return False
            self._write_unlocked(remaining)
            return True


STORE = CommentStore(DATA_PATH)


class AttachmentStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        mime_type = _clean_string(payload.get("mimeType"), "тип изображения", 40)
        if mime_type not in ATTACHMENT_TYPES:
            raise ValidationError("Поддерживаются PNG, JPEG и WebP.")
        encoded = _clean_string(payload.get("data"), "данные изображения", MAX_ATTACHMENT_BODY_BYTES)
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValidationError("Изображение повреждено.") from exc
        if not data or len(data) > MAX_ATTACHMENT_BYTES:
            raise ValidationError("Изображение должно быть не больше 8 МБ.")
        if not _valid_image_bytes(mime_type, data):
            raise ValidationError("Формат изображения не совпадает с содержимым файла.")
        attachment_id = uuid.uuid4().hex[:10].upper()
        filename = _attachment_filename(attachment_id, mime_type)
        self.path.mkdir(parents=True, exist_ok=True)
        with self._lock:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=filename + ".", suffix=".tmp", dir=self.path
            )
            temporary_path = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary_path, 0o600)
                os.replace(temporary_path, self.path / filename)
            finally:
                if temporary_path.exists():
                    temporary_path.unlink()
        return {
            "id": attachment_id,
            "token": f"[скриншот#{attachment_id}]",
            "filename": _clean_string(
                payload.get("filename", "скриншот"), "имя файла", 240, required=False
            )
            or "скриншот",
            "mimeType": mime_type,
            "size": len(data),
            "width": round(_number(payload.get("width", 0), "ширина изображения", 0, 20_000)),
            "height": round(_number(payload.get("height", 0), "высота изображения", 0, 20_000)),
            "url": f"/__review__/attachments/{filename}",
        }

    def delete(self, attachment_id: str) -> bool:
        if not re.fullmatch(r"[A-F0-9]{10}", attachment_id):
            return False
        deleted = False
        with self._lock:
            for suffix in ATTACHMENT_TYPES.values():
                path = self.path / (attachment_id + suffix)
                if path.is_file():
                    path.unlink()
                    deleted = True
        return deleted

    def resolve(self, filename: str) -> tuple[Path, str] | None:
        match = re.fullmatch(r"([A-F0-9]{10})(\.png|\.jpg|\.webp)", filename)
        if not match:
            return None
        mime_type = next(
            (current for current, suffix in ATTACHMENT_TYPES.items() if suffix == match.group(2)),
            "",
        )
        path = self.path / filename
        return (path, mime_type) if mime_type and path.is_file() else None


ATTACHMENT_STORE = AttachmentStore(ATTACHMENTS_PATH)


class MarkStore(CommentStore):
    def add(self, payload: dict[str, Any], trusted_author: str = "") -> dict[str, Any]:
        mark = normalize_mark(payload, trusted_author)
        with self._lock:
            marks = self._read_unlocked()
            marks.append(mark)
            self._write_unlocked(marks)
        return mark

    def update_geometry(
        self, mark_id: str, geometry: dict[str, Any], actor: str = ""
    ) -> dict[str, Any]:
        with self._lock:
            marks = self._read_unlocked()
            for mark in marks:
                if mark.get("id") != mark_id:
                    continue
                kind = str(mark.get("kind", ""))
                if kind not in MARK_KINDS:
                    raise ValidationError("Неизвестный тип графической пометки.")
                changed_at = (
                    datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                mark["geometry"] = normalize_mark_geometry(kind, geometry)
                mark["updatedAt"] = changed_at
                history = mark.setdefault("history", [])
                if isinstance(history, list):
                    history.append(
                        {
                            "at": changed_at,
                            "by": actor or "system",
                            "action": "geometry_changed",
                        }
                    )
                self._write_unlocked(marks)
                return mark
        raise KeyError(mark_id)


MARK_STORE = MarkStore(MARKS_PATH)


class VibeDebugHandler(SimpleHTTPRequestHandler):
    server_version = "TtHackVibeDebug/1.0"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _payload(self, maximum: int = MAX_BODY_BYTES) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValidationError("Некорректный размер запроса.") from exc
        if length <= 0 or length > maximum:
            raise ValidationError("Некорректный размер запроса.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("Ожидается корректный JSON.") from exc
        if not isinstance(payload, dict):
            raise ValidationError("Ожидается JSON-объект.")
        return payload

    def _trusted_author(self) -> str:
        return self.headers.get("X-Review-User", "").strip()[:80]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/__review__/session":
            self._json(HTTPStatus.OK, {"author": self._trusted_author()})
            return
        if parsed.path == "/__review__/comments":
            route = parse_qs(parsed.query).get("route", parse_qs(parsed.query).get("page", [""]))[0]
            try:
                self._json(HTTPStatus.OK, {"comments": STORE.list(route)})
            except RuntimeError as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if parsed.path == "/__review__/marks":
            route = parse_qs(parsed.query).get("route", [""])[0]
            try:
                self._json(HTTPStatus.OK, {"marks": MARK_STORE.list(route)})
            except RuntimeError as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if parsed.path.startswith("/__review__/attachments/"):
            resolved = ATTACHMENT_STORE.resolve(parsed.path.rsplit("/", 1)[-1])
            if not resolved:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Изображение не найдено."})
                return
            attachment_path, mime_type = resolved
            body = attachment_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "private, max-age=3600")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        try:
            payload = self._payload(
                MAX_ATTACHMENT_BODY_BYTES if path == "/__review__/attachments" else MAX_BODY_BYTES
            )
            if path == "/__review__/attachments":
                attachment = ATTACHMENT_STORE.add(payload)
                self._json(HTTPStatus.CREATED, {"attachment": attachment})
                return
            if path == "/__review__/attachments/delete":
                attachment_id = _clean_string(payload.get("id"), "id вложения", 10)
                deleted = ATTACHMENT_STORE.delete(attachment_id)
                self._json(HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND, {"deleted": deleted})
                return
            if path == "/__review__/comments":
                comment = STORE.add(payload, self._trusted_author())
                self._json(HTTPStatus.CREATED, {"comment": comment})
                return
            if path == "/__review__/comments/status":
                item = STORE.set_status(
                    _clean_string(payload.get("id"), "id", 80),
                    _clean_string(payload.get("status"), "статус", 40),
                    self._trusted_author() or _clean_string(
                        payload.get("author") or "system", "автор", 80
                    ),
                )
                self._json(HTTPStatus.OK, {"comment": item})
                return
            if path == "/__review__/marks":
                mark = MARK_STORE.add(payload, self._trusted_author())
                self._json(HTTPStatus.CREATED, {"mark": mark})
                return
            if path == "/__review__/marks/update":
                mark = MARK_STORE.update_geometry(
                    _clean_string(payload.get("id"), "id", 80),
                    payload.get("geometry"),
                    self._trusted_author() or _clean_string(
                        payload.get("author", "system"), "автор", 80
                    ),
                )
                self._json(HTTPStatus.OK, {"mark": mark})
                return
            if path == "/__review__/marks/delete":
                mark_id = _clean_string(payload.get("id"), "id", 80)
                if not MARK_STORE.delete(mark_id):
                    self._json(HTTPStatus.NOT_FOUND, {"error": "Пометка не найдена."})
                    return
                self._json(HTTPStatus.OK, {"deleted": mark_id})
                return
            if path == "/__review__/comments/delete":
                comment_id = _clean_string(payload.get("id"), "id", 80)
                comment = STORE.get(comment_id)
                deleted = STORE.delete(comment_id)
                if deleted and comment:
                    for attachment in comment.get("attachments") or []:
                        if isinstance(attachment, dict):
                            ATTACHMENT_STORE.delete(str(attachment.get("id", "")))
                self._json(HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND, {"deleted": deleted})
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "Маршрут не найден."})
        except ValidationError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except KeyError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Комментарий не найден."})
        except RuntimeError as exc:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), VibeDebugHandler)
    print(f"Vibe Debug: http://{HOST}:{PORT}/index.html")
    print(f"Комментарии: {DATA_PATH}")
    print(f"Графические пометки: {MARKS_PATH}")
    print(f"Скриншоты: {ATTACHMENTS_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
