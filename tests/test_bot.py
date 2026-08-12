import os
import sys
from datetime import datetime, timedelta, timezone

os.environ.setdefault("LOCAL_TZ", "Asia/Jakarta")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bot


def make_event(**overrides):
    ev = {
        "id": 1,
        "title": "Test CTF",
        "url": "https://ctftime.org/event/1",
        "start": "2026-08-14T11:00:00+00:00",
        "finish": "2026-08-14T20:00:00+00:00",
        "duration": {"days": 0, "hours": 9},
        "format": "Jeopardy",
        "weight": 0.0,
    }
    ev.update(overrides)
    return ev


NOW = datetime(2026, 8, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_event_basic():
    e = bot.parse_event(make_event())
    assert e["name"] == "Test CTF"
    assert e["url"] == "https://ctftime.org/event/1"
    assert e["duration"] == "9h"
    assert e["format"] == "Jeopardy"
    assert e["weight_txt"] == "Belum ada"


def test_parse_event_missing_fields():
    e = bot.parse_event({"id": 2})
    assert e["name"] == "Untitled"
    assert e["duration"] == "0h"
    assert e["format"] == "-"
    assert e["weight_txt"] == "Belum ada"
    assert e["start"] is None


def test_name_escaping():
    e = bot.parse_event(make_event(title="A|B [C]"))
    assert "|" not in e["name"]
    assert "[" not in e["name"]
    assert "]" not in e["name"]


def test_weight_display():
    e = bot.parse_event(make_event(weight=33.891))
    assert e["weight_txt"] == "33.89"


def test_time_left_days():
    start = NOW + timedelta(days=2, hours=3)
    assert bot.describe_time_left(NOW, start) == "2 hari 3 jam"


def test_time_left_hours():
    start = NOW + timedelta(hours=5)
    assert bot.describe_time_left(NOW, start) == "5 jam"


def test_time_left_started():
    start = NOW - timedelta(hours=1)
    assert bot.describe_time_left(NOW, start) == "Dimulai"


def test_render_upcoming_columns():
    events = [bot.parse_event(make_event())]
    content = bot.render_readme(events, [], 5, now=NOW)
    assert "Upcoming Events" in content
    assert "https://ctftime.org/event/1" in content
    assert "Berakhir (UTC)" in content
    assert "2026-08-14 20:00" in content  # kolom Berakhir (UTC)
    assert "2026-08-14 18:00" in content  # kolom lokal = UTC+7
    assert "Mulai (Asia/Jakarta)" in content
    assert "Total Ditrack" in content
    assert "Workflow Status" in content


def test_render_empty_events():
    content = bot.render_readme([], [], 0, now=NOW)
    assert "Tidak ada event ditemukan" in content


def test_render_past_section():
    past = bot.parse_event(
        make_event(
            id=99,
            start="2026-08-08T09:00:00+00:00",
            finish="2026-08-08T18:00:00+00:00",
        )
    )
    content = bot.render_readme([], [past], 1, now=NOW)
    assert "Sudah Berakhir" in content
    assert "2026-08-08" in content


def test_render_no_past_section_when_empty():
    content = bot.render_readme([], [], 1, now=NOW)
    assert "Sudah Berakhir" not in content


def test_archive_merge_by_id(tmp_path):
    path = str(tmp_path / "nested" / "archive.json")

    events1 = [bot.parse_event(make_event())]
    a1 = bot.update_archive(events1, path, NOW)
    assert len(a1) == 1

    events2 = [bot.parse_event(make_event(id=2, title="Test CTF 2"))]
    a2 = bot.update_archive(events2, path, NOW)
    assert len(a2) == 2

    events3 = [bot.parse_event(make_event(id=1, title="Test CTF 3"))]
    a3 = bot.update_archive(events3, path, NOW)
    assert len(a3) == 2  # id sama -> update, bukan duplikat

    assert a3["1"]["first_seen"] == NOW.isoformat(timespec="seconds")
    assert a3["1"]["title"] == "Test CTF 3"
