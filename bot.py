"""CTF Event Tracker - update otomatis jadwal CTF dari CTFtime ke README.md."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

Event = Dict[str, Any]

# --- KONFIGURASI (bisa di-override via environment variable) ---
DAYS_AHEAD: int = max(1, int(os.environ.get("DAYS_AHEAD", "14")))
PAST_DAYS: int = max(1, int(os.environ.get("PAST_DAYS", "7")))
LIMIT: int = min(100, max(1, int(os.environ.get("LIMIT", "50"))))
ARCHIVE_PATH: str = os.environ.get("ARCHIVE_PATH", "data/ctf_events.json")


def _local_tz() -> ZoneInfo:
    tz_name = os.environ.get("LOCAL_TZ", "Asia/Jakarta")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        print(f"Peringatan: timezone '{tz_name}' tidak dikenal, fallback ke Asia/Jakarta.")
        return ZoneInfo("Asia/Jakarta")


LOCAL_TZ: ZoneInfo = _local_tz()
LOCAL_TZ_NAME: str = LOCAL_TZ.key

API_URL = "https://ctftime.org/api/v1/events/"
USER_AGENT = "CTF-Tracker-Bot/3.0 (+https://github.com/Frigg1337/ctf-event-tracker)"
REPO = "Frigg1337/ctf-event-tracker"
REPO_URL = f"https://github.com/{REPO}"


def build_session() -> requests.Session:
    """Session dengan retry untuk mengatasi rate-limit/5xx dari CTFtime."""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def parse_dt(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_event(ev: Event) -> Event:
    """Normalisasi event dari API agar aman meski ada field yang hilang."""
    name = str(ev.get("title") or "Untitled").replace("|", "-").replace("[", "(").replace("]", ")")
    url = ev.get("url") or ev.get("ctftime_url") or ""

    duration = ev.get("duration") or {}
    dur_days = int(duration.get("days") or 0)
    dur_hours = int(duration.get("hours") or 0)
    dur_txt = f"{dur_days}d {dur_hours}h" if dur_days > 0 else f"{dur_hours}h"

    weight = ev.get("weight")
    weight_txt = "Belum ada" if weight is None or weight <= 0 else f"{weight:.2f}"

    return {
        "id": str(ev.get("id")),
        "name": name,
        "url": url,
        "start": parse_dt(ev.get("start")),
        "finish": parse_dt(ev.get("finish")),
        "start_iso": ev.get("start"),
        "finish_iso": ev.get("finish"),
        "duration": dur_txt,
        "format": ev.get("format") or "-",
        "weight_txt": weight_txt,
    }


def _fetch(params: Dict[str, int]) -> Optional[List[Event]]:
    try:
        response = build_session().get(API_URL, params=params, timeout=15)
        response.raise_for_status()
        return [parse_event(ev) for ev in response.json()]
    except requests.RequestException as e:
        print(f"Gagal mengambil data dari CTFtime: {e}")
        return None


def get_upcoming_ctfs() -> Optional[List[Event]]:
    """Ambil daftar CTF untuk DAYS_AHEAD hari ke depan."""
    now = datetime.now(timezone.utc)
    return _fetch(
        {
            "limit": LIMIT,
            "start": int(now.timestamp()),
            "finish": int((now + timedelta(days=DAYS_AHEAD)).timestamp()),
        }
    )


def get_past_ctfs() -> List[Event]:
    """Ambil event yang sudah berakhir dalam PAST_DAYS hari terakhir."""
    now = datetime.now(timezone.utc)
    result = _fetch(
        {
            "limit": LIMIT,
            "start": int((now - timedelta(days=PAST_DAYS)).timestamp()),
            "finish": int(now.timestamp()),
        }
    )
    return [e for e in (result or []) if e["finish"] and e["finish"] <= now]


def describe_time_left(now: datetime, start_dt: Optional[datetime]) -> str:
    if not start_dt:
        return "-"
    seconds = int((start_dt - now).total_seconds())
    if seconds <= 0:
        return "Dimulai"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    if days > 0:
        return f"{days} hari {hours} jam" if hours else f"{days} hari"
    return f"{hours} jam" if hours else "Sebentar lagi"


def fmt_utc(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


def fmt_local(dt: Optional[datetime]) -> str:
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M") if dt else "-"


MONTHS_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def fmt_month_day(dt: Optional[datetime]) -> str:
    if not dt:
        return "-"
    return f"{dt.day} {MONTHS_ID[dt.month - 1]}"


def fmt_weekday(dt: Optional[datetime]) -> str:
    if not dt:
        return "-"
    return DAYS_ID[dt.weekday()]


def progress_pct(event: Event, now: datetime, mode: str = "upcoming") -> int:
    start, finish = event.get("start"), event.get("finish")
    if not start:
        return 0
    if mode == "ongoing":
        if not finish or finish <= start:
            return 100
        elapsed = (now - start).total_seconds()
        total = (finish - start).total_seconds()
        pct = elapsed / total * 100
    else:
        window = DAYS_AHEAD * 86400
        remaining = (start - now).total_seconds()
        pct = (1 - remaining / window) * 100
    return max(0, min(100, int(pct)))


def bar_color(event: Event, now: datetime, mode: str = "upcoming") -> str:
    if mode == "ongoing":
        return "3fb950"
    pct = progress_pct(event, now, mode="upcoming")
    if pct >= 90:
        return "d73a49"
    if pct >= 50:
        return "58a6ff"
    return "3fb950"


def progress_bar(pct: int, color: str) -> str:
    clamped = max(0, min(100, pct))
    filled = round(clamped / 100 * 20)
    return f"{'█' * filled}{'░' * (20 - filled)} {clamped}%"


def meta_line(ev: Event) -> str:
    weekday = fmt_weekday(ev["start"])
    date = fmt_month_day(ev["start"])
    if ev["start"] and ev["finish"]:
        hours = (
            f"{ev['start'].astimezone(LOCAL_TZ).strftime('%H:%M')}–"
            f"{ev['finish'].astimezone(LOCAL_TZ).strftime('%H:%M')} WIB"
        )
    else:
        hours = fmt_local(ev["start"])
    parts = [f"{weekday}, {date} · {hours}"]
    if ev.get("duration"):
        parts.append(ev["duration"])
    if ev.get("format"):
        parts.append(ev["format"])
    if ev.get("weight_txt"):
        parts.append(f"Rating {ev['weight_txt']}")
    return " · ".join(parts)


def render_timeline(events: List[Event], now: datetime, mode: str = "upcoming") -> str:
    """Timeline list: tanggal di kiri, nama + meta + progress bar di kanan."""
    lines = ["| Jadwal | Event |", "|--------|-------|"]
    for ev in events:
        name = f"[{ev['name']}]({ev['url']})" if ev["url"] else ev["name"]
        left = f"{fmt_weekday(ev['start'])} · {fmt_month_day(ev['start'])}"
        if mode == "ongoing":
            right = f"🏃 **{name}**<br>{meta_line(ev)}"
        else:
            pct = progress_pct(ev, now, mode=mode)
            color = bar_color(ev, now, mode=mode)
            right = f"**{name}**<br>{meta_line(ev)}<br>{progress_bar(pct, color)}"
        lines.append(f"| {left} | {right} |")
    return "\n".join(lines)


def render_past_timeline(events: List[Event]) -> str:
    """Timeline list untuk event yang sudah berakhir (tanpa progress bar)."""
    lines = ["| Jadwal | Event |", "|--------|-------|"]
    for ev in events:
        name = f"[{ev['name']}]({ev['url']})" if ev["url"] else ev["name"]
        left = f"{fmt_weekday(ev['start'])} · {fmt_month_day(ev['start'])}"
        lines.append(f"| ✅ {left} | **{name}**<br>{meta_line(ev)} |")
    return "\n".join(lines)


def render_readme(
    events: List[Event],
    past_events: List[Event],
    total_tracked: int,
    now: Optional[datetime] = None,
) -> str:
    now = now or datetime.now(timezone.utc)

    upcoming = [e for e in events if e["start"] and e["start"] > now]
    ongoing = [
        e
        for e in events
        if e["start"] and e["finish"] and e["start"] <= now < e["finish"]
    ]

    content = "# CTF Event Tracker\n\n"
    content += (
        "Repository ini otomatis mengupdate jadwal CTF dari "
        "CTFtime setiap 2 jam.\n\n"
    )
    content += (
        f"[CTFtime](https://ctftime.org) · "
        f"[Repo]({REPO_URL}) · "
        f"[![Workflow Status](https://github.com/{REPO}/actions/workflows/update.yml/badge.svg)]"
        f"({REPO_URL}/actions/workflows/update.yml)\n\n"
    )
    content += (
        f"`{len(upcoming)} upcoming · {total_tracked} ditrack · "
        f"update terakhir {now.strftime('%Y-%m-%d %H:%M:%S')} UTC`\n\n"
    )
    content += (
        "[Berlangsung](#berlangsung) · "
        "[Upcoming](#upcoming-next-14-days) · "
        "[Sudah Berakhir](#sudah-berakhir-7-hari-terakhir)\n\n"
    )

    if ongoing:
        content += "### Berlangsung\n<details open><summary>Expand / Collapse</summary>\n\n"
        content += render_timeline(ongoing, now, "ongoing") + "\n</details>\n\n"

    content += "### Upcoming (Next 14 Days)\n<details open><summary>Expand / Collapse</summary>\n\n"
    if upcoming:
        content += render_timeline(upcoming, now, "upcoming") + "\n"
    else:
        content += "Tidak ada event ditemukan.\n"
    content += "</details>\n\n"

    if past_events:
        content += (
            f"### Sudah Berakhir ({PAST_DAYS} Hari Terakhir)\n"
            "<details><summary>Expand / Collapse</summary>\n\n"
        )
        content += render_past_timeline(past_events) + "\n</details>\n\n"

    content += (
        f"\n---\n*Last updated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC — "
        f"dihasilkan otomatis oleh [ctf-event-tracker]({REPO_URL})*\n"
    )
    return content


def load_archive(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def update_archive(events: List[Event], path: str, now: datetime) -> Dict[str, Any]:
    """Simpan riwayat event (dedup by id) ke data/ctf_events.json."""
    archive = load_archive(path)
    now_iso = now.isoformat(timespec="seconds")
    for ev in events:
        entry = archive.get(ev["id"], {})
        entry.update(
            {
                "id": ev["id"],
                "title": ev["name"],
                "url": ev["url"],
                "start": ev["start_iso"],
                "finish": ev["finish_iso"],
                "format": ev["format"],
                "weight": ev["weight_txt"],
                "last_seen": now_iso,
            }
        )
        entry.setdefault("first_seen", now_iso)
        archive[ev["id"]] = entry

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
    return archive


def update_readme(
    events: List[Event],
    past_events: List[Event],
    archive: Dict[str, Any],
    now: Optional[datetime] = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    content = render_readme(events, past_events, len(archive), now)
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(content)


def main() -> int:
    print("Memulai tracking...")
    now = datetime.now(timezone.utc)
    events = get_upcoming_ctfs()
    if events is None:
        # Exit 0 agar workflow tetap membuat commit kosong (streak aman).
        print("API gagal. README.md dipertahankan, tetap lanjut agar push/streak berjalan.")
        return 0
    past_events = get_past_ctfs()
    archive = update_archive(events + past_events, ARCHIVE_PATH, now)
    update_readme(events, past_events, archive, now)
    print(
        f"Selesai! README.md diupdate "
        f"({len(events)} upcoming, {len(past_events)} lampau, {len(archive)} total di-track)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
