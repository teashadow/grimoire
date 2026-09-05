"""Filesystem storage for wiki."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

WIKI_ROOT = Path.home() / "wiki"
RAW_DIR = WIKI_ROOT / "raw"
WIKI_DIR = WIKI_ROOT / "wiki"
SCHEMA_DIR = WIKI_ROOT / "schema"
LINKS_PATH = SCHEMA_DIR / "links.json"
TAGS_PATH = SCHEMA_DIR / "tags.json"
QUOTES_PATH = SCHEMA_DIR / "quotes.json"


def ensure_structure() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for path, default in (
        (LINKS_PATH, {}),
        (TAGS_PATH, {}),
        (QUOTES_PATH, []),
    ):
        if not path.exists():
            path.write_text(json.dumps(default, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9а-яА-Я]+", "-", title.strip().lower()).strip("-")
    return slug or "note"


def new_note(title: str, *, wiki: bool = False) -> Path:
    ensure_structure()
    slug = slugify(title)
    target = WIKI_DIR if wiki else RAW_DIR
    filename = f"{slug}.md" if wiki else f"{date.today().isoformat()}_{slug}.md"
    path = target / filename
    if wiki:
        post = frontmatter.Post(
            f"# {title}\n\n## Суть атаки\n...\n",
            **{
                "title": title,
                "tags": ["mad"],
                "created": date.today().isoformat(),
                "updated": date.today().isoformat(),
                "links": [],
            },
        )
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
    else:
        path.write_text(f"# {title}\n\n", encoding="utf-8")
    return path


def list_notes(*, wiki: bool = False) -> list[Path]:
    ensure_structure()
    target = WIKI_DIR if wiki else RAW_DIR
    return sorted(target.glob("*.md"))


_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}_")


def _note_slug(path: Path) -> str:
    """Slug заметки без дата-префикса: '2026-08-11_acme-ssrf.md' → 'acme-ssrf'."""
    return _DATE_PREFIX.sub("", path.stem)


def read_note(slug: str) -> Path:
    ensure_structure()
    # raw-заметки названы '<дата>_<slug>.md' — сверяем по slug-части, а не по началу имени (там дата)
    for target in (WIKI_DIR, RAW_DIR):
        for path in target.glob("*.md"):
            if path.stem == slug or _note_slug(path) == slug:
                return path
    raise FileNotFoundError(f"note not found: {slug}")


def search_notes(query: str) -> list[Path]:
    ensure_structure()
    hits = []
    q = query.lower()
    for path in list_notes() + list_notes(wiki=True):
        if q in path.read_text(encoding="utf-8").lower():
            hits.append(path)
    return hits


def add_link(src: str, dst: str) -> None:
    ensure_structure()
    data = json.loads(LINKS_PATH.read_text(encoding="utf-8"))
    data.setdefault(src, [])
    if dst not in data[src]:
        data[src].append(dst)
    LINKS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_schema() -> None:
    ensure_structure()
    links: dict[str, list[str]] = {}
    tags: dict[str, list[str]] = {}
    for path in list_notes(wiki=True):
        post = frontmatter.load(path)
        slug = path.stem
        links[slug] = list(post.metadata.get("links", []))
        for tag in post.metadata.get("tags", []):
            tags.setdefault(tag, []).append(slug)
    LINKS_PATH.write_text(json.dumps(links, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    TAGS_PATH.write_text(json.dumps(tags, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_quote(text: str, author: str, source: str, tags: list[str], lang: str) -> dict[str, Any]:
    ensure_structure()
    quotes = json.loads(QUOTES_PATH.read_text(encoding="utf-8"))
    next_id = f"q{len(quotes) + 1:03d}"
    item = {"id": next_id, "text": text, "author": author, "source": source, "tags": tags, "lang": lang}
    quotes.append(item)
    QUOTES_PATH.write_text(json.dumps(quotes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return item


def search_quotes(query: str) -> list[dict[str, Any]]:
    ensure_structure()
    q = query.lower()
    quotes = json.loads(QUOTES_PATH.read_text(encoding="utf-8"))
    return [item for item in quotes if q in json.dumps(item, ensure_ascii=False).lower()]


def export_html() -> Path:
    ensure_structure()
    from html import escape  # экранируем: скопированный ответ цели с </pre><script> не исполнится
    html = ["<html><body><h1>grimoire</h1>"]
    for path in list_notes(wiki=True):
        html.append(f"<h2>{escape(path.stem)}</h2><pre>{escape(path.read_text(encoding='utf-8'))}</pre>")
    html.append("</body></html>")
    out = WIKI_ROOT / "export.html"
    out.write_text("\n".join(html), encoding="utf-8")
    return out


def promote_note(slug: str, **overrides: Any) -> dict[str, Any]:
    """Заметка-разведка → находка (схема finding-organizer). Кирпич цепочки заметка→находка→репорт.

    Контракт: выданный dict грузится как finding-organizer Finding (source=manual, status=queue).
    Гипотеза из вики становится структурированной находкой; тип/платформа/severity — из overrides
    или плейсхолдеры (заполнит человек перед репортом). Заметка НЕ удаляется — промоут это копия.
    """
    path = read_note(slug)
    post = frontmatter.load(path)   # работает и на raw (metadata пуст, content = весь текст)
    body = post.content.strip()
    tags = list(post.metadata.get("tags", []))
    # человеческий заголовок: frontmatter → первая '# '-строка тела → slug (последнее — хуже всего)
    title = post.metadata.get("title")
    if not title:
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
    title = title or slug
    today = date.today().isoformat()
    finding = {
        "id": f"F-{today}-{slugify(title)[:24]}",
        "created": today, "updated": today,
        "title": title,
        "platform": overrides.get("platform", "private"),
        "program": overrides.get("program", "[program name]"),
        "severity": overrides.get("severity", "info"),   # info = ещё гипотеза, поднимет человек
        "type": overrides.get("type", "prompt-injection"),
        "status": "queue",
        "target": overrides.get("target", "[TARGET]"),
        "description": body,
        "steps": overrides.get("steps", []),
        "impact": overrides.get("impact", ""),
        # провенанс — в теги, НЕ в notes: downstream (disclosure) читает notes как PoC-payload,
        # а у промоутнутой гипотезы payload'а ещё нет — пусть остаётся каркас-подсказка человеку
        "tags": tags + [f"promoted-from:{path.name}"],
        "notes": "",
        "source": "manual",
    }
    return finding
