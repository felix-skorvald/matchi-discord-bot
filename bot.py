"""Discord bot — @mention with a club name, get free tennis slots from matchi.se."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date, timedelta
from itertools import groupby
from typing import Callable

import discord
from dotenv import load_dotenv

import matchi

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tennis-bot")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

MIN_MATCH_SCORE = 55

WEEKDAYS = {
    "måndag": 0, "mandag": 0, "monday": 0,
    "tisdag": 1, "tuesday": 1,
    "onsdag": 2, "wednesday": 2,
    "torsdag": 3, "thursday": 3,
    "fredag": 4, "friday": 4,
    "lördag": 5, "lordag": 5, "saturday": 5,
    "söndag": 6, "sondag": 6, "sunday": 6,
}

SlotFilter = Callable[[matchi.Slot], bool]


def _strip_mentions(content: str, bot_id: int) -> str:
    return re.sub(rf"<@!?{bot_id}>", "", content).strip().strip("?!.,").strip()


def _parse_time_filter(text: str) -> tuple[str, SlotFilter]:
    """Pull 'efter HH[:MM]' / 'före HH[:MM]' out of text, return (rest, predicate)."""
    predicates: list[SlotFilter] = []

    def consume(pattern: str, builder):
        nonlocal text
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return
        h = int(m.group("h"))
        mm = int(m.group("m") or 0)
        threshold = f"{h:02d}:{mm:02d}"
        predicates.append(builder(threshold))
        text = (text[: m.start()] + text[m.end():]).strip()

    consume(
        r"\b(?:efter|after)\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\b",
        lambda t: lambda s: s.start >= t,
    )
    consume(
        r"\b(?:före|fore|innan|before)\s+(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\b",
        lambda t: lambda s: s.start < t,
    )

    if not predicates:
        return text, lambda s: True
    return text, lambda s: all(p(s) for p in predicates)


def _parse_date(text: str) -> tuple[str, date]:
    """Pull a date hint out of text. Returns (rest, date). Defaults to today."""
    today = date.today()

    m = re.search(r"\bi\s+övermorgon\b|\bi\s+overmorgon\b", text, re.IGNORECASE)
    if m:
        return (text[: m.start()] + text[m.end():]).strip(), today + timedelta(days=2)

    m = re.search(r"\b(?:imorgon|i\s+morgon|tomorrow)\b", text, re.IGNORECASE)
    if m:
        return (text[: m.start()] + text[m.end():]).strip(), today + timedelta(days=1)

    m = re.search(r"\b(?:idag|i\s+dag|today)\b", text, re.IGNORECASE)
    if m:
        return (text[: m.start()] + text[m.end():]).strip(), today

    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if m:
        try:
            return (text[: m.start()] + text[m.end():]).strip(), date.fromisoformat(m.group(1))
        except ValueError:
            pass

    m = re.search(r"\b(" + "|".join(WEEKDAYS) + r")\b", text, re.IGNORECASE)
    if m:
        target = WEEKDAYS[m.group(1).lower()]
        diff = (target - today.weekday()) % 7  # 0 = today
        return (text[: m.start()] + text[m.end():]).strip(), today + timedelta(days=diff)

    return text, today


def _parse_query(text: str) -> tuple[list[str], date, SlotFilter]:
    text, time_filter = _parse_time_filter(text)
    text, on = _parse_date(text)
    # Collapse leftover whitespace and split clubs on commas / "och" / "and"
    text = re.sub(r"\s+", " ", text).strip(" ,")
    clubs = [c.strip() for c in re.split(r"\s*,\s*|\s+och\s+|\s+and\s+", text) if c.strip()]
    return clubs, on, time_filter


def _format_block(facility: matchi.Facility, on: date, slots: list[matchi.Slot]) -> str:
    header = f"**{facility.name}** ({facility.city}) — {on.isoformat()}"
    if not slots:
        return f"{header}\nNo free tennis slots.\n<{facility.url}>"

    lines = [header + ":"]
    by_court = sorted(slots, key=lambda s: (s.court, s.start))
    for court, group in groupby(by_court, key=lambda s: s.court):
        times = ", ".join(f"{s.start}-{s.end}" for s in group)
        lines.append(f"• **{court}**: {times}")
    lines.append(f"<{facility.url}>")
    return "\n".join(lines)


async def _lookup_one(query: str, on: date, time_filter: SlotFilter) -> str:
    matches = await asyncio.to_thread(matchi.find_facility, query, 3)
    if not matches or matches[0][1] < MIN_MATCH_SCORE:
        suggest = ""
        if matches:
            suggest = "\nDid you mean: " + ", ".join(
                f"_{f.name}_ ({f.city})" for f, _ in matches
            )
        return f"Couldn't find a club matching `{query}`.{suggest}"

    facility, score = matches[0]
    log.info("query=%r on=%s → %s (score=%d)", query, on, facility.name, score)

    slots = await asyncio.to_thread(matchi.get_tennis_slots, facility.id, on)
    slots = [s for s in slots if time_filter(s)]
    return _format_block(facility, on, slots)


async def _handle_query(raw: str) -> str:
    if not raw:
        return (
            "Mention me with a club name, e.g. `@bot Högsbohöjds TK`.\n"
            "Also supports: `imorgon`, `tisdag`, `2026-06-01`, "
            "`efter 17`, `före 20`, and `, ` to list multiple clubs."
        )

    clubs, on, time_filter = _parse_query(raw)
    if not clubs:
        return "I parsed your filters but didn't see a club name."

    blocks = await asyncio.gather(*(_lookup_one(c, on, time_filter) for c in clubs))
    return "\n\n".join(blocks)


@client.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", client.user, client.user.id)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if client.user not in message.mentions:
        return

    query = _strip_mentions(message.content, client.user.id)
    async with message.channel.typing():
        try:
            reply = await _handle_query(query)
        except Exception:
            log.exception("query failed")
            reply = "Something went wrong talking to matchi.se. Try again in a bit."

    await message.reply(reply, mention_author=False)


if __name__ == "__main__":
    client.run(TOKEN)
