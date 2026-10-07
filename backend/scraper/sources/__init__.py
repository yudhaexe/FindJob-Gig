"""Connector registry. Add a source: write `<name>.py`, import it here, add it to config/sources.yaml."""

from __future__ import annotations

from core import config
from scraper.base import Source
from scraper.sources.freelancer import Freelancer
from scraper.sources.hackernews import HackerNews
from scraper.sources.himalayas import Himalayas
from scraper.sources.jobstreet import JobStreet
from scraper.sources.reddit import Reddit

REGISTRY: dict[str, type[Source]] = {
    cls.name: cls for cls in (Freelancer, JobStreet, Himalayas, Reddit, HackerNews)
}


def load_sources() -> dict[str, Source]:
    """Every registered connector, configured from config/sources.yaml (enabled or not)."""
    settings = config.load("sources").get("sources", {})
    return {name: cls(settings.get(name, {"enabled": False})) for name, cls in REGISTRY.items()}
