# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Marzban is a proxy management panel built on top of [Xray-core](https://github.com/XTLS/Xray-core). It exposes a FastAPI REST backend, a React/Vite dashboard, a Telegram bot, and a CLI. Users get subscription links (V2ray, Clash, SingBox) that point at Xray inbounds managed by the panel.

## Running the app

```bash
# copy and edit config
cp .env.example .env

# run DB migrations
alembic upgrade head

# start the server (runs on http://localhost:8000)
python3 main.py
```

The dashboard is served at `/dashboard/`. Enable Swagger docs by setting `DOCS=True` in `.env`, then visit `/docs`.

## Dashboard (frontend)

```bash
cd app/dashboard
npm install
npm run dev        # dev server on :3000, proxies API to :8000
npm run build      # outputs to app/dashboard/build/
```

The built assets are committed to `app/dashboard/build/` and served statically by FastAPI — you only need to rebuild when changing frontend code.

## Database migrations

```bash
# create a new migration after changing app/db/models.py
alembic revision --autogenerate -m "describe change"

# apply
alembic upgrade head

# downgrade one step
alembic downgrade -1
```

Supports SQLite (default, `sqlite:///db.sqlite3`) and MySQL/MariaDB via `SQLALCHEMY_DATABASE_URL`.

## Architecture

### Backend layers

```
main.py                  → uvicorn entrypoint
app/__init__.py          → FastAPI app, APScheduler, CORS, router registration
app/routers/             → HTTP route handlers (user, admin, node, subscription, core, system, home, user_template)
app/models/              → Pydantic request/response schemas
app/db/models.py         → SQLAlchemy ORM models
app/db/crud.py           → all DB read/write operations
app/db/base.py           → engine + SessionLocal
app/jobs/                → APScheduler background jobs (auto-loaded by __init__.py glob)
app/subscription/        → subscription format generators (V2ray links, Clash YAML, SingBox, Outline)
app/telegram/            → Telegram bot handlers
app/discord/             → Discord webhook report handlers
app/utils/               → JWT helpers, reporting, system utilities
xray/                    → Xray-core process management, config generation, node API wrappers
config.py                → all env-var config with defaults
```

### Key data flow

- **User lifecycle**: `app/routers/user.py` → `app/db/crud.py` → `xray/operations.py` (adds/removes user from running Xray core via gRPC API)
- **Subscription**: `GET /{sub_path}/{token}` → `app/routers/subscription.py` → `app/subscription/share.py` generates links from user's proxies + inbounds
- **Background jobs**: `app/jobs/` files are glob-imported at startup; each registers itself with the APScheduler instance from `app/__init__.py`. Job `0_xray_core.py` runs first (filename ordering) and starts the Xray process.
- **Nodes**: Remote Xray nodes connect via `xray_api` (gRPC). Node health and user sync are managed in `app/jobs/0_xray_core.py` and `xray/operations.py`.

### DB session pattern

Use `GetDB` as a context manager in jobs/background code, and `get_db` as a FastAPI dependency in routers:

```python
# in a job
with GetDB() as db:
    users = get_users(db, status=UserStatus.active)

# in a router
def my_route(db: Session = Depends(get_db)):
    ...
```

### Proxy / inbound model

- `ProxyInbound` (DB) mirrors inbound tags from `xray_config.json`
- `Proxy` (DB) stores per-user protocol settings as JSON
- `excluded_inbounds_association` tracks which inbounds a user is excluded from
- `xray.config.inbounds_by_protocol` and `inbounds_by_tag` are the in-memory index built from the Xray JSON config

### User statuses

`active` → `limited` / `expired` / `disabled` / `on_hold`

The `review_users` job runs on an interval and transitions users between statuses, fires webhook/Telegram notifications, and applies `next_plan` resets.
