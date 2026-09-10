from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from flask import Flask, jsonify, render_template, request, send_file


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_DIR.parent / "GoodData.md"
DEFAULT_DATABASE = PROJECT_DIR / "data" / "annotations.db"
EXPORT_DIR = PROJECT_DIR / "exports"

SOURCE_TYPES = (
    "github_pr",
    "github_issue",
    "github_discussion",
    "github_commit",
    "github_repo",
    "github_release",
    "bugzilla",
    "project_blog",
    "documentation",
    "other",
)
SCOPES = ("function", "module", "project", "unknown")
ANNOTATION_FIELDS = (
    "source_type",
    "target",
    "project_status",
    "candidates",
    "choice",
    "scope",
    "evidence",
    "rationale",
    "other",
)
EXPORT_FIELDS = (
    "url",
    "source_type",
    "repository",
    "source_number_or_id",
    "target",
    "project_status",
    "candidates",
    "choice",
    "scope",
    "evidence",
    "rationale",
    "other",
    "created_at",
    "updated_at",
)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_extracted_url(value: str) -> str:
    value = html.unescape(value.strip())
    value = value.rstrip(".,;:!?，。；：！？、")
    closing_pairs = ((")", "("), ("]", "["), ("}", "{"))
    changed = True
    while changed and value:
        changed = False
        for closing, opening in closing_pairs:
            if value.endswith(closing) and value.count(closing) > value.count(opening):
                value = value[:-1]
                changed = True
    return value


def canonicalize_url(value: str) -> str:
    value = clean_extracted_url(value)
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Not a valid HTTP(S) URL")
    scheme = parts.scheme.lower()
    hostname = parts.hostname.lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    if parts.username or parts.password:
        raise ValueError("URLs containing credentials are not supported")
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, hostname, path, parts.query, ""))


def extract_urls(markdown_text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in URL_RE.finditer(markdown_text):
        raw_url = clean_extracted_url(match.group(0))
        try:
            canonical = canonicalize_url(raw_url)
        except ValueError:
            continue
        if canonical not in seen:
            seen.add(canonical)
            found.append(raw_url)
    return found


def classify_url(url: str) -> dict[str, str]:
    parts = urlsplit(url)
    hostname = (parts.hostname or "").lower()
    segments = [segment for segment in parts.path.split("/") if segment]
    result = {"source_type": "other", "repository": "", "source_number_or_id": ""}

    if hostname in {"github.com", "www.github.com"} and len(segments) >= 2:
        result["repository"] = f"{segments[0]}/{segments[1]}"
        if len(segments) == 2:
            result["source_type"] = "github_repo"
        elif len(segments) >= 4 and segments[2] == "pull" and segments[3].isdigit():
            result.update(source_type="github_pr", source_number_or_id=segments[3])
        elif len(segments) >= 4 and segments[2] == "issues" and segments[3].isdigit():
            result.update(source_type="github_issue", source_number_or_id=segments[3])
        elif len(segments) >= 4 and segments[2] == "discussions" and segments[3].isdigit():
            result.update(source_type="github_discussion", source_number_or_id=segments[3])
        elif len(segments) >= 4 and segments[2] in {"commit", "commits"}:
            result.update(source_type="github_commit", source_number_or_id=segments[3])
        elif len(segments) >= 3 and segments[2] in {"release", "releases"}:
            release_id = segments[4] if len(segments) >= 5 and segments[3] == "tag" else (segments[3] if len(segments) >= 4 else "")
            result.update(source_type="github_release", source_number_or_id=release_id)
        elif any(segment.lower() in {"docs", "documentation", "wiki", "readme.md"} for segment in segments[2:]):
            result["source_type"] = "documentation"
        return result

    if "bugzilla" in hostname or parts.path.lower().endswith("show_bug.cgi"):
        result["source_type"] = "bugzilla"
        match = re.search(r"(?:^|[?&])id=([^&]+)", parts.query)
        if match:
            result["source_number_or_id"] = match.group(1)
    elif any(token in hostname or token in parts.path.lower() for token in ("docs.", "/docs/", "/documentation/", "/wiki/")):
        result["source_type"] = "documentation"
    elif any(token in parts.path.lower() for token in ("/blog/", "/blogs/", "/post/", "/posts/", "/news/", "/announcement")):
        result["source_type"] = "project_blog"
    return result


@contextmanager
def connect_database(path: Path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect_database(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                canonical_url TEXT NOT NULL UNIQUE,
                source_type TEXT NOT NULL DEFAULT 'other',
                repository TEXT NOT NULL DEFAULT '',
                source_number_or_id TEXT NOT NULL DEFAULT '',
                target TEXT NOT NULL DEFAULT '',
                project_status TEXT NOT NULL DEFAULT '',
                candidates TEXT NOT NULL DEFAULT '',
                choice TEXT NOT NULL DEFAULT '',
                scope TEXT NOT NULL DEFAULT 'unknown',
                evidence TEXT NOT NULL DEFAULT '',
                rationale TEXT NOT NULL DEFAULT 'unknown',
                other TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def sync_markdown(input_path: Path, database_path: Path) -> dict[str, int]:
    urls = extract_urls(input_path.read_text(encoding="utf-8"))
    added = 0
    existing = 0
    now = utc_now()
    with connect_database(database_path) as connection:
        for url in urls:
            canonical = canonicalize_url(url)
            present = connection.execute("SELECT id FROM annotations WHERE canonical_url = ?", (canonical,)).fetchone()
            if present:
                existing += 1
                continue
            metadata = classify_url(url)
            connection.execute(
                """
                INSERT INTO annotations (
                    url, canonical_url, source_type, repository, source_number_or_id,
                    scope, rationale, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'unknown', 'unknown', ?, ?)
                """,
                (url, canonical, metadata["source_type"], metadata["repository"], metadata["source_number_or_id"], now, now),
            )
            added += 1
    return {"found": len(urls), "added": added, "existing": existing}


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys() if key != "canonical_url"}


def create_app(
    input_path: Path | None = None,
    database_path: Path | None = None,
    export_dir: Path | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["INPUT_PATH"] = Path(input_path or DEFAULT_INPUT).resolve()
    app.config["DATABASE_PATH"] = Path(database_path or DEFAULT_DATABASE).resolve()
    app.config["EXPORT_DIR"] = Path(export_dir or EXPORT_DIR).resolve()
    initialize_database(app.config["DATABASE_PATH"])

    @app.get("/")
    def index():
        return render_template("index.html", source_types=SOURCE_TYPES, scopes=SCOPES)

    @app.get("/api/sources")
    def list_sources():
        query = request.args.get("q", "").strip()
        scope = request.args.get("scope", "all")
        source_type = request.args.get("source_type", "all")
        clauses: list[str] = []
        values: list[str] = []
        if query:
            clauses.append("(url LIKE ? OR repository LIKE ? OR choice LIKE ? OR target LIKE ?)")
            wildcard = f"%{query}%"
            values.extend([wildcard] * 4)
        if scope != "all":
            clauses.append("scope = ?")
            values.append(scope)
        if source_type != "all":
            clauses.append("source_type = ?")
            values.append(source_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(app.config["DATABASE_PATH"]) as connection:
            rows = connection.execute(f"SELECT * FROM annotations {where} ORDER BY id", values).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
        return jsonify({"items": [row_to_dict(row) for row in rows], "shown": len(rows), "total": total})

    @app.get("/api/sources/<int:source_id>")
    def get_source(source_id: int):
        with connect_database(app.config["DATABASE_PATH"]) as connection:
            row = connection.execute("SELECT * FROM annotations WHERE id = ?", (source_id,)).fetchone()
        if not row:
            return jsonify({"error": "Source not found"}), 404
        return jsonify(row_to_dict(row))

    @app.patch("/api/sources/<int:source_id>")
    def update_source(source_id: int):
        payload = request.get_json(silent=True) or {}
        updates = {field: payload[field] for field in ANNOTATION_FIELDS if field in payload}
        if not updates:
            return jsonify({"error": "No editable fields supplied"}), 400
        if "source_type" in updates and updates["source_type"] not in SOURCE_TYPES:
            return jsonify({"error": "Invalid source_type"}), 400
        if "scope" in updates and updates["scope"] not in SCOPES:
            return jsonify({"error": "Invalid scope"}), 400
        for field, value in updates.items():
            if not isinstance(value, str):
                return jsonify({"error": f"{field} must be a string"}), 400
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{field} = ?" for field in updates)
        values = list(updates.values()) + [source_id]
        with connect_database(app.config["DATABASE_PATH"]) as connection:
            cursor = connection.execute(f"UPDATE annotations SET {assignments} WHERE id = ?", values)
            if cursor.rowcount == 0:
                return jsonify({"error": "Source not found"}), 404
            row = connection.execute("SELECT * FROM annotations WHERE id = ?", (source_id,)).fetchone()
        return jsonify(row_to_dict(row))

    @app.post("/api/sync")
    def sync_sources():
        input_file = app.config["INPUT_PATH"]
        if not input_file.is_file():
            return jsonify({"error": f"Input Markdown file not found: {input_file}"}), 404
        try:
            result = sync_markdown(input_file, app.config["DATABASE_PATH"])
        except (OSError, UnicodeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400
        return jsonify(result)

    def export_rows() -> list[dict[str, Any]]:
        with connect_database(app.config["DATABASE_PATH"]) as connection:
            rows = connection.execute("SELECT * FROM annotations ORDER BY id").fetchall()
        return [{field: row[field] for field in EXPORT_FIELDS} for row in rows]

    @app.get("/api/export/csv")
    def export_csv():
        app.config["EXPORT_DIR"].mkdir(parents=True, exist_ok=True)
        output_path = app.config["EXPORT_DIR"] / "annotations.csv"
        with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS)
            writer.writeheader()
            writer.writerows(export_rows())
        return send_file(output_path, as_attachment=True, download_name="annotations.csv", mimetype="text/csv")

    @app.get("/api/export/json")
    def export_json():
        app.config["EXPORT_DIR"].mkdir(parents=True, exist_ok=True)
        output_path = app.config["EXPORT_DIR"] / "annotations.json"
        output_path.write_text(json.dumps(export_rows(), ensure_ascii=False, indent=2), encoding="utf-8")
        return send_file(output_path, as_attachment=True, download_name="annotations.json", mimetype="application/json")

    return app


def load_config(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local language-choice evidence annotation tool")
    parser.add_argument("--input", type=Path, help="Markdown file containing evidence URLs")
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument("--host", default=None, help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="Server port (default: 5000)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    configured_input = args.input or (Path(config["input"]) if config.get("input") else DEFAULT_INPUT)
    configured_database = Path(config["database"]) if config.get("database") else DEFAULT_DATABASE
    application = create_app(configured_input, configured_database)
    if application.config["INPUT_PATH"].is_file():
        sync_result = sync_markdown(application.config["INPUT_PATH"], application.config["DATABASE_PATH"])
        print(
            f"Initial sync: found {sync_result['found']} URLs, "
            f"added {sync_result['added']}, already existed {sync_result['existing']}."
        )
    else:
        print(f"Input Markdown file not found: {application.config['INPUT_PATH']}")
    application.run(host=args.host or config.get("host", "127.0.0.1"), port=args.port or int(config.get("port", 5000)), debug=False)
