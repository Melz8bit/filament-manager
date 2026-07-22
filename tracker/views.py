import html as html_lib
import json
import re
import urllib.request
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from urllib.parse import urlencode
from django.utils import timezone
from django.utils.html import format_html
from django.views import View
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import ListView, CreateView, UpdateView

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Exists, OuterRef, Sum

from .forms import SpoolForm, FilamentProductForm, AccountForm
from .models import Spool, PrintLog, PrintSpool, FilamentProduct


class AccountView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = AccountForm
    template_name = 'tracker/account.html'
    success_url = reverse_lazy('account')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Account updated.')
        return super().form_valid(form)


class AccountPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'tracker/password_change.html'
    success_url = reverse_lazy('account')

    def form_valid(self, form):
        messages.success(self.request, 'Password changed successfully.')
        return super().form_valid(form)


def _title_from_url_slug(url):
    """Extract a model name from the URL path for known 3D printing sites."""
    from urllib.parse import urlparse, unquote
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    segment = parsed.path.rstrip("/").split("/")[-1]

    if host in ("makerworld.com", "printables.com"):
        # paths like /en/models/2599617-parametric-organizer or /model/123456-my-model
        name = re.sub(r"^\d+-", "", segment)
        # If only digits remain (no slug text was stripped), fall through to network fetch
        if not name or name.isdigit():
            return ""
        return name.replace("-", " ").title()

    if host == "thingiverse.com":
        # paths like /thing:123456 — no name in slug
        return ""

    if host == "thangs.com":
        # paths like /designer/user/3d-model/Title%20Here-1234567
        decoded = unquote(segment)
        name = re.sub(r"-\d+$", "", decoded).strip()
        return name if name and not name.isdigit() else ""

    return ""


def _fetch_printables_title(model_id):
    """Fetch a Printables model title via their public GraphQL API."""
    gql = json.dumps({"query": "{ print(id: " + model_id + ") { name } }"}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.printables.com/graphql/",
        data=gql,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Referer": "https://www.printables.com/",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("data", {}).get("print", {}).get("name", "")


def _fetch_page_title(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")

    # Try slug extraction first (instant, no network needed)
    title = _title_from_url_slug(url)
    if title:
        # Printables: upgrade slug title to real title via GraphQL (preserves special chars)
        if host == "printables.com":
            segment = parsed.path.rstrip("/").split("/")[-1]
            m = re.match(r"^(\d+)", segment)
            if m:
                try:
                    api_title = _fetch_printables_title(m.group(1))
                    if api_title:
                        return api_title
                except Exception:
                    pass
        return title

    # Fallback: fetch the page and read <title> or og:title
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read(32768).decode("utf-8", errors="ignore")
        # og:title first (more accurate on SPAs with SSR)
        m = re.search(
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
            raw, re.IGNORECASE,
        ) or re.search(
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:title["\']',
            raw, re.IGNORECASE,
        )
        if m:
            return html_lib.unescape(m.group(1).strip())
        m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
        if m:
            return html_lib.unescape(m.group(1).strip())
    except Exception:
        pass
    return ""


def _fetch_makerworld_filaments(url):
    """
    Query the MakerWorld API for per-plate filament usage.
    Returns list[dict] with grams/hex/material (same format as parsers),
    or [] if the URL is not MakerWorld or on any error.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    if host != "makerworld.com":
        return []

    # Extract numeric model ID from path: /en/models/2978237-slug or /2978237
    segments = [s for s in parsed.path.split("/") if s]
    if not segments:
        return []
    m = re.match(r"^(\d+)", segments[-1])
    if not m:
        return []
    model_id = m.group(1)

    # Extract instance ID from fragment: #profileId-3341125
    instance_id = None
    if parsed.fragment:
        fm = re.search(r"profileId[:\-](\d+)", parsed.fragment)
        if fm:
            instance_id = int(fm.group(1))

    try:
        api_url = "https://makerworld.com/api/v1/design-service/design/" + model_id
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, */*",
            "Referer": "https://makerworld.com/",
        }
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    instances = data.get("instances", [])
    if not instances:
        return []

    # Pick the instance matching the URL fragment, then defaultInstanceId, then first
    instance = None
    if instance_id:
        instance = next((i for i in instances if i.get("id") == instance_id), None)
    if instance is None:
        default_id = data.get("defaultInstanceId")
        if default_id:
            instance = next((i for i in instances if i.get("id") == default_id), None)
    if instance is None:
        instance = instances[0]

    plates = instance.get("extention", {}).get("modelInfo", {}).get("plates", [])

    # Aggregate grams per (hex, material) across all plates
    totals = {}
    for plate in plates:
        for f in plate.get("filaments", []):
            hex_val = f.get("color", "")
            if not hex_val.startswith("#"):
                hex_val = "#" + hex_val
            material = f.get("type", "")
            try:
                grams = float(f.get("usedG", 0))
            except (ValueError, TypeError):
                continue
            key = (hex_val, material)
            totals[key] = totals.get(key, 0.0) + grams

    return [
        {"grams": grams, "hex": hex_val, "material": material}
        for (hex_val, material), grams in totals.items()
        if grams > 0
    ]


from .constants import LOW_STOCK_THRESHOLD_G, PRINT_NAME_MAX_LENGTH
from .parsers import parse_3mf, parse_gcode
from .utils import parse_filament_product, is_filament_product, rank_spools_by_color


def _is_mobile_request(request):
    return bool(re.search(r"Mobi", request.META.get("HTTP_USER_AGENT", "")))


@login_required
def dashboard(request):
    _well_stocked_sibling = Spool.objects.filter(
        brand=OuterRef("brand"),
        color_name=OuterRef("color_name"),
        material=OuterRef("material"),
        remaining_g__gte=LOW_STOCK_THRESHOLD_G,
    )
    low_stock_spools = (
        Spool.objects.annotate(has_well_stocked_sibling=Exists(_well_stocked_sibling))
        .filter(remaining_g__lt=LOW_STOCK_THRESHOLD_G)
        .exclude(has_well_stocked_sibling=True)
        .order_by("remaining_g")
    )
    total_grams = (
        PrintSpool.objects.filter(print_log__status="confirmed")
        .aggregate(total=Sum("grams_used"))["total"] or 0
    )
    recent_prints = (
        PrintLog.objects.filter(status="confirmed")
        .prefetch_related("spools_used__spool")
        .order_by("-printed_at")[:5]
    )
    return render(request, "tracker/dashboard.html", {
        "total_spools": Spool.objects.count(),
        "low_stock_spools": low_stock_spools,
        "confirmed_prints": PrintLog.objects.filter(status="confirmed").count(),
        "total_grams": total_grams,
        "queued_count": PrintLog.objects.filter(status="queued").count(),
        "recent_prints": recent_prints,
    })


class SpoolListView(LoginRequiredMixin, ListView):
    model = Spool
    template_name = "tracker/spool_list.html"
    context_object_name = "spools"

    _SORT_MAP = {
        "brand_asc":      ("brand", "color_name"),
        "brand_desc":     ("-brand", "-color_name"),
        "color_asc":      ("color_name",),
        "color_desc":     ("-color_name",),
        "material_asc":   ("material", "brand"),
        "material_desc":  ("-material", "-brand"),
        "remaining_asc":  ("remaining_g",),
        "remaining_desc": ("-remaining_g",),
    }

    def get_queryset(self):
        live_sibling = Spool.objects.filter(
            brand=OuterRef("brand"),
            color_name=OuterRef("color_name"),
            material=OuterRef("material"),
            remaining_g__gt=0,
        )
        well_stocked_sibling = Spool.objects.filter(
            brand=OuterRef("brand"),
            color_name=OuterRef("color_name"),
            material=OuterRef("material"),
            remaining_g__gte=LOW_STOCK_THRESHOLD_G,
        )
        qs = (
            Spool.objects.annotate(
                has_live_sibling=Exists(live_sibling),
                has_well_stocked_sibling=Exists(well_stocked_sibling),
            )
            .exclude(remaining_g=0, has_live_sibling=True)
        )
        if brand := self.request.GET.get("brand"):
            qs = qs.filter(brand=brand)
        if material := self.request.GET.get("material"):
            qs = qs.filter(material=material)
        if color := self.request.GET.get("color"):
            qs = qs.filter(color_name__icontains=color)
        if self.request.GET.get("low_stock"):
            qs = qs.filter(remaining_g__lt=LOW_STOCK_THRESHOLD_G).exclude(has_well_stocked_sibling=True)
        order = self._SORT_MAP.get(self.request.GET.get("sort", "brand_asc"), ("brand", "color_name"))
        return qs.order_by(*order)

    def get(self, request, *args, **kwargs):
        if "view" in request.GET:
            request.session["spool_view"] = request.GET["view"]
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["brands"] = Spool.objects.values_list("brand", flat=True).distinct().order_by("brand")
        ctx["materials"] = Spool.objects.values_list("material", flat=True).distinct().order_by("material")
        ctx["total_count"] = Spool.objects.count()
        ctx["f"] = self.request.GET
        default_view = "grouped" if _is_mobile_request(self.request) else "cards"
        view_mode = self.request.session.get("spool_view", default_view)
        ctx["view_mode"] = view_mode
        if view_mode == "grouped":
            spools_sorted = sorted(
                ctx["spools"],
                key=lambda s: (s.brand, s.color_name, s.material, -s.remaining_g),
            )
            groups = []
            for key, group_iter in groupby(
                spools_sorted, key=lambda s: (s.brand, s.color_name, s.material)
            ):
                spool_list = list(group_iter)
                groups.append({
                    "brand": key[0],
                    "color_name": key[1],
                    "material": key[2],
                    "color_hex": spool_list[0].color_hex,
                    "spools": spool_list,
                    "total_remaining": sum(s.remaining_g for s in spool_list),
                })
            ctx["groups"] = groups
        return ctx


class SpoolCreateView(LoginRequiredMixin, CreateView):
    model = Spool
    form_class = SpoolForm
    template_name = "tracker/spool_form.html"
    success_url = reverse_lazy("spool-list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(title="Add Spool", **kwargs)
        ctx["products"] = FilamentProduct.objects.all()
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        sku = form.cleaned_data.get("sku", "").strip()
        if sku:
            FilamentProduct.objects.get_or_create(
                sku=sku,
                defaults={
                    "brand": form.cleaned_data["brand"],
                    "material": form.cleaned_data["material"],
                    "color_name": form.cleaned_data["color_name"],
                    "color_hex": form.cleaned_data["color_hex"],
                    "full_weight_g": form.cleaned_data["full_weight_g"],
                    "diameter_mm": form.cleaned_data["diameter_mm"],
                },
            )
        return response


class SpoolUpdateView(LoginRequiredMixin, UpdateView):
    model = Spool
    form_class = SpoolForm
    template_name = "tracker/spool_form.html"
    success_url = reverse_lazy("spool-list")

    def get_context_data(self, **kwargs):
        return super().get_context_data(title=f"Edit {self.object}", **kwargs)


class SpoolCardView(LoginRequiredMixin, View):
    def get(self, request, pk):
        spool = get_object_or_404(Spool, pk=pk)
        return render(request, "tracker/partials/spool_card.html", {"spool": spool})


class SpoolDeleteView(LoginRequiredMixin, View):
    def get(self, request, pk):
        spool = get_object_or_404(Spool, pk=pk)
        return render(request, "tracker/spool_confirm_delete.html", {"spool": spool})

    def post(self, request, pk):
        spool = get_object_or_404(Spool, pk=pk)
        spool.delete()
        if request.htmx:
            return HttpResponse("")
        messages.success(request, "Spool deleted.")
        return redirect("spool-list")


class SkuLookupView(LoginRequiredMixin, View):
    def get(self, request):
        sku = re.sub(r"[^A-Za-z0-9]", "", request.GET.get("sku", ""))
        if len(sku) < 4:
            return HttpResponse("")
        try:
            product = FilamentProduct.objects.get(sku__iexact=sku)
        except FilamentProduct.DoesNotExist:
            return render(request, "tracker/partials/sku_result.html", {"not_found": True, "sku": sku})
        return render(request, "tracker/partials/sku_result.html", {"product": product})


class FilamentProductListView(LoginRequiredMixin, ListView):
    model = FilamentProduct
    template_name = "tracker/filament_product_list.html"
    context_object_name = "products"


class FilamentProductUpdateView(LoginRequiredMixin, UpdateView):
    model = FilamentProduct
    form_class = FilamentProductForm
    template_name = "tracker/filament_product_form.html"
    success_url = reverse_lazy("filament-product-list")

    def get_context_data(self, **kwargs):
        return super().get_context_data(title=f"Edit {self.object}", **kwargs)


class FilamentProductDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        get_object_or_404(FilamentProduct, pk=pk).delete()
        return redirect("filament-product-list")


MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

_ZIP_MAGIC = b"PK\x03\x04"


def _validate_upload(uploaded_file):
    """Return (source, error_str). source is 'threemf' | 'gcode'; error_str is None on success."""
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        return None, "File too large (max 50 MB)."

    name = uploaded_file.name.lower()
    header = uploaded_file.read(512)
    uploaded_file.seek(0)

    if name.endswith(".3mf"):
        if not header.startswith(_ZIP_MAGIC):
            return None, "Invalid .3mf file (not a valid ZIP archive)."
        return "threemf", None
    elif name.endswith(".gcode"):
        try:
            header.decode("utf-8")
        except UnicodeDecodeError:
            return None, "Invalid .gcode file (not valid UTF-8 text)."
        return "gcode", None
    else:
        return None, "Unsupported file type. Upload a .3mf or .gcode file."


class LogPrintView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "tracker/log_print.html")

    def post(self, request):
        uploaded_file = request.FILES.get("source_file")
        source_url = request.POST.get("source_url", "").strip()
        name = request.POST.get("name", "").strip()

        if uploaded_file:
            source, error = _validate_upload(uploaded_file)
            if error:
                messages.error(request, error)
                return render(request, "tracker/log_print.html")

            slots = parse_3mf(uploaded_file) if source == "threemf" else parse_gcode(uploaded_file)
            if not slots:
                messages.error(request, "No filament data found in that file.")
                return render(request, "tracker/log_print.html")

            print_log = PrintLog.objects.create(
                name=(name or uploaded_file.name)[:PRINT_NAME_MAX_LENGTH],
                printed_at=timezone.now(),
                source=source,
                source_file=uploaded_file,
                status="pending_assignment",
            )

        elif source_url:
            slots = _fetch_makerworld_filaments(source_url)
            if slots:
                # MakerWorld with filament data — go straight to spool assignment
                print_log = PrintLog.objects.create(
                    name=(name or _fetch_page_title(source_url) or source_url)[:PRINT_NAME_MAX_LENGTH],
                    printed_at=timezone.now(),
                    source="threemf",
                    source_url=source_url,
                    status="pending_assignment",
                )
            else:
                # Other sites — fetch title and hand off to manual entry
                title = (name or _fetch_page_title(source_url) or "")[:PRINT_NAME_MAX_LENGTH]
                messages.info(request, "Filament data isn't available for this URL — enter it manually below.")
                qs = urlencode({"name": title, "source_url": source_url})
                return redirect(reverse("manual-entry") + "?" + qs)

        else:
            messages.error(request, "Please upload a file or enter a URL.")
            return render(request, "tracker/log_print.html")

        for slot in slots:
            PrintSpool.objects.create(
                print_log=print_log,
                grams_used=slot["grams"],
                slicer_hex=slot["hex"],
            )

        return redirect("spool-assignment", pk=print_log.pk)


class SpoolAssignmentView(LoginRequiredMixin, View):
    def get(self, request, pk):
        print_log = get_object_or_404(PrintLog, pk=pk)
        all_spools = list(Spool.objects.order_by("brand", "color_name", "material"))
        slots = []
        for ps in print_log.spools_used.all():
            ranked = rank_spools_by_color(ps.slicer_hex, all_spools) if ps.slicer_hex else all_spools
            best_pk = ranked[0].pk if ranked else None
            slots.append({"print_spool": ps, "spools": all_spools, "best_pk": best_pk})
        return render(request, "tracker/spool_assignment.html", {
            "print_log": print_log,
            "slots": slots,
        })

    def post(self, request, pk):
        print_log = get_object_or_404(PrintLog, pk=pk)
        with transaction.atomic():
            for ps in list(print_log.spools_used.all()):
                spool_id = request.POST.get(f"spool_{ps.pk}")
                cont_spool_id = request.POST.get(f"continuation_spool_{ps.pk}")
                if not spool_id:
                    continue
                spool = get_object_or_404(Spool, pk=spool_id)
                if cont_spool_id:
                    # Primary spool runs out; remainder comes from continuation spool
                    cont_spool = get_object_or_404(Spool, pk=cont_spool_id)
                    primary_grams = float(spool.remaining_g)
                    cont_grams = max(0, float(ps.grams_used) - primary_grams)
                    ps.spool = spool
                    ps.grams_used = primary_grams
                    ps.save()
                    PrintSpool.objects.create(
                        print_log=print_log,
                        spool=cont_spool,
                        grams_used=cont_grams,
                        slicer_hex=ps.slicer_hex,
                    )
                    spool.remaining_g = 0
                    spool.save()
                    cont_spool.remaining_g = max(0, cont_spool.remaining_g - cont_grams)
                    cont_spool.save()
                else:
                    spool.remaining_g = max(0, spool.remaining_g - float(ps.grams_used))
                    spool.save()
                    ps.spool = spool
                    ps.save()
            print_log.status = "confirmed"
            print_log.save()
        messages.success(request, f'"{print_log.name}" confirmed. Inventory updated.')
        return redirect("print-history")


class QueueListView(LoginRequiredMixin, ListView):
    template_name = "tracker/queue_list.html"
    context_object_name = "queued_prints"

    def get_queryset(self):
        return PrintLog.objects.filter(status="queued").order_by("-created_at")


class QueueAddView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "tracker/queue_add.html")

    def post(self, request):
        url = request.POST.get("source_url", "").strip()
        name = request.POST.get("name", "").strip()
        notes = request.POST.get("queue_notes", "").strip()

        if not url:
            messages.error(request, "Please paste a URL.")
            return render(request, "tracker/queue_add.html")

        # Fetch title from URL if name not provided
        if not name:
            name = _fetch_page_title(url) or url
        name = name[:PRINT_NAME_MAX_LENGTH]

        print_log = PrintLog.objects.create(
            name=name,
            printed_at=timezone.now(),
            source="threemf",
            source_url=url,
            queue_notes=notes,
            status="queued",
        )

        # Auto-fetch filament data from MakerWorld API if available
        slots = _fetch_makerworld_filaments(url)
        for slot in slots:
            PrintSpool.objects.create(
                print_log=print_log,
                grams_used=slot["grams"],
                slicer_hex=slot["hex"],
            )

        if slots:
            messages.success(request, "Added to queue with filament data from MakerWorld.")
        else:
            messages.success(request, "Added to queue.")
        return redirect("queue-list")


class QueueUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        print_log = get_object_or_404(PrintLog, pk=pk, status="queued")
        uploaded_file = request.FILES.get("source_file")

        if not uploaded_file:
            messages.error(request, "Please select a file.")
            return redirect("queue-list")

        source, error = _validate_upload(uploaded_file)
        if error:
            messages.error(request, error)
            return redirect("queue-list")

        slots = parse_3mf(uploaded_file) if source == "threemf" else parse_gcode(uploaded_file)

        if not slots:
            messages.error(request, "No filament data found in that file.")
            return redirect("queue-list")

        # Clear any PrintSpools from a previous upload attempt on this queue item
        print_log.spools_used.all().delete()

        print_log.source = source
        print_log.source_file = uploaded_file
        # Keep status "queued" — item stays in queue until assignment is confirmed
        print_log.save()

        for slot in slots:
            PrintSpool.objects.create(
                print_log=print_log,
                grams_used=slot["grams"],
                slicer_hex=slot["hex"],
            )

        return redirect("spool-assignment", pk=print_log.pk)


class QueueEditView(LoginRequiredMixin, View):
    def get(self, request, pk):
        entry = get_object_or_404(PrintLog, pk=pk, status="queued")
        return render(request, "tracker/queue_edit.html", {"entry": entry})

    def post(self, request, pk):
        entry = get_object_or_404(PrintLog, pk=pk, status="queued")
        url = request.POST.get("source_url", "").strip()
        name = request.POST.get("name", "").strip()
        notes = request.POST.get("queue_notes", "").strip()
        if not url:
            messages.error(request, "Please paste a URL.")
            return render(request, "tracker/queue_edit.html", {"entry": entry})
        entry.name = (name or url)[:PRINT_NAME_MAX_LENGTH]
        entry.source_url = url
        entry.queue_notes = notes
        entry.save()
        messages.success(request, "Queue entry updated.")
        return redirect("queue-list")


class QueueDeleteView(LoginRequiredMixin, View):
    def get(self, request, pk):
        entry = get_object_or_404(PrintLog, pk=pk, status="queued")
        return render(request, "tracker/partials/queue_confirm_delete.html", {"entry": entry})

    def post(self, request, pk):
        entry = get_object_or_404(PrintLog, pk=pk, status="queued")
        entry.delete()
        if request.htmx:
            return HttpResponse("")
        return redirect("queue-list")


class QueueFetchTitleView(LoginRequiredMixin, View):
    def get(self, request):
        url = request.GET.get("source_url", "").strip()
        title = (_fetch_page_title(url) if url else "") or ""
        title = title[:PRINT_NAME_MAX_LENGTH]
        return HttpResponse(format_html(
            '<input type="text" id="name" name="name" value="{}" '
            'placeholder="e.g. Articulated Dragon" maxlength="{}" '
            'class="block w-full rounded-md border-gray-300 shadow-sm '
            'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">',
            title, PRINT_NAME_MAX_LENGTH,
        ))


class PrintHistoryView(LoginRequiredMixin, ListView):
    model = PrintLog
    template_name = "tracker/print_history.html"
    context_object_name = "prints"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            PrintLog.objects.filter(status="confirmed")
            .prefetch_related("spools_used__spool")
            .order_by("-printed_at")
        )
        if material := self.request.GET.get("material"):
            qs = qs.filter(spools_used__spool__material=material)
        if spool_id := self.request.GET.get("spool"):
            qs = qs.filter(spools_used__spool__id=spool_id)
        if date_from := self.request.GET.get("date_from"):
            qs = qs.filter(printed_at__date__gte=date_from)
        if date_to := self.request.GET.get("date_to"):
            qs = qs.filter(printed_at__date__lte=date_to)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["materials"] = (
            Spool.objects.values_list("material", flat=True).distinct().order_by("material")
        )
        ctx["spools"] = Spool.objects.order_by("brand", "color_name")
        ctx["f"] = self.request.GET
        return ctx


class SlotRowView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "tracker/partials/slot_row.html")


class SpoolSlotRowView(LoginRequiredMixin, View):
    """Returns a single assignment slot row (used to restore after a cancelled split)."""
    def get(self, request, pk):
        ps = get_object_or_404(PrintSpool, pk=pk)
        all_spools = list(Spool.objects.order_by("brand", "color_name", "material"))
        ranked = rank_spools_by_color(ps.slicer_hex, all_spools) if ps.slicer_hex else all_spools
        best_pk = ranked[0].pk if ranked else None
        return render(request, "tracker/partials/spool_slot_row.html", {
            "slot": {"print_spool": ps, "spools": all_spools, "best_pk": best_pk},
        })


class SplitSpoolSlotView(LoginRequiredMixin, View):
    """GET: inline split form. POST: validate, delete original, create sub-slots."""
    def _build_slot(self, ps, all_spools):
        # If a spool was pre-assigned during split, keep it selected
        if ps.spool_id:
            best_pk = ps.spool_id
        else:
            ranked = rank_spools_by_color(ps.slicer_hex, all_spools) if ps.slicer_hex else all_spools
            best_pk = ranked[0].pk if ranked else None
        return {"print_spool": ps, "spools": all_spools, "best_pk": best_pk}

    def get(self, request, pk):
        ps = get_object_or_404(PrintSpool, pk=pk)
        all_spools = list(Spool.objects.order_by("brand", "color_name", "material"))
        return render(request, "tracker/partials/split_slot_form.html", {
            "ps": ps,
            "all_spools": all_spools,
        })

    def post(self, request, pk):
        ps = get_object_or_404(PrintSpool, pk=pk)
        original_grams = float(ps.grams_used)

        spool_id_list = request.POST.getlist("split_spool")
        grams_list = request.POST.getlist("split_grams")

        splits, total = [], 0.0
        for spool_id, g in zip(spool_id_list, grams_list):
            try:
                grams = float(g)
            except (ValueError, TypeError):
                continue
            if grams <= 0:
                continue
            spool = None
            if spool_id:
                try:
                    spool = Spool.objects.get(pk=spool_id)
                except Spool.DoesNotExist:
                    pass
            splits.append({
                "spool": spool,
                "hex": spool.color_hex if spool else ps.slicer_hex,
                "grams": grams,
            })
            total += grams

        all_spools = list(Spool.objects.order_by("brand", "color_name", "material"))

        if len(splits) < 2:
            return render(request, "tracker/partials/split_slot_form.html", {
                "ps": ps, "all_spools": all_spools,
                "error": "Enter grams for at least 2 sub-slots.",
            })
        if abs(total - original_grams) > 0.5:
            return render(request, "tracker/partials/split_slot_form.html", {
                "ps": ps, "all_spools": all_spools,
                "error": f"Sub-slot grams total {total:.1f}g but must equal {original_grams:.1f}g.",
            })

        print_log = ps.print_log
        ps.delete()

        new_slots = []
        for split in splits:
            new_ps = PrintSpool.objects.create(
                print_log=print_log,
                grams_used=split["grams"],
                slicer_hex=split["hex"],
                spool=split["spool"],
            )
            new_slots.append(self._build_slot(new_ps, all_spools))

        return render(request, "tracker/partials/spool_slot_rows.html", {"slots": new_slots})


class ManualEntryView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "tracker/manual_entry.html", {
            "now": timezone.now().strftime("%Y-%m-%d %H:%M"),
            "prefilled_name": request.GET.get("name", ""),
            "prefilled_url": request.GET.get("source_url", ""),
        })

    def post(self, request):
        name = request.POST.get("name", "").strip()
        source_url = request.POST.get("source_url", "").strip()
        printed_at_raw = request.POST.get("printed_at", "").strip()
        grams_list = request.POST.getlist("grams_used")
        hex_list = request.POST.getlist("slicer_hex")

        if not name:
            messages.error(request, "Print name is required.")
            return render(request, "tracker/manual_entry.html", {
                "now": timezone.now().strftime("%Y-%m-%d %H:%M"),
                "prefilled_name": name,
                "prefilled_url": source_url,
            })

        slots = []
        for g, h in zip(grams_list, hex_list):
            try:
                grams = float(g)
                if grams > 0:
                    slots.append({"grams": grams, "hex": h or ""})
            except (ValueError, TypeError):
                pass

        if not slots:
            messages.error(request, "Add at least one color slot with grams > 0.")
            return render(request, "tracker/manual_entry.html", {
                "now": timezone.now().strftime("%Y-%m-%d %H:%M"),
                "prefilled_name": name,
                "prefilled_url": source_url,
            })

        try:
            from django.utils.dateparse import parse_datetime
            printed_at = parse_datetime(printed_at_raw) or timezone.now()
        except Exception:
            printed_at = timezone.now()

        print_log = PrintLog.objects.create(
            name=name[:PRINT_NAME_MAX_LENGTH],
            printed_at=printed_at,
            source="manual",
            source_url=source_url,
            status="pending_assignment",
        )
        for slot in slots:
            PrintSpool.objects.create(
                print_log=print_log,
                grams_used=slot["grams"],
                slicer_hex=slot["hex"],
            )

        return redirect("spool-assignment", pk=print_log.pk)
