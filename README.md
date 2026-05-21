# book-tennis-bot

Discord bot — @mention it with a Swedish tennis club name and it replies with today's
free tennis slots from matchi.se.

```
@bot Högsbohöjds TK?
→ Högsbohöjds Tennisklubb (Göteborg) — free tennis slots 2026-05-21:
  • Bana 1: 10:00-11:00, 22:00-23:00
  • Bana 2: 10:00-11:00, 12:00-13:00, 13:00-14:00, ...
```

Typos are fine — fuzzy matching resolves `Höbsoböjds tk` → `Högsbohöjds Tennisklubb`.

## Setup

1. Create a Discord bot at https://discord.com/developers/applications, enable the
   **Message Content Intent**, and copy its token.
2. Invite it to your server with the `bot` scope and **Send Messages** + **Read Message
   History** permissions.
3. Install and run:

   ```
   pip install -r requirements.txt
   cp .env.example .env        # then paste your token
   python bot.py
   ```

## How it works

- `matchi.py` calls `POST /facilities/findFacilities` once (cached 12h), fuzzy-matches
  the user's input against the full facility list, then scrapes `GET /book/schedule`
  for sport=1 (tennis), both indoor and outdoor.
- `bot.py` listens for mentions, strips the mention, runs the scraper in a thread, and
  replies with slots grouped by court.

## Notes

- Only checks today. Extending to a date arg is straightforward — `get_tennis_slots`
  already takes a `date`.
- matchi.se has no official public API; this scrapes their internal endpoints. If they
  change the HTML/JSON shape, `matchi.py` will need updating.
