"""CLI for grimoire."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from .banner import GRIMOIRE_BANNER
from .store import (add_link, add_quote, export_html, list_notes, new_note, promote_note,
                    read_note, search_notes, search_quotes, sync_schema)

console = Console()


def _banner() -> None:
    console.print(f"[bold yellow]{GRIMOIRE_BANNER}[/bold yellow]")


class BannerGroup(click.Group):
    def get_help(self, ctx: click.Context) -> str:
        _banner()
        return super().get_help(ctx)


@click.group(cls=BannerGroup)
def main() -> None:
    """MAD local wiki."""


@main.command("new")
@click.argument("title")
@click.option("--wiki", "as_wiki", is_flag=True)
def new_cmd(title: str, as_wiki: bool) -> None:
    path = new_note(title, wiki=as_wiki)
    console.print(f"[green]Created[/green] {path}")


@main.command("list")
@click.option("--wiki", "as_wiki", is_flag=True)
def list_cmd(as_wiki: bool) -> None:
    table = Table(title="Notes")
    table.add_column("Path")
    for path in list_notes(wiki=as_wiki):
        table.add_row(str(path))
    console.print(table)


@main.command("search")
@click.argument("query")
def search_cmd(query: str) -> None:
    table = Table(title=f"Search: {query}")
    table.add_column("Path")
    for path in search_notes(query):
        table.add_row(str(path))
    console.print(table)


@main.command("show")
@click.argument("slug")
def show_cmd(slug: str) -> None:
    console.print(Markdown(read_note(slug).read_text(encoding="utf-8")))


@main.command("link")
@click.argument("src")
@click.argument("dst")
def link_cmd(src: str, dst: str) -> None:
    add_link(src, dst)
    console.print(f"[green]Linked[/green] {src} -> {dst}")


@main.group("quote")
def quote_group() -> None:
    """Quote helpers."""


@quote_group.command("add")
@click.option("--text", prompt=True)
@click.option("--author", prompt=True)
@click.option("--source", prompt=True)
@click.option("--tags", default="")
@click.option("--lang", default="ru", show_default=True)
def quote_add_cmd(text: str, author: str, source: str, tags: str, lang: str) -> None:
    item = add_quote(text, author, source, [tag.strip() for tag in tags.split(",") if tag.strip()], lang)
    console.print(f"[green]Added[/green] {item['id']}")


@quote_group.command("search")
@click.argument("query")
def quote_search_cmd(query: str) -> None:
    table = Table(title=f"Quotes: {query}")
    table.add_column("ID")
    table.add_column("Author")
    table.add_column("Text")
    for item in search_quotes(query):
        table.add_row(item["id"], item["author"], item["text"][:120])
    console.print(table)


@main.command("promote")
@click.argument("slug")
@click.option("--target", default=None, help="цель находки")
@click.option("--type", "vuln_type", default=None, help="тип уязвимости")
@click.option("--severity", default=None, help="critical|high|medium|low|info")
@click.option("--program", default=None, help="программа H1")
@click.option("--output", type=click.Path(path_type=Path), help="сохранить finding-JSON")
def promote_cmd(slug: str, target: str | None, vuln_type: str | None, severity: str | None,
                program: str | None, output: Path | None) -> None:
    """Развернуть заметку-разведку в находку (JSON схемы finding-organizer) — заметка→находка."""
    import json

    over = {k: v for k, v in (("target", target), ("type", vuln_type),
                              ("severity", severity), ("program", program)) if v}
    finding = promote_note(slug, **over)
    text = json.dumps(finding, ensure_ascii=False, indent=2)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
        console.print(f"[green]Promoted[/green] {slug} -> {output}")
    else:
        console.print(text)


@main.command("sync")
def sync_cmd() -> None:
    sync_schema()
    console.print("[green]Schema synced[/green]")


@main.command("export")
@click.option("--format", "fmt", default="html", type=click.Choice(["html"]), show_default=True)
def export_cmd(fmt: str) -> None:
    path = export_html()
    console.print(f"[green]Exported[/green] {path}")


if __name__ == "__main__":
    main()
