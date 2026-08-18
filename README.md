# Telegram Movie Bot — Python + MongoDB (simple edition)

Same idea as a full Go/Postgres/Redis version, rebuilt for minimum setup
friction: **fill in a handful of env vars and run one command.** No
migrations, no connection-pool tuning, no Redis. MongoDB's schemaless
documents mean "add a field to a movie" is just a new dict key.

> ⚠️ **Scope**: for distributing movies/videos you own, have licensed, or
> are otherwise authorized to redistribute. No scraping, no piracy-source
> integration, no DRM bypass.

## Why this is simpler than the Go version

| | Go version | This version |
|---|---|---|
| Database | PostgreSQL + migrations | MongoDB, indexes auto-created on boot |
| Caching/rate-limit | Redis | In-process Python dicts |
| Setup steps | .env + `docker compose up` + wait for migrations | .env + `python bot.py` |
| Moving parts to run | bot + Postgres + Redis | bot + MongoDB (or just Atlas, zero local infra) |

The trade-off: this runs as a single process with in-memory state, so it's
not meant to be horizontally scaled across multiple replicas. For one bot
serving one channel, that's not a real limitation — Telegram only allows a
single long-polling consumer per bot token anyway.

## Quick start (fastest path)

```bash
pip install -r requirements.txt
cp .env.example .env
```

Now edit `.env` — you only need to fill in:
1. `BOT_TOKEN` (from @BotFather)
2. `CHANNEL_ID` and `CHANNEL_USERNAME` (your mandatory channel)
3. `SEED_ADMIN_IDS` (your Telegram user ID)
4. `MONGO_URI` (see options below)

Then:

```bash
python bot.py
```

That's it — no build step, no migrations. On boot it logs `MongoDB indexes
ensured`, `N active admin(s) ready`, and `Authorized as @yourbot`.

### MongoDB options (pick one)

- **Local, zero-install-friction**: `docker compose up -d mongo` starts just
  MongoDB (`MONGO_URI=mongodb://localhost:27017` already matches this).
- **Everything in Docker**: `docker compose up -d --build` runs MongoDB
  *and* the bot together.
- **No local infra at all**: create a free [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register)
  cluster, copy its connection string into `MONGO_URI` in `.env`, run
  `python bot.py` directly. This is the lowest-friction option if you don't
  want Docker or a local database at all.

## 1. Create the bot with BotFather

Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow the
prompts → copy the token it gives you into `BOT_TOKEN`.

## 2. Set up the mandatory channel

1. Create a Telegram channel, add your bot as **administrator**.
2. Get its numeric ID (forward a message from it to
   [@userinfobot](https://t.me/userinfobot), or use
   [@RawDataBot](https://t.me/RawDataBot) temporarily) — looks like
   `-1001234567890`. Put it in `CHANNEL_ID`.
3. If public, put the username (no `@`) in `CHANNEL_USERNAME`.

## 3. Get your Telegram user ID

Message [@userinfobot](https://t.me/userinfobot) → put your ID in
`SEED_ADMIN_IDS` (comma-separated for multiple).

## 4. Run it

```bash
python bot.py
```

or, with Docker doing everything:

```bash
docker compose up -d --build
docker compose logs -f bot
```

## 5. Configure the channel from inside the bot (super-admin only)

```
/setchannel -1001234567890 @your_channel_username
```

For a private channel, pass an invite link instead of `@username`.

## 6. Add your first movie

Send the video file itself, with this as the caption:

```
/addmovie 1025|The Movie Title|2024|Action|A short description here.
```

The `file_id` is captured automatically — the file is never re-uploaded
for future deliveries.

## 7. Test it

- `/start` from an account not in the channel → Join/Verify prompt.
- Join, tap Verify → confirmation, then send `1025` → movie delivered.
- Deep link: `https://t.me/YOUR_BOT_USERNAME?start=1025` → same flow,
  auto-delivers movie `#1025` right after verification.

## Commands

| Command | Access | Description |
|---|---|---|
| `/start [payload]` | everyone | welcome + subscription gate + deep-link auto-delivery |
| `/help` | everyone | usage help |
| `/movie <number>` | everyone (post-verification) | fetch by number |
| `/search <text>` | everyone (post-verification) | fuzzy title search, paginated |
| `/stats` | admin | user/movie/request statistics |
| `/addmovie <n>\|<title>\|<year>\|<genre>\|<desc>` (attach file) | admin | add a movie |
| `/editmovie <n> field=value;...` (optionally attach new file) | admin | edit a movie |
| `/deletemovie <n>` | admin | delete a movie |
| `/broadcast <text>` | admin | async broadcast to all users, rate-limited |
| `/users [page]` | admin | paginated user list |
| `/ban <id>` / `/unban <id>` | admin | restrict/restore a user |
| `/setchannel <chat_id> [@username\|invite_link]` | super_admin | set mandatory channel |
| `/addadmin <telegram_id>` | super_admin | promote a user to admin |

## What's simplified vs. the Go version (and how to add it back)

- **No Redis** — `ratelimit.py` uses in-memory dicts for rate limiting,
  duplicate-request suppression, and subscription/movie caching. Swap in
  `redis.asyncio` with the same function signatures if you ever need
  multi-instance deployment.
- **No structured JSON logging / metrics endpoint** — `logging.basicConfig`
  is enough for a single-VPS deployment; add `python-json-logger` and a
  `/healthz` aiohttp route if you wire this into an orchestrator.
- **No formal test suite** — the logic is intentionally thin per-function
  (`parse_movie_number`, `is_subscribed`, etc.) so it's straightforward to
  unit test with `pytest` + `pytest-asyncio` and `mongomock`/`mongomock-motor`
  if you want that later; not included here to keep the file count minimal.
- **No admin REST API** — everything is bot-native; add a small `aiohttp`
  or `FastAPI` app importing the same `database.py` functions if you want
  a dashboard.

## Deploying to a VPS

```bash
curl -fsSL https://get.docker.com | sh
git clone <your-repo> && cd telegram-movie-bot-python
cp .env.example .env   # fill in real values, chmod 600 .env
docker compose up -d --build
```

No inbound ports or HTTPS needed — the bot uses outbound long-polling only.
