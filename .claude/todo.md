# Todo — FilamentTracker

## Pending

### Security / Hardening
- [x] Server-side MIME validation on file uploads (`.3mf`, `.gcode`) — currently only `accept=` on the input
- [x] Add `MAX_UPLOAD_SIZE` check in the upload view
- [x] Review `ALLOWED_HOSTS` and `DEBUG=False` path for production

### Deployment
- [ ] Deploy to Railway (or Render): Procfile, `collectstatic`, env vars `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `DEBUG=False`
- [ ] Confirm `whitenoise` serves static files correctly under production settings

### Quality / UX
- [ ] Add Django system check to CI (or pre-commit hook)
- [ ] Mobile nav: link to Account page in mobile menu (currently missing)
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
- [x] Date fields: flatpickr altInput mm/dd/yyyy display, digit-mask entry

### Infrastructure
- [x] Supabase migration (SQLite → PostgreSQL via Session Pooler)
- [x] DB-level FK cascade migration (RunSQL 0004) for direct Supabase table editor deletes
- [x] GitHub repo setup and initial push (github.com/Melz8bit/filament-manager)
- [x] CLAUDE.md and .claude/settings.json initialized
