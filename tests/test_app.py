import tempfile
import unittest
from pathlib import Path

from app import classify_url, create_app, extract_urls, sync_markdown


class UrlExtractionTests(unittest.TestCase):
    def test_extracts_bare_and_markdown_urls_and_removes_punctuation(self):
        text = "Bare https://example.com/post. Markdown [PR](https://github.com/org/repo/pull/42)."
        self.assertEqual(
            extract_urls(text),
            ["https://example.com/post", "https://github.com/org/repo/pull/42"],
        )

    def test_deduplicates_canonical_urls_in_first_seen_order(self):
        text = "https://Example.com/path/ https://example.com/path https://second.example/a"
        self.assertEqual(extract_urls(text), ["https://Example.com/path/", "https://second.example/a"])


class ClassificationTests(unittest.TestCase):
    def test_github_source_types_repository_and_ids(self):
        cases = {
            "https://github.com/org/repo/pull/4319": ("github_pr", "org/repo", "4319"),
            "https://github.com/org/repo/issues/625": ("github_issue", "org/repo", "625"),
            "https://github.com/org/repo/discussions/285": ("github_discussion", "org/repo", "285"),
            "https://github.com/org/repo/commit/1163f500e455": ("github_commit", "org/repo", "1163f500e455"),
            "https://github.com/org/repo": ("github_repo", "org/repo", ""),
            "https://github.com/org/repo/releases/tag/v1.0": ("github_release", "org/repo", "v1.0"),
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                actual = classify_url(url)
                self.assertEqual((actual["source_type"], actual["repository"], actual["source_number_or_id"]), expected)

    def test_non_github_blog_is_retained_and_classified(self):
        self.assertEqual(classify_url("https://ladybird.org/posts/adopting-rust/")["source_type"], "project_blog")


class SyncTests(unittest.TestCase):
    def test_sync_does_not_overwrite_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "GoodData.md"
            database = root / "annotations.db"
            url = "https://github.com/org/repo/pull/7"
            markdown.write_text(url, encoding="utf-8")
            app = create_app(markdown, database, root / "exports")
            self.assertEqual(sync_markdown(markdown, database), {"found": 1, "added": 1, "existing": 0})
            client = app.test_client()
            source = client.get("/api/sources").get_json()["items"][0]
            response = client.patch(f"/api/sources/{source['id']}", json={"choice": "Rust", "target": "parser"})
            self.assertEqual(response.status_code, 200)

            markdown.write_text(f"{url}\nhttps://example.com/blog/new", encoding="utf-8")
            self.assertEqual(sync_markdown(markdown, database), {"found": 2, "added": 1, "existing": 1})
            preserved = client.get(f"/api/sources/{source['id']}").get_json()
            self.assertEqual(preserved["choice"], "Rust")
            self.assertEqual(preserved["target"], "parser")

    def test_empty_fields_and_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markdown = root / "GoodData.md"
            database = root / "annotations.db"
            markdown.write_text("https://example.com/docs/page", encoding="utf-8")
            app = create_app(markdown, database, root / "exports")
            client = app.test_client()
            home = client.get("/")
            self.assertEqual(home.status_code, 200)
            self.assertIn(b'id="language-select"', home.data)
            self.assertEqual(client.post("/api/sync").status_code, 200)
            source = client.get("/api/sources").get_json()["items"][0]
            self.assertEqual(client.patch(f"/api/sources/{source['id']}", json={"target": "", "other": ""}).status_code, 200)
            csv_response = client.get("/api/export/csv")
            json_response = client.get("/api/export/json")
            self.assertEqual(csv_response.status_code, 200)
            self.assertEqual(json_response.status_code, 200)
            csv_response.close()
            json_response.close()


if __name__ == "__main__":
    unittest.main()
