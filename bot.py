"""Discord bot — @mention with a club name, get today's free tennis slots."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date
from itertools import groupby

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

MIN_MATCH_SCORE = 55  # below this, treat as "no match"


def _strip_mentions(content: str, bot_id: int) -> str:
    """Remove the bot mention(s) from the message text."""
    cleaned = re.sub(rf"<@!?{bot_id}>", "", content)
    return cleaned.strip().strip("?!.,").strip()


def _format_reply(facility: matchi.Facility, slots: list[matchi.Slot]) -> str:
    on = date.today().isoformat()
    if not slots:
        return (
            f"**{facility.name}** ({facility.city}) — {on}\n"
            f"No free tennis slots today.\n<{facility.url}>"
        )

    lines = [f"**{facility.name}** ({facility.city}) — free tennis slots {on}:"]
    # Group by court for a compact summary
    by_court = sorted(slots, key=lambda s: (s.court, s.start))
    for court, group in groupby(by_court, key=lambda s: s.court):
        times = ", ".join(f"{s.start}-{s.end}" for s in group)
        lines.append(f"• **{court}**: {times}")
    lines.append(f"<{facility.url}>")
    return "\n".join(lines)


async def _handle_query(query: str) -> str:
    """Run the (blocking) scraper in a thread and format the reply."""
    if not query:
        return "Mention me with a club name, e.g. `@bot Högsbohöjds TK`"

    matches = await asyncio.to_thread(matchi.find_facility, query, 3)
    if not matches or matches[0][1] < MIN_MATCH_SCORE:
        suggest = ""
        if matches:
            suggest = "\nDid you mean: " + ", ".join(
                f"_{f.name}_ ({f.city})" for f, _ in matches
            )
        return f"Couldn't find a club matching `{query}`.{suggest}"

    facility, score = matches[0]
    log.info("query=%r → %s (score=%d)", query, facility.name, score)

    slots = await asyncio.to_thread(matchi.get_tennis_slots, facility.id, date.today())
    return _format_reply(facility, slots)


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
