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


def test_fmt_date():
    dt = datetime(2026, 8, 14, 11, 0, tzinfo=timezone.utc)
    assert bot.fmt_month_day(dt) == "14 Agu"
    assert bot.fmt_weekday(dt) == "Jumat"
    assert bot.fmt_month_day(None) == "-"
    assert bot.fmt_weekday(None) == "-"


def test_progress_pct_upcoming_imminence():
    ev = bot.parse_event(make_event(start=(NOW + timedelta(days=bot.DAYS_AHEAD)).isoformat()))
    assert bot.progress_pct(ev, NOW, mode="upcoming") == 0
    ev_mid = bot.parse_event(make_event(start=(NOW + timedelta(days=bot.DAYS_AHEAD / 2)).isoformat()))
    assert bot.progress_pct(ev_mid, NOW, mode="upcoming") == 50


def test_progress_pct_ongoing_elapsed():
    ev = bot.parse_event(
        make_event(
            start=(NOW - timedelta(hours=3)).isoformat(),
            finish=(NOW + timedelta(hours=3)).isoformat(),
        )
    )
    assert bot.progress_pct(ev, NOW, mode="ongoing") == 50
    ev_start = bot.parse_event(
        make_event(
            start=NOW.isoformat(),
            finish=(NOW + timedelta(hours=6)).isoformat(),
        )
    )
    assert bot.progress_pct(ev_start, NOW, mode="ongoing") == 0


def test_progress_pct_ongoing_finished_clamped():
    ev = bot.parse_event(
        make_event(
            start=(NOW - timedelta(hours=6)).isoformat(),
            finish=(NOW - timedelta(hours=1)).isoformat(),
        )
    )
    assert bot.progress_pct(ev, NOW, mode="ongoing") == 100


def test_bar_color():
    soon = bot.parse_event(make_event(start=(NOW + timedelta(hours=2)).isoformat()))
    assert bot.bar_color(soon, NOW, mode="upcoming") == "d73a49"
    far = bot.parse_event(make_event(start=(NOW + timedelta(days=5)).isoformat()))
    assert bot.bar_color(far, NOW, mode="upcoming") == "58a6ff"
    running = bot.parse_event(
        make_event(
            start=(NOW - timedelta(hours=1)).isoformat(),
            finish=(NOW + timedelta(hours=2)).isoformat(),
        )
    )
    assert bot.bar_color(running, NOW, mode="ongoing") == "3fb950"


def test_progress_bar():
    bar50 = "██████████░░░░░░░░░░ 50%"
    bar100 = "████████████████████ 100%"
    bar0 = "░░░░░░░░░░░░░░░░░░░░ 0%"
    bar83 = "█████████████████░░░ 83%"
    assert bot.progress_bar(50, "58a6ff") == bar50
    assert bot.progress_bar(100, "3fb950") == bar100
    assert bot.progress_bar(-5, "3fb950") == bar0
    assert bot.progress_bar(83, "58a6ff") == bar83


def test_meta_line():
    ev = bot.parse_event(
        make_event(
            id=1,
            name="Test CTF",
            start="2026-08-14T11:00:00+00:00",
            finish="2026-08-14T20:00:00+00:00",
            duration={"days": 0, "hours": 9},
            format="Jeopardy",
            weight=33.891,
        )
    )
    assert bot.meta_line(ev) == "Jumat, 14 Agu · 18:00–03:00 WIB · 9h · Jeopardy · Rating 33.89"


def test_render_timeline_upcoming():
    ev = bot.parse_event(
        make_event(
            id=1,
            name="Test CTF",
            url="https://ctftime.org/event/1",
            start="2026-08-14T11:00:00+00:00",
            finish="2026-08-14T20:00:00+00:00",
        )
    )
    line = bot.render_timeline([ev], NOW, mode="upcoming")
    assert line.startswith("| Jadwal | Event |")
    assert "|--------|-------|" in line
    assert "| Jumat · 14 Agu |" in line
    assert '[Test CTF](https://ctftime.org/event/1)' in line
    assert '<br>' in line
    assert '█' in line
    assert '%' in line


def test_render_timeline_ongoing_no_bar():
    ev = bot.parse_event(
        make_event(
            id=1,
            name="Test CTF",
            start="2026-08-12T00:00:00+00:00",
            finish="2026-08-12T09:00:00+00:00",
        )
    )
    line = bot.render_timeline([ev], NOW, mode="ongoing")
    assert "█" not in line
    assert "🏃" in line


def test_render_past_timeline():
    ev = bot.parse_event(
        make_event(
            id=1,
            name="Test CTF",
            start="2026-08-08T09:00:00+00:00",
            finish="2026-08-08T18:00:00+00:00",
            format="Jeopardy",
        )
    )
    line = bot.render_past_timeline([ev])
    assert line.startswith("| Jadwal | Event |")
    assert "|--------|-------|" in line
    assert "✅" in line
    assert "<br>" in line
    assert "█" not in line
    assert "Jeopardy" in line


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
    assert "# CTF Event Tracker" in content
    assert "Workflow Status" in content
    assert "https://ctftime.org/event/1" in content
    assert "14 Agu" in content
    assert "Jumat" in content
    assert "18:00–03:00 WIB" in content
    assert "Rating Belum ada" in content
    assert "█" in content
    assert "%" in content
    assert "1 upcoming · 5 ditrack" in content
    assert "### Upcoming (Next 14 Days)" in content
    assert "#upcoming-next-14-days" in content
    assert "<details" in content


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
    assert "8 Agu" in content
    assert "<details>" in content


def test_render_no_past_section_when_empty():
    content = bot.render_readme([], [], 1, now=NOW)
    assert "### Sudah Berakhir" not in content


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
