"""`fjg` command line (DESIGN-SYSTEM §9)."""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated, Optional

import typer

from core import config
from core.models import Schedule, ScrapeQuery, SourceRunResult
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


@app.command()
def prune(
    days: Annotated[int, typer.Option("--days", "-d", min=1, help="Archive raw files and runs older than this")] = 90,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Only list what would move")] = False,
) -> None:
    """Move old raw day-files and run records to data/archive/ (jobs/ is never touched)."""
    from storage.filestore import FileStore

    moved = FileStore().prune(days, dry_run=dry_run)
    verb = "would archive" if dry_run else "archived"
    typer.echo(f"{verb} {len(moved['raw'])} raw files, {len(moved['runs'])} runs older than {days} days")


schedule_app = typer.Typer(help="Scheduled scrapes (data/state/schedules.json).", no_args_is_help=True)
app.add_typer(schedule_app, name="schedule")


@schedule_app.command("list")
def schedule_list() -> None:
    """Show schedules, their next run and failure state."""
    from storage.filestore import FileStore

    items = FileStore().load_schedules()
    for s in items:
        state = "on " if s.enabled else "off"
        nxt = f"{s.next_run_at:%Y-%m-%d %H:%M}Z" if s.next_run_at else "-"
        typer.echo(f"[{state}] {s.id}  {s.name:24} every {s.every:4} next {nxt}  last={s.last_status or '-'}"
                   + (f"  ({s.paused_reason})" if s.paused_reason else ""))
    if not items:
        typer.echo("No schedules.")


@schedule_app.command("add")
def schedule_add(
    name: Annotated[str, typer.Option("--name", "-n")],
    every: Annotated[str, typer.Option(help="30m, 1h, 6h, 12h, 1d …")] = "6h",
    keyword: Annotated[Optional[list[str]], typer.Option("--keyword", "-k")] = None,
    source: Annotated[Optional[list[str]], typer.Option("--source", "-s")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "ALL",
    category: Annotated[str, typer.Option()] = "any",
    preset: Annotated[Optional[str], typer.Option()] = None,
    since: Annotated[int, typer.Option()] = 72,
) -> None:
    """Add a schedule (same query options as `fjg scrape`)."""
    from datetime import datetime, timezone

    from scraper import scheduler
    from storage.filestore import FileStore

    fields: dict = {}
    if preset:
        presets = config.load("sources").get("presets", {})
        if preset not in presets:
            typer.echo(f"Unknown preset '{preset}'. Available: {', '.join(presets) or '-'}", err=True)
            raise typer.Exit(2)
        fields = {k: v for k, v in presets[preset].items() if k in ScrapeQuery.model_fields}
    try:
        delta = scheduler.parse_every(every)
        q = ScrapeQuery(**{
            **fields,
            "keywords": _split(keyword) or fields.get("keywords", []),
            "sources": _split(source) or fields.get("sources", []),
            "region": region.upper() if region.upper() != "ALL" else fields.get("region", "ALL"),
            "category": category if category != "any" else fields.get("category", "any"),
            "since_hours": since,
        })
    except ValueError as e:
        typer.echo(f"Invalid options: {e}", err=True)
        raise typer.Exit(2) from e
    now = datetime.now(timezone.utc)
    sched = Schedule(id=scheduler.new_schedule_id(), name=name, query=q, every=every.lower(),
                     created_at=now, next_run_at=now + delta)
    FileStore().update_schedules(lambda items: items.append(sched))
    typer.echo(f"Added {sched.id} '{name}' every {sched.every}")


@schedule_app.command("run-due")
def schedule_run_due() -> None:
    """Run every schedule that is due. Safe to call often (Task Scheduler does, every 30 min)."""
    from scraper import scheduler
    from storage.filestore import FileStore

    ensure_data_dirs()
    runs = asyncio.run(scheduler.run_due(FileStore()))
    for r in runs:
        typer.echo(f"{r.schedule_id}: run {r.id} {r.status}")
    if not runs:
        typer.echo("Nothing due.")


@schedule_app.command("status")
def schedule_status() -> None:
    """Report whether the Windows Task Scheduler entry from scripts/register-task.ps1 exists."""
    import subprocess

    if sys.platform != "win32":
        typer.echo("not-supported")
        return
    r = subprocess.run(["schtasks", "/Query", "/TN", "FindJobGig"], capture_output=True, text=True)
    typer.echo("registered" if r.returncode == 0 else "not-registered")


if __name__ == "__main__":
    app()
