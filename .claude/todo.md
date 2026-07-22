# Todo — FilamentTracker

## Pending

### Deployment
- [x] Deploy to Raspberry Pi via Docker (running on OMV Pi at 192.168.1.73:8000)
- [x] Test Docker build and `docker compose up -d` on the Pi
- [x] Confirm `whitenoise` serves static files correctly under production settings
- [x] Public access migrated from ngrok to Cloudflare Tunnel on a purchased domain (`8bitcode.net`) — `filament.8bitcode.net` routes via `cloudflared` (systemd service `homepi` tunnel, config at `/etc/cloudflared/config.yml`) to `localhost:8000`; barcode/camera scanning confirmed working over the tunnel's HTTPS
- [x] ngrok fully removed (service, package, apt source, config, `.env.production` references)
- [ ] Add more hostname entries to `/etc/cloudflared/config.yml` ingress rules as future webapps are deployed to this Pi (e.g. `plex.8bitcode.net`, `<app>.8bitcode.net`) — no local reverse proxy (Caddy/NPM) needed since cloudflared already does hostname-based routing
- [x] Set up CI/CD: GitHub Actions self-hosted runner on the Pi (`.github/workflows/deploy.yml`), triggered on push to `main`, auto-runs `git pull && docker compose up --build -d` — confirmed working 2026-07-22

### Quality / UX
- [x] Add Django system check to CI — `docker compose run --rm web python manage.py check` runs as a gate in `.github/workflows/deploy.yml` before the deploy step; a failing check blocks the production `docker compose up -d`
- [ ] Forgot password link on login page (requires email backend setup)

---

## Completed

### Features (Phases 1–7)
- [x] Phase 1 — Project scaffolding (Django, Tailwind, HTMX, auth, base template)
- [x] Phase 2 — Spool inventory CRUD (cards, progress bars, low-stock indicator, HTMX delete confirm)
- [x] Phase 3 — Print logging (PrintLog + PrintSpool models, .3mf and .gcode parsers, file upload view)
- [x] Phase 4 — Spool assignment screen: hex proximity matching, formset confirm, atomic inventory deduction
- [x] Phase 5 — Print queue: mobile URL-paste form, desktop file-upload-to-queue flow
- [x] Phase 6 — Dashboard + print history: live stats, cost estimates, filterable history
- [x] Phase 7 — Manual entry + deployment prep: HTMX slot rows, Procfile, Railway config
- [x] SKU/product library: FilamentProduct model, CRUD, SKU HTMX lookup on spool form, QR code generation
- [x] User account management: username/email update, password change view
- [x] Date fields: flatpickr altInput mm/dd/yyyy display, digit-mask entry, 2-digit year auto-expansion

### Security / Hardening
- [x] Server-side MIME validation on file uploads (`.3mf`, `.gcode`)
- [x] `MAX_UPLOAD_SIZE` check in upload views (50 MB)
- [x] Production security settings (HTTPS headers, HSTS, CSRF trusted origins)

### Infrastructure
- [x] Supabase migration (SQLite → PostgreSQL via Session Pooler)
- [x] DB-level FK cascade migration (RunSQL 0004) for direct Supabase table editor deletes
- [x] GitHub repo setup and initial push (github.com/Melz8bit/filament-manager)
- [x] CLAUDE.md and .claude/settings.json initialized

### UX / Polish
- [x] Remove UTF-8 BOM from base.html (was displacing head content into body DOM)
- [x] HTMX history caching disabled (belt-and-suspenders fix for DOM corruption)
- [x] Spool delete Cancel button: HTMX restore to spool card (no page navigation)
- [x] Mobile nav: Account link with username in bottom section
- [x] Site title "Filament Tracker" links to dashboard
- [x] Dashboard stat cards clickable (Spools → inventory, Prints/Filament Used → history)
- [x] Add Spool form: Product Library dropdown to pre-fill from existing products
- [x] Add Spool form: color name → hex auto-fill from ~700 XKCD color names
- [x] Add Spool form: full_weight_g defaults to 1000g if left blank
- [x] Spool assignment dropdown sorted alphabetically (color pre-selection preserved)
- [x] Queue mobile layout: stacks vertically on small screens
- [x] Queue: shows "Assign Spools" button + color swatches when MakerWorld filament data pre-fetched; otherwise shows file upload form
- [x] Queue: status stays "queued" until spool assignment confirmed
- [x] Log a Print: URL input field with MakerWorld auto-fetch or redirect to manual entry for other sites
- [x] URL title extraction: MakerWorld (API), Printables (GraphQL), Thangs (slug decode), Thingiverse (HTML fallback)
- [x] Spool assignment: split a slot into multiple sub-slots with live remaining counter; spool selected from inventory
- [x] Spool assignment: confirm redirects to print history (not inventory)
- [x] Spool assignment: continuation spool selector when primary spool can't cover slot grams
- [x] Inventory: hide 0g spools when a live sibling of same brand/color/material exists
- [x] Inventory: low-stock filter and dashboard exclude spools with a well-stocked sibling
- [x] Inventory: grouped view (Cards / Grouped toggle, persists in session)
- [x] Docker deployment files: Dockerfile, compose.yml, .dockerignore
