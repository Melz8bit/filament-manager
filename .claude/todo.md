# Todo — FilamentTracker

## Pending

### Deployment
- [ ] Add more hostname entries to `/etc/cloudflared/config.yml` ingress rules as future webapps are deployed to this Pi (e.g. `plex.8bitcode.net`, `<app>.8bitcode.net`) — no local reverse proxy (Caddy/NPM) needed since cloudflared already does hostname-based routing

### Quality / UX
- [ ] Forgot password link on login page (requires email backend setup)
- [x] Log a Print: filament selection dropdown should not show 0g spools — `remaining_g__gt=0` filter applied to all 4 spool-selection query sites in `views.py` (main assignment, slot restore, split GET/POST)
- [x] Spool assignment default selection now material-aware (2026-09-08) — was defaulting a plain PLA print to e.g. a "Black HT-PLA" spool just because it was closer alphabetically/color-wise; now prefers an exact material match, falls back to plain PLA, then any spool, ranked by color distance within that group. `PrintSpool.slicer_material` field added to persist the gcode's parsed filament type (was previously parsed but discarded); `rank_spools_by_material_and_color()` in `utils.py`
- [x] Spool assignment: insufficient-filament guard (2026-09-18) — selecting a spool with less than the slot needs now shows an at-a-glance red badge/ring + expanded "replacement spool needed" panel computed server-side (not dependent on JS timing), and `SpoolAssignmentView.post` validates every slot before saving anything — a submission where the chosen spool(s) can't fully cover the grams needed is rejected with a specific error instead of silently flooring `remaining_g` to 0. Client-side submit guard added too as a faster feedback layer. `_build_slot_dict()` helper in `views.py` shared across all 3 slot-rendering call sites; 6 new regression tests

### Features
- [x] Process to handle failed prints (2026-09-08) — "Failed Print" button on confirmed prints in history, expands an inline row for layer number (preferred) or percent complete; `estimate_remaining_by_layer()` in `parsers.py` walks the actual gcode extrusion per color between `; CHANGE_LAYER` markers to credit back the real unused amount per spool (not just a naive uniform fraction), falling back to percent-based uniform credit when no per-layer gcode data is available. `PrintLog.failed_at_layer/failed_total_layers/failed_at_percent` + `PrintSpool.grams_returned` fields; 15 regression tests in `tracker/tests.py` including one against a real 4-color 405-layer fixture file
- [x] Print cost calculator, logged to the project — `/calculator/` (Material/Electricity/Depreciation/Labor breakdown, live totals, Bambu A1 Mini/P1S presets) + `/sales-log/` (saved entries with summary stats, mirrors the user's spreadsheet: total prints, revenue, profit, avg margin, most-used printer); `PrintSale` model, edit/delete per entry

### Bug Fixes (2026-08-19)
- [x] Uploading a `.3mf` with an 8-digit slicer color (`RRGGBBAA`, includes alpha) crashed with a 500 — `PrintSpool.slicer_hex` is `CharField(max_length=7)` and Postgres/Supabase enforces that length on insert, unlike SQLite. `parse_3mf`/`parse_gcode` in `parsers.py` now truncate parsed hex colors to 6 digits before returning them

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

### Deployment & CI/CD (2026-07-22)
- [x] Deployed to Raspberry Pi via Docker (OMV Pi, `compose.yml`, `restart: unless-stopped`)
- [x] Public access migrated from ngrok to Cloudflare Tunnel on purchased domain `8bitcode.net` — `filament.8bitcode.net` → `cloudflared` (systemd service, tunnel `homepi`) → `localhost:8000`; barcode/camera scanning confirmed working over the tunnel's HTTPS
- [x] ngrok fully removed (service, package, apt source, config, `.env.production` references)
- [x] CI/CD: GitHub Actions self-hosted runner on the Pi (`.github/workflows/deploy.yml`), auto-deploys on push to `main`
- [x] CI gate: `docker compose run --rm web python manage.py check` runs before the deploy step — a failing check blocks production

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

### Mobile UI fixes (2026-07-22)
- [x] Inventory: top bar stacks on mobile instead of crowding; view-mode picker hidden below `sm` breakpoint, mobile sessions default to grouped view (detected via User-Agent)
- [x] Log a Print: "No file? Enter manually" link moved to its own line above Cancel/Continue
- [x] Print History: mobile-only card layout (name + colors on one line, date/grams/cost below) replaces the table on small screens; long unspaced names wrap inside the card instead of overflowing it
- [x] Print names capped at 60 chars (`PRINT_NAME_MAX_LENGTH`) everywhere a name gets set — file upload, URL fetch, queue add/edit, manual entry, HTMX title-fetch — with matching `maxlength` on the inputs

### Cost Calculator & Sales Log (2026-07-30)
- [x] Spool assignment dropdowns: same-color spools ordered least-remaining-first (least-depleted spool becomes the default pick, via `remaining_g` tiebreaker + stable color-distance sort)
- [x] Calculator defaults (spool cost, filament used, print duration, printer cost, lifespan) zeroed out instead of sample values
- [x] Calculator "Save to Sales Log" Printer field always syncs to the selected printer preset
- [x] Print History: "Calculate cost" link per row opens the calculator pre-filled with item name, total grams, and the priciest assigned spool's $/kg (conservative estimate for multi-color prints)

### Dashboard Graphs (2026-07-30)
- [x] Filament Usage line charts — last 12 weeks and last 30 days, hover tooltip + crosshair, shared `usage_chart.html` partial + `_usage_chart(period, periods)` view helper
- [x] Top Materials & Colors ranked bar chart (real filament colors as bar fill, with a visibility ring so white/light colors don't disappear against the track)
- [x] Fixed week-chart tooltip label ("Week of Jul 13–19" instead of a bare start date that read as a single day with no prints)
- [x] Fixed end-of-line value label colliding with a steep incoming line (white halo via SVG `paint-order="stroke"`)

### Bug Fixes (2026-07-30)
- [x] Timezone: `TIME_ZONE` was `UTC`, causing late-night local prints to display as the next day; changed to `America/New_York` (inferred from the FPL electricity-rate default in the calculator — confirm if wrong)

### Dark Mode (2026-07-30)
- [x] Site-wide dark mode: sun/moon toggle in nav, persisted via Django session (same mechanism as the existing Inventory Cards/Grouped toggle — resets on logout, not tied to the user account)
- [x] Tailwind `darkMode: 'class'` + `dark:` variants applied across all 28 templates, shared form-input classes (`forms.py`), and the flatpickr date-picker popup (re-skinned manually — ships light-only by default)
- [x] Spool color swatches deliberately unaffected (raw inline `background-color` styles, untouched by theme classes) — verified visually
- [x] Fixed ~46 hand-coded `<input>`/`<select>` elements across 13 templates that had no explicit background color set (would have stayed white boxes in dark mode)

### Polish & Fixes (2026-08-11)
- [x] Added `static/favicon.svg` (simple indigo spool icon) — was 404ing on every page load, no favicon existed anywhere in the app
- [x] Dashboard usage charts: fixed the end-of-line value label clipping against the chart's top edge when the highest value in the series is also the most recent point (very large day/week totals) — added dedicated top headroom (`_CHART_PAD_TOP`) separate from the side/bottom padding
- [x] Nav: added a third responsive tier for medium widths (~768–1024px — tablets, foldable-interior screens) where the full link row didn't fit but the desktop breakpoint had already activated, causing "Log a Print" to wrap onto 3 lines. New "Menu ▾" trigger opens a compact 2-column dropdown card (styled like a desktop dropdown, not a reused mobile sheet); true mobile hamburger and full desktop row both untouched

### Polish & Fixes (2026-08-12)
- [x] Swapped favicon from the placeholder SVG to a user-supplied `static/filament-icon.png` (64x64, transparent, actual spool icon); removed the now-unused `favicon.svg`
