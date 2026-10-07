"""`fjg` command line. Commands are filled in from M1 onwards."""

import typer

from core.paths import DATA_DIR, ensure_data_dirs

app = typer.Typer(help="FindJob&Gig — scrape & manage job data.", no_args_is_help=True)


@app.command()
def info() -> None:
    """Show where data is stored."""
    ensure_data_dirs()
    typer.echo(f"data dir: {DATA_DIR}")


@app.command()
def scrape() -> None:
    """Scrape sources (coming in M1)."""
    typer.echo("Not implemented yet (M1).")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
