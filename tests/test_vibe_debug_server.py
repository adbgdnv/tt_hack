import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.review_schema import load_schema, validate
from scripts.vibe_debug_server import (
    AttachmentStore,
    CommentStore,
    MarkStore,
    ValidationError,
    normalize_comment,
)


class VibeDebugStoreTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "comments.json"
        self.store = CommentStore(self.path)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_comments_from_different_authenticated_users_persist(self):
        first = self.store.add(
            {
                "route": "/catalog.html",
                "selector": "#products",
                "viewport": {"width": 1440, "height": 900},
                "author": "подменённый автор",
                "displayAuthor": "Божена",
                "text": "Первый комментарий",
                "mode": "vibe",
                "anchor": {"x": 0.45, "y": 0.3, "offsetX": 120, "offsetY": 48},
                "pageTitle": "Каталог",
                "url": "https://lapki-demo.academcheck.ru/catalog.html",
                "target": {
                    "element": "section",
                    "sectionId": "catalog-grid",
                    "heading": "Каталог",
                    "label": "Каталог",
                    "excerpt": "Карточки товаров",
                },
            },
            trusted_author="bozhenkas",
        )
        second = self.store.add(
            {
                "route": "/catalog.html",
                "selector": ":root",
                "viewport": {"width": 390, "height": 844},
                "text": "Второй комментарий",
            },
            trusted_author="bondarika",
        )

        saved = CommentStore(self.path).list("/catalog.html")
        self.assertEqual({item["author"] for item in saved}, {"bozhenkas", "bondarika"})
        self.assertEqual(first["status"], "new")
        self.assertEqual(first["author"], "bozhenkas")
        self.assertEqual(first["displayAuthor"], "Божена")
        self.assertEqual(first["mode"], "vibe")
        self.assertEqual(first["anchor"]["x"], 0.45)
        self.assertEqual(first["page"]["title"], "Каталог")
        self.assertEqual(first["target"]["heading"], "Каталог")
        self.assertEqual(first["target"]["selector"], "#products")
        self.assertEqual(first["history"][0]["action"], "created")
        self.assertEqual(second["viewport"]["width"], 390)
        self.assertEqual(len(json.loads(self.path.read_text(encoding="utf-8"))), 2)

    def test_route_filter_and_status_lifecycle(self):
        current = self.store.add(
            {"route": "/about.html", "selector": ":root", "author": "local", "text": "Текст"}
        )
        self.store.add(
            {"route": "/faq.html", "selector": ":root", "author": "local", "text": "Другое"}
        )

        updated = self.store.set_status(current["id"], "approved", "reviewer")
        self.assertEqual(updated["status"], "approved")
        self.assertEqual(updated["history"][-1]["by"], "reviewer")
        self.assertEqual(len(self.store.list("/about.html")), 1)
        self.assertEqual(len(self.store.list("/faq.html")), 1)
        self.assertEqual(len(self.store.list()), 2)

    def test_comment_can_be_deleted(self):
        comment = self.store.add(
            {"route": "/contacts.html", "selector": ":root", "author": "local", "text": "Удалить"}
        )

        self.assertTrue(self.store.delete(comment["id"]))
        self.assertEqual(self.store.list("/contacts.html"), [])
        self.assertFalse(self.store.delete(comment["id"]))

    def test_screenshot_is_stored_and_linked_from_comment_context(self):
        attachment_path = Path(self.temporary_directory.name) / "attachments"
        attachment_store = AttachmentStore(attachment_path)
        png = base64.b64encode(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
        ).decode("ascii")
        attachment = attachment_store.add(
            {
                "filename": "review.png",
                "mimeType": "image/png",
                "width": 1,
                "height": 1,
                "data": png,
            }
        )

        with patch("scripts.vibe_debug_server.ATTACHMENTS_PATH", attachment_path):
            comment = normalize_comment(
                {
                    "route": "/product.html",
                    "selector": ":root",
                    "author": "local",
                    "text": "Посмотрите сюда",
                    "attachments": [attachment],
                }
            )

        self.assertIn(attachment["token"], comment["text"])
        self.assertEqual(comment["attachments"][0]["id"], attachment["id"])
        self.assertEqual(comment["attachments"][0]["width"], 1)
        self.assertTrue((attachment_path / f"{attachment['id']}.png").is_file())
        self.assertTrue(attachment_store.delete(attachment["id"]))

    def test_validation_rejects_empty_comment(self):
        with self.assertRaises(ValidationError):
            normalize_comment({"route": "/", "author": "local", "text": " "})

    def test_stored_comment_matches_published_schema(self):
        schema = load_schema()
        comment = normalize_comment(
            {
                "route": "/catalog.html",
                "selector": 'main [data-debug-id="s-03-каталог"]',
                "author": "lapki",
                "displayAuthor": "Лапки",
                "text": "Плашка «веган» должна быть видна на карточке",
                "mode": "vibe",
                "pageTitle": "S-03 Каталог — Биолапки, каркас",
                "url": "https://lapki-demo.academcheck.ru/catalog.html",
                "target": {
                    "element": "section",
                    "sectionId": "S-03",
                    "heading": "Ассортимент",
                    "label": "Ассортимент",
                    "excerpt": "Карточки товаров",
                },
                "anchor": {"x": 0.4, "y": 0.2, "offsetX": 12, "offsetY": 8},
                "viewport": {"width": 1440, "height": 748},
            }
        )

        self.assertEqual(validate(comment, schema), [])

        store = CommentStore(self.path)
        stored = store.add(comment | {"author": "lapki"}, "lapki")
        self.assertEqual(validate(stored, schema), [])

        moved = store.set_status(stored["id"], "in_progress", "bozhenkas")
        self.assertEqual(validate(moved, schema), [])

    def test_stroke_and_rectangle_are_ai_ready_and_route_scoped(self):
        mark_store = MarkStore(Path(self.temporary_directory.name) / "marks.json")
        common = {
            "route": "/product.html",
            "selector": '[data-debug-id="product-card"]',
            "displayAuthor": "Арт-директор",
            "pageTitle": "Карточка товара",
            "url": "https://lapki-demo.academcheck.ru/product.html",
            "target": {
                "element": "section",
                "label": "Карточка товара",
                "excerpt": "Название, состав и цена",
            },
            "style": {"color": "#A96F7B", "thickness": 6},
        }
        stroke = mark_store.add(
            {
                **common,
                "kind": "stroke",
                "geometry": {
                    "points": [{"x": 0.1, "y": 0.2}, {"x": 0.4, "y": 0.5}]
                },
            },
            trusted_author="lapki",
        )
        rectangle = mark_store.add(
            {
                **common,
                "kind": "rectangle",
                "geometry": {
                    "bounds": {"x": 0.2, "y": 0.1, "width": 0.5, "height": 0.4}
                },
            },
            trusted_author="lapki",
        )

        self.assertEqual(stroke["author"], "lapki")
        self.assertEqual(stroke["displayAuthor"], "Арт-директор")
        self.assertEqual(stroke["geometry"]["coordinateSpace"], "target-relative")
        self.assertEqual(stroke["style"], {"color": "#a96f7b", "thickness": 6.0})
        self.assertEqual(rectangle["geometry"]["bounds"]["width"], 0.5)
        self.assertEqual(len(mark_store.list("/product.html")), 2)

        moved_stroke = mark_store.update_geometry(
            stroke["id"],
            {"points": [{"x": 0.2, "y": 0.25}, {"x": 0.5, "y": 0.55}]},
            "Арт-директор",
        )
        self.assertEqual(moved_stroke["geometry"]["points"][0]["x"], 0.2)
        self.assertEqual(moved_stroke["history"][-1]["action"], "geometry_changed")

        moved = mark_store.update_geometry(
            rectangle["id"],
            {"bounds": {"x": 0.45, "y": 0.4, "width": 0.5, "height": 0.4}},
            "Арт-директор",
        )
        self.assertEqual(moved["geometry"]["bounds"]["x"], 0.45)
        self.assertEqual(moved["history"][-1]["action"], "geometry_changed")
        self.assertEqual(moved["history"][-1]["by"], "Арт-директор")
        self.assertTrue(mark_store.delete(rectangle["id"]))
        self.assertEqual(len(mark_store.list("/product.html")), 1)


if __name__ == "__main__":
    unittest.main()
