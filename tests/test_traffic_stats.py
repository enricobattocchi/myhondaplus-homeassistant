"""Tests for the traffic-stats snapshot script in .github/scripts/."""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "traffic.py"


@pytest.fixture
def traffic_module(monkeypatch):
    """Import .github/scripts/traffic.py with required env vars stubbed."""
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("TRAFFIC_TOKEN", "fake-token")
    spec = importlib.util.spec_from_file_location("traffic_stats", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["traffic_stats"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("traffic_stats", None)


class TestMerge:
    def test_creates_new_csv_from_empty(self, tmp_path, traffic_module):
        out = tmp_path / "clones.csv"
        traffic_module.merge(out, [
            {"timestamp": "2026-04-25T00:00:00Z", "count": 10, "uniques": 5},
        ])
        rows = list(csv.DictReader(out.open()))
        assert rows == [{"date": "2026-04-25", "count": "10", "uniques": "5"}]

    def test_appends_new_dates(self, tmp_path, traffic_module):
        out = tmp_path / "clones.csv"
        out.write_text("date,count,uniques\n2026-04-23,178,42\n")
        traffic_module.merge(out, [
            {"timestamp": "2026-04-24T00:00:00Z", "count": 120, "uniques": 48},
        ])
        rows = list(csv.DictReader(out.open()))
        assert [r["date"] for r in rows] == ["2026-04-23", "2026-04-24"]

    def test_overwrites_existing_date_with_new_value(self, tmp_path, traffic_module):
        # GitHub re-reports the last 14 days each call — the freshest value wins.
        out = tmp_path / "clones.csv"
        out.write_text("date,count,uniques\n2026-04-24,99,40\n")
        traffic_module.merge(out, [
            {"timestamp": "2026-04-24T00:00:00Z", "count": 120, "uniques": 48},
        ])
        rows = list(csv.DictReader(out.open()))
        assert rows == [{"date": "2026-04-24", "count": "120", "uniques": "48"}]

    def test_preserves_dates_outside_new_window(self, tmp_path, traffic_module):
        # Old dates (>14 days) won't appear in fresh API responses; merge must keep them.
        out = tmp_path / "clones.csv"
        out.write_text(
            "date,count,uniques\n"
            "2026-03-01,5,2\n"
            "2026-04-23,178,42\n"
        )
        traffic_module.merge(out, [
            {"timestamp": "2026-04-25T00:00:00Z", "count": 200, "uniques": 50},
        ])
        rows = list(csv.DictReader(out.open()))
        assert [r["date"] for r in rows] == ["2026-03-01", "2026-04-23", "2026-04-25"]

    def test_creates_parent_dir(self, tmp_path, traffic_module):
        out = tmp_path / "stats" / "clones.csv"
        traffic_module.merge(out, [
            {"timestamp": "2026-04-25T00:00:00Z", "count": 1, "uniques": 1},
        ])
        assert out.exists()


class TestPlot:
    def setup_method(self):
        pytest.importorskip("matplotlib")

    def test_writes_png(self, tmp_path, traffic_module):
        csv_path = tmp_path / "clones.csv"
        csv_path.write_text(
            "date,count,uniques\n"
            "2026-04-23,178,42\n"
            "2026-04-24,120,48\n"
            "2026-04-25,200,50\n"
        )
        png_path = tmp_path / "clones.png"
        traffic_module.plot(csv_path, png_path, "Clones")
        assert png_path.exists()
        # Sanity-check the PNG header magic bytes.
        assert png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


class TestMain:
    def setup_method(self):
        pytest.importorskip("matplotlib")

    def test_runs_end_to_end_with_stubbed_fetch(self, tmp_path, monkeypatch, traffic_module):
        sample_clones = {
            "count": 200, "uniques": 50,
            "clones": [
                {"timestamp": "2026-04-25T00:00:00Z", "count": 200, "uniques": 50},
            ],
        }
        sample_views = {
            "count": 75, "uniques": 30,
            "views": [
                {"timestamp": "2026-04-25T00:00:00Z", "count": 75, "uniques": 30},
            ],
        }
        monkeypatch.setattr(
            traffic_module,
            "fetch",
            lambda endpoint: sample_clones if endpoint == "clones" else sample_views,
        )
        monkeypatch.chdir(tmp_path)
        rc = traffic_module.main()
        assert rc == 0
        assert (tmp_path / "stats" / "clones.csv").exists()
        assert (tmp_path / "stats" / "views.csv").exists()
        assert (tmp_path / "stats" / "clones.png").exists()
        assert (tmp_path / "stats" / "views.png").exists()
