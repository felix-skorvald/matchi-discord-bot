"""Scraper for matchi.se — finds tennis facilities and free time slots."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date as date_cls
from html import unescape

import requests
from rapidfuzz import fuzz, process

BASE = "https://www.matchi.se"
UA = "Mozilla/5.0 (compatible; book-tennis-bot/0.1)"
SPORT_TENNIS = 1

_session = requests.Session()
_session.headers.update({"User-Agent": UA})

_facility_cache: list[dict] = []
_facility_cache_ts: float = 0.0
_CACHE_TTL = 60 * 60 * 12  # 12h


@dataclass(frozen=True)
class Facility:
    id: int
    name: str
    shortname: str
    city: str

    @property
    def url(self) -> str:
        return f"{BASE}/facilities/{self.shortname}"


@dataclass(frozen=True)
class Slot:
    court: str
    start: str  # "HH:MM"
    end: str    # "HH:MM"
    indoor: bool


def _fetch_facilities() -> list[dict]:
    """Return raw facility dicts from matchi (cached)."""
    global _facility_cache, _facility_cache_ts
    if _facility_cache and (time.time() - _facility_cache_ts) < _CACHE_TTL:
        return _facility_cache

    # The endpoint ignores `q` and returns the full universe via restOfFacilities.
    r = _session.post(
        f"{BASE}/facilities/findFacilities",
        data={"asJson": "true", "q": "", "lat": "59.33", "lng": "18.07"},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    facilities = (data.get("facilities") or []) + (data.get("restOfFacilities") or [])

    _facility_cache = facilities
    _facility_cache_ts = time.time()
    return facilities


def find_facility(query: str, limit: int = 5) -> list[tuple[Facility, int]]:
    """Fuzzy-match a facility by name. Returns [(facility, score), ...] best first."""
    facilities = _fetch_facilities()
    if not facilities:
        return []

    # Build "Name (City)" haystack so cities help disambiguate.
    keys = [f"{f['name']} {f.get('city', '')}".strip() for f in facilities]
    matches = process.extract(
        query, keys, scorer=fuzz.WRatio, limit=limit
    )

    out: list[tuple[Facility, int]] = []
    for _, score, idx in matches:
        f = facilities[idx]
        out.append((
            Facility(
                id=int(f["id"]),
                name=f["name"],
                shortname=f["shortname"],
                city=f.get("city", "") or "",
            ),
            int(score),
        ))
    return out


_SLOT_RE = re.compile(
    r'<td[^>]*class="slot free"[^>]*'
    r'title="([^"]+)"',
    re.IGNORECASE | re.DOTALL,
)


def _parse_slots(html: str, indoor: bool) -> list[Slot]:
    slots: list[Slot] = []
    for m in _SLOT_RE.finditer(html):
        title = unescape(m.group(1))
        # title looks like: "Available<br>Bana 1<br> 10:00 - 11:00"
        parts = [p.strip() for p in re.split(r"<br\s*/?>", title) if p.strip()]
        # parts[0]=Available, parts[1]=court, parts[2]="HH:MM - HH:MM"
        if len(parts) < 3:
            continue
        court = parts[1]
        time_match = re.match(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", parts[2])
        if not time_match:
            continue
        slots.append(Slot(
            court=court,
            start=time_match.group(1),
            end=time_match.group(2),
            indoor=indoor,
        ))
    return slots


def _get_schedule_html(facility_id: int, on: date_cls, indoor: bool) -> str:
    r = _session.get(
        f"{BASE}/book/schedule",
        params={
            "wl": "",
            "facilityId": facility_id,
            "date": on.isoformat(),
            "sport": SPORT_TENNIS,
            "week": "",
            "year": "",
            "indoor": "true" if indoor else "false",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.text


def get_tennis_slots(facility_id: int, on: date_cls) -> list[Slot]:
    """Return free tennis slots (indoor + outdoor) for a given date."""
    all_slots: list[Slot] = []
    for indoor in (True, False):
        html = _get_schedule_html(facility_id, on, indoor)
        all_slots.extend(_parse_slots(html, indoor))

    # De-dup by (court, start, end) — same slot may appear under both tabs
    # if the facility only has one type.
    seen: set[tuple[str, str, str]] = set()
    unique: list[Slot] = []
    for s in all_slots:
        key = (s.court, s.start, s.end)
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    unique.sort(key=lambda s: (s.start, s.court))
    return unique
