# FilamentTracker — App Planning Spec

---

## Overview

A web app (mobile-responsive) for tracking 3D print filament inventory. Users can manage their spool collection, log prints with filament usage, and automatically deduct from spool totals. Designed around a Django + Supabase stack with a deliberate, user-confirmed logging flow — no auto-writes without explicit action.

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Django templates + HTMX | Good for hands-on Django practice; HTMX handles interactivity without a full JS framework |
| Backend | Django (Python) | ORM, migrations, admin panel, forms |
| Database | Supabase (Postgres) | Connect via `dj-database-url` using Supabase's connection string |
| Auth | Django built-in auth | Single user for MVP; scaffolded for multi-user expansion later |
| File handling | Django file uploads | Parse `.3mf` and `.gcode` server-side |
| Styling | Tailwind CSS | Mobile-responsive, utility-first |
| Hosting | Railway or Render | Both support Django + environment variable config cleanly |

---

## Data Models

### `Spool`
```
id
brand               (str)
material            (str)        # PLA, PETG, ABS, TPU, etc.
color_name          (str)
color_hex           (str)        # e.g. #FF6B35
full_weight_g       (int)        # weight of a brand new full roll
remaining_g         (float)      # decremented on each confirmed print
price_paid          (decimal)
purchase_date       (date)
notes               (text, optional)
created_at
updated_at
```

### `PrintLog`
```
id
name                (str)
printed_at          (datetime)
source              (str)        # 'threemf', 'gcode', 'manual', 'script'
source_file         (file, optional)
source_url          (str, optional)   # MakerWorld or reference URL — stored only, not parsed
status              (str)        # 'queued', 'pending_assignment', 'confirmed'
queue_notes         (text, optional)  # mobile notes e.g. "red and white"
notes               (text, optional)
created_at
updated_at
```

### `PrintSpool` *(join table)*
```
id
print_log           (FK → PrintLog)
spool               (FK → Spool)
grams_used          (float)
slicer_hex          (str, optional)   # hex from slicer, used for matching only
```

---

## Print Log Status Flow

```
queued → pending_assignment → confirmed
```

| Status | Meaning |
|---|---|
| `queued` | URL saved from mobile, no file uploaded yet |
| `pending_assignment` | File parsed, waiting for user to confirm spool assignments |
| `confirmed` | Spools assigned, inventory deducted, print fully logged |

Nothing is deducted from spool inventory until status reaches `confirmed`.

---

## Feature Scope

### MVP

#### Filament Inventory
- View all spools — card or table layout with remaining % progress bar per spool
- Add a new spool: brand, material, color name, color hex, full roll weight (g), current remaining weight (g), price paid, purchase date, notes
- Edit spool details
- Delete a spool
- Low stock visual indicator (e.g. warning state below 100g remaining)

#### Log a Print
Three input methods, in priority order:

**1. `.3mf` upload (primary)**
- User exports `.3mf` from OrcaSlicer or Bambu Studio after final slice
- App parses embedded metadata server-side:
  - Grams used per color slot
  - Hex color code per slot
  - Material type per slot
- Skips slots with 0.00g used
- Handles both OrcaSlicer and Bambu Studio `.3mf` format variants
- Moves log to `pending_assignment`

**2. `.gcode` upload (secondary)**
- Parses the G-code header comment block:
  ```
  ; filament used [g] = 14.23, 6.87, 0.00, 2.41
  ; filament_colour = #FF6B35, #FFFFFF, #1A1A2E, #00C896
  ; filament_type = PLA, PLA, PLA, PETG
  ```
- Same comma-separated, positionally-aligned format as `.3mf`
- Same downstream flow as `.3mf` upload

**3. Manual entry (fallback)**
- Designed for Handy-initiated prints and reprints
- Fast, minimal form: print name, select spools used, enter grams per spool (or total to split)
- Target: completable in under 30 seconds on mobile
- Goes directly to `pending_assignment`

#### Spool Assignment Screen
Shown after any file parse or as part of manual entry:

- One row per active color slot
- Shows: color swatch (slicer hex), grams for that slot, material type
- Spool picker per slot — inventory sorted by **hex proximity** (closest color match pre-selected)
- Hex proximity algorithm — RGB Euclidean distance:
  ```python
  def hex_distance(hex1, hex2):
      r1,g1,b1 = int(hex1[1:3],16), int(hex1[3:5],16), int(hex1[5:7],16)
      r2,g2,b2 = int(hex2[1:3],16), int(hex2[3:5],16), int(hex2[5:7],16)
      return ((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2) ** 0.5
  ```
- User can override pre-selected spool with any spool from inventory
- If no close match exists, field defaults to unselected with full inventory list
- On confirm → deduct grams from each spool, set status to `confirmed`

#### Print Queue *(mobile-first)*
Bridges the gap between seeing a print on Handy/MakerWorld and processing it on desktop.

**Mobile flow:**
1. User sees a model in Bambu Handy or MakerWorld
2. Copies the share URL, pastes into the app's queue input
3. Optionally adds a note ("print in red and white")
4. Entry saved as `queued` — visible on dashboard as a pending item

**Desktop flow:**
1. User opens app, sees queued items on dashboard
2. Clicks the MakerWorld URL directly from the queue entry — opens the model page in browser
3. Downloads the `.3mf` from MakerWorld, uploads it to the queue entry
4. App parses filament data — hex proximity matching applied, closest spool pre-selected per slot
5. User confirms or overrides spool assignments
6. Entry moves `queued` → `confirmed`, spools deducted

#### Print History
- List of all confirmed prints, newest first
- Columns: print name, date, spools used (with color swatches), total grams, estimated cost
- Estimated cost per print = sum of `(grams_used / spool.full_weight_g) × spool.price_paid` per spool used
- Filterable by date range, spool, or material

#### Dashboard
- Total spools in inventory
- Total filament weight remaining (g / kg)
- Total estimated inventory value
- Low stock warnings (spools below 100g)
- Queued prints pending desktop processing
- Recent confirmed prints

---

### Post-MVP

- Multi-user auth (Django allauth or Supabase Auth)
- Spool "finished" archiving — mark as empty without deleting history
- Shopping list — auto-suggest reorder when spools are low
- Per-material / per-brand cost analytics
- Export inventory and print history as CSV
- Photo upload per spool
- OrcaSlicer post-processing script (optional companion tool — see below)

---

## OrcaSlicer Post-Processing Script *(Post-MVP, Optional)*

A small companion `.py` script users configure once in OrcaSlicer under `Others → Post-processing scripts`. Fires on every slice.

**Behavior:** Opens a browser tab to the app's new print log form with filament data pre-populated as URL parameters — does not auto-create any records. User still confirms before anything is saved.

```
https://yourapp.com/log/new?name=benchy&grams=14.23,6.87&hex=FF6B35,FFFFFF&type=PLA,PLA
```

**Limitations to document:**
- Fires on every slice, including exploratory slices — user ignores tabs they don't want
- Requires the app to be running and accessible from the user's machine
- Secured via a personal API token configured once in the script

---

## File Parsing Notes

### `.3mf` Format
A `.3mf` is a renamed ZIP file. Bambu Studio and OrcaSlicer embed slicer metadata in a `Metadata/` folder inside the archive. Filament usage is stored per-extruder slot in grams.

```python
import zipfile
import xml.etree.ElementTree as ET

def parse_3mf(file):
    with zipfile.ZipFile(file) as z:
        # Bambu Studio: Metadata/slice_info.config
        # OrcaSlicer:   Metadata/slice_info.config or similar
        # Read and parse XML for filament usage per slot
        pass
```

Both Bambu Studio and OrcaSlicer formats need to be handled — they differ slightly in XML structure.

### `.gcode` Format
Filament data is in the header as semicolon-prefixed comments:

```
; filament used [g] = 14.23, 6.87, 0.00, 2.41
; filament_colour = #FF6B35, #FFFFFF, #1A1A2E, #00C896
; filament_type = PLA, PLA, PLA, PETG
```

Parse by reading the first ~100 lines of the file, splitting comma-separated values, and zipping the three arrays together. Drop any slot where grams = 0.00.

### `.stl` Format
**Not supported.** Pure geometry only — no print metadata. Users with `.stl` files should open in OrcaSlicer, slice, and export as `.3mf`.

---

## Key Screens

| Screen | Purpose |
|---|---|
| Dashboard | Summary stats, low stock alerts, print queue, recent prints |
| Inventory | Spool list with progress bars, add/edit/delete |
| Print Queue | Queued MakerWorld URLs pending desktop processing |
| Log a Print | Step 1: file upload or manual entry → Step 2: spool assignment → confirm |
| Print History | Filterable log of all confirmed prints with cost estimates |
| Spool Detail | Individual spool page — usage history, all prints that consumed it |

---

## API Endpoint (for post-processing script, post-MVP)

```
GET /log/new/
```
Accepts query parameters: `name`, `grams`, `hex`, `type`
Pre-populates the new print log form. No data written on GET — only on user-confirmed POST.

Secured via a personal token passed as a query parameter, configured once by the user in the script.

---

## Deferred / Out of Scope

| Item | Reason |
|---|---|
| Bambu Handy direct integration | Closed ecosystem, auth lockdown Jan 2025, not viable |
| MakerWorld URL scraping | Bot detection, and filament data is slicer-dependent anyway |
| MQTT printer bridge | Fragile, requires always-on local device, post-MVP at earliest |
| Multi-user / auth | Scaffolded but not built in MVP |
