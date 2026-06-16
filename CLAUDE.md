# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FilamentTracker — a Django web app for tracking 3D print filament inventory. Spec: `filament-tracker-spec.md`.

## Common Commands

All Python commands must use the venv interpreter directly (the venv is not auto-activated in shell sessions):

```powershell
# Django dev server
.\venv\Scripts\python.exe manage.py runserver

# Migrations
.\venv\Scripts\python.exe manage.py makemigrations
.\venv\Scripts\python.exe manage.py migrate

# Django system check
.\venv\Scripts\python.exe manage.py check

# Tailwind — watch mode (run in a separate terminal alongside runserver)
npm run dev

# Tailwind — production build
npm run build
```

## Architecture

**Django project package:** `config/` — settings, root URLs, wsgi/asgi.  
**Single Django app:** `tracker/` — all models, views, forms, URLs, and templates for MVP features.  
**Templates:** Project-level templates in `templates/` (base layout, auth). App templates in `tracker/templates/tracker/`.  
**Static:** Source CSS at `static/css/src/input.css` → compiled to `static/css/main.css` (gitignored) by Tailwind CLI.  
**Uploads:** `MEDIA_ROOT = uploads/` (gitignored) for `.3mf` and `.gcode` file uploads.

### Key files

| File | Purpose |
|---|---|
| `config/settings.py` | All environment config via `python-decouple`; database via `dj-database-url` |
| `tracker/models.py` | `Spool`, `PrintLog`, `PrintSpool` (join table) |
| `tracker/parsers.py` | (Phase 3) `.3mf` and `.gcode` file parsing — pure functions, no Django imports |
| `tracker/utils.py` | (Phase 4) `hex_distance()` and `rank_spools_by_color()` for spool color matching |
| `tracker/constants.py` | `LOW_STOCK_THRESHOLD_G = 100` and other shared constants |

### Data flow

Print logging follows a strict status progression: `queued → pending_assignment → confirmed`. Spool inventory (`remaining_g`) is **never decremented** until status reaches `confirmed`, which happens in a single `transaction.atomic()` block in the spool assignment view.

### Database

SQLite locally (default fallback). Supabase (Postgres) in production — set `DATABASE_URL` in `.env`. Switch is a one-line env var change; no code changes needed.

### Frontend

- Tailwind CSS v3 (Node CLI pipeline, `tailwind.config.js`)
- HTMX 1.9 loaded via CDN in `base.html`; CSRF token injected via `hx-headers` on `<body>`
- `django-htmx` middleware adds `request.htmx` helper in views

## Environment Variables (`.env`)

```
SECRET_KEY=
DEBUG=True
DATABASE_URL=          # blank = SQLite; set to postgres:// for Supabase
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Implementation Status

Building phase by phase — see plan at `C:\Users\nival\.claude\plans\read-the-contents-of-idempotent-galaxy.md`.

- [x] Phase 1 — Project scaffolding
- [x] Phase 2 — Spool inventory CRUD
- [ ] Phase 3 — File parsing + print log flow
- [ ] Phase 4 — Spool assignment screen
- [ ] Phase 5 — Print queue
- [ ] Phase 6 — Dashboard + print history
- [ ] Phase 7 — Manual entry + deployment prep