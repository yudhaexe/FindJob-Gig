"""`fjg` command line (DESIGN-SYSTEM §9)."""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated, Optional

import typer

from core import config
from core.models import ScrapeQuery, SourceRunResult
from core.paths import DATA_DIR, ensure_data_dirs

app = typer.Typer(help="FindJob&Gig — scrape & manage job data.", no_args_is_help=True)

# Piped output on Windows uses the ANSI code page, which cannot print ✓/✗/…
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(errors="replace")


def _split(values: list[str] | None) -> list[str]:
    """Accept both `-s a -s b` and `-s a,b`."""
    return [v.strip() for item in values or [] for v in item.split(",") if v.strip()]


@app.command()
def info() -> None:
    """Show where data is stored."""
    ensure_data_dirs()
    typer.echo(f"data dir: {DATA_DIR}")


@app.command()
def sources() -> None:
    """List connectors, whether they are enabled, and their markets."""
    from scraper.sources import load_sources

    for name, s in load_sources().items():
        flag = "on " if s.enabled else "off"
        typer.echo(f"[{flag}] {name:12} {s.display_name:18} {s.category:4}  markets={','.join(s.markets)}")


@app.command()
def scrape(
    keyword: Annotated[Optional[list[str]], typer.Option("--keyword", "-k", help="Repeat or comma-separate.")] = None,
    type_: Annotated[Optional[list[str]], typer.Option("--type", "-t", help="fulltime, parttime, contract, freelance, internship, temporary")] = None,
    source: Annotated[Optional[list[str]], typer.Option("--source", "-s", help="Default: enabled sources for the region.")] = None,
    region: Annotated[str, typer.Option("--region", "-r", help="ALL, SEA, ID, EU, … (config/regions.yaml)")] = "ALL",
    location: Annotated[Optional[str], typer.Option(help="City/area passed to sources that support it.")] = None,
    category: Annotated[str, typer.Option(help="job | gig | any")] = "any",
    remote_only: Annotated[bool, typer.Option("--remote-only")] = False,
    since: Annotated[int, typer.Option(help="Only postings from the last N hours (0 = any).")] = 72,
    max_per_source: Annotated[int, typer.Option("--max", help="Max items per source per keyword.")] = 100,
    preset: Annotated[Optional[str], typer.Option(help="Preset from config/sources.yaml, e.g. creative.")] = None,
) -> None:
    """Scrape sources and store results in data/jobs/<source>.jsonl."""
    from scraper.runner import run_scrape

    ensure_data_dirs()
    fields: dict = {}
    if preset:
        presets = config.load("sources").get("presets", {})
        if preset not in presets:
            typer.echo(f"Unknown preset '{preset}'. Available: {', '.join(presets) or '-'}", err=True)
            raise typer.Exit(2)
        fields = {k: v for k, v in presets[preset].items() if k in ScrapeQuery.model_fields}

    keywords = _split(keyword) or fields.get("keywords", [])
    try:
        q = ScrapeQuery(
            keywords=keywords,
            types=_split(type_) or fields.get("types", []),
            category=category if category != "any" else fields.get("category", "any"),
            sources=_split(source) or fields.get("sources", []),
            region=region.upper() if region.upper() != "ALL" else fields.get("region", "ALL"),
            location=location or fields.get("location"),
            remote_only=remote_only or fields.get("remote_only", False),
            since_hours=since,
            max_per_source=max_per_source,
        )
    except ValueError as e:
        typer.echo(f"Invalid options: {e}", err=True)
        raise typer.Exit(2) from e

    def progress(name: str, r: SourceRunResult) -> None:
        if r.status == "running":
            typer.echo(f"  … {name}")
        elif r.status == "done":
            note = f"  ({r.error})" if r.error else ""
            typer.echo(f"  ✓ {name:12} fetched={r.fetched} new={r.new} updated={r.updated} skipped={r.skipped} {r.ms}ms{note}")
        else:
            typer.echo(f"  ✗ {name:12} {r.error}  {r.ms}ms")

    typer.echo(f"Scraping keywords={q.keywords or ['*']} region={q.region} since={f'{q.since_hours}h' if q.since_hours else 'any'}")
    try:
        run = asyncio.run(run_scrape(q, trigger="cli", progress=progress))
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from e
    typer.echo(f"Run {run.id}: {run.status}")
    if run.status == "failed":
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
