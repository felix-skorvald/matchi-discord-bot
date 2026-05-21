# matchi discord bot

Discord bot — @mention it with a Swedish tennis club name and it replies with free
tennis slots from matchi.se. Typos are fine; fuzzy matching resolves
`Höbsoböjds tk` → `Högsbohöjds Tennisklubb`.

## Usage

```
@bot Högsbohöjds TK
@bot Högsbohöjds TK imorgon
@bot Högsbohöjds TK tisdag efter 17
@bot Högsbohöjds TK, GLTK 2026-06-01 före 20
@bot Högsbohöjds TK och GLTK i övermorgon
```

Modifiers (any order, optional, Swedish or English):

| What            | Words it understands                                                       |
|-----------------|----------------------------------------------------------------------------|
| **Date**        | `idag`/`today`, `imorgon`/`tomorrow`, `i övermorgon`, weekday names (`tisdag`, `tuesday`, …), or an ISO date like `2026-06-01` |
| **Time filter** | `efter 17` / `after 17:30`, `före 20` / `before 20`                        |
| **Many clubs**  | Separate with `,` or `och`/`and`                                           |

Weekday names resolve to the **next occurrence including today** (so `tisdag` on a
Tuesday means today). Default date is today; default time filter is no filter.

## Setup

1. Create a Discord bot at https://discord.com/developers/applications, enable the
   **Message Content Intent**, and copy its token.
2. Invite it to your server. Easiest is to open this URL (replace the client_id with
   your Application ID):

   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&scope=bot&permissions=68608
   ```

3. Install and run:

   ```
   pip install -r requirements.txt
   cp .env.example .env        # then paste your token into .env
   python bot.py
   ```

## How it works

- `matchi.py` calls `POST /facilities/findFacilities` once (cached 12h), fuzzy-matches
  the user's input against the full facility list, then scrapes
  `GET /book/schedule?facilityId=…&sport=1` for both indoor and outdoor tennis.
- `bot.py` listens for mentions, parses date / time filter / club list out of the
  text, runs the scraper concurrently for each club, and replies with slots grouped
  by court.

## Notes

- matchi.se has no official public API; this scrapes their internal endpoints. If
  they change the HTML/JSON shape, `matchi.py` will need updating.
- Slots reflect what's free at the moment the scraper runs — there's no live push,
  so somebody could grab a slot a second after the bot replies.
