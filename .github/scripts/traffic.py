"""Snapshot GitHub repo traffic to CSV + render PNG plots.

GitHub only retains the last 14 days of clone/view data. This script fetches
both endpoints, merges new dates into a long-running CSV (keyed by date,
keeping the latest count when an existing date is re-reported), and re-renders
the corresponding PNG plot so the README chart stays current.

Reads:
- env GITHUB_REPOSITORY (e.g. "owner/name")
- env TRAFFIC_TOKEN (fine-grained PAT with Administration: read on the repo)
"""

from __future__ import annotations

import csv
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["TRAFFIC_TOKEN"]
OUT = Path("stats")


def fetch(endpoint: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/traffic/{endpoint}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json
        return json.loads(resp.read())


def merge(path: Path, rows: list[dict]) -> None:
    """Merge rows into CSV, keyed by date (YYYY-MM-DD). New value wins."""
    by_date: dict[str, dict[str, str]] = {}
    if path.exists():
        with path.open() as f:
            for r in csv.DictReader(f):
                by_date[r["date"]] = r
    for r in rows:
        date = r["timestamp"][:10]
        by_date[date] = {
            "date": date,
            "count": str(r["count"]),
            "uniques": str(r["uniques"]),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "count", "uniques"])
        w.writeheader()
        for date in sorted(by_date):
            w.writerow(by_date[date])


def plot(csv_path: Path, png_path: Path, title: str) -> None:
    # Lazy import so the rest of the module (and its tests) don't require
    # matplotlib — only the plot step does, and the workflow installs it
    # explicitly before running.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    dates: list[datetime] = []
    counts: list[int] = []
    uniques: list[int] = []
    with csv_path.open() as f:
        for r in csv.DictReader(f):
            dates.append(datetime.fromisoformat(r["date"]))
            counts.append(int(r["count"]))
            uniques.append(int(r["uniques"]))
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(dates, counts, marker="o", markersize=3, label="Total", linewidth=1.2)
    ax.plot(dates, uniques, marker="o", markersize=3, label="Unique", linewidth=1.2)
    ax.set_title(f"{title} — {REPO}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Count")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(png_path, dpi=120)
    plt.close(fig)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for endpoint, title in (("clones", "Clones"), ("views", "Views")):
        try:
            data = fetch(endpoint)
        except urllib.error.HTTPError as e:
            print(f"::error::{endpoint} fetch failed: HTTP {e.code} {e.reason}", file=sys.stderr)
            return 1
        rows = data.get(endpoint, [])
        csv_path = OUT / f"{endpoint}.csv"
        png_path = OUT / f"{endpoint}.png"
        merge(csv_path, rows)
        plot(csv_path, png_path, title)
        print(f"{endpoint}: {len(rows)} new datapoints, total summary count={data.get('count')} uniques={data.get('uniques')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
