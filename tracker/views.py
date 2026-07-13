import html as html_lib
import json
import re
import urllib.request

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.views import View
from django.contrib.auth.views import PasswordChangeView
from django.views.generic import ListView, CreateView, UpdateView

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Sum

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
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")
    segment = parsed.path.rstrip("/").split("/")[-1]

    if host in ("makerworld.com", "printables.com"):
        # paths like /en/models/2599617-parametric-organizer or /model/123456-my-model
        name = re.sub(r"^\d+-", "", segment)
        return name.replace("-", " ").title() if name else ""

    if host == "thingiverse.com":
        # paths like /thing:123456  — no name in slug, skip
        return ""

    return ""


def _fetch_page_title(url):
    # Try slug extraction first (instant, no network needed)
    title = _title_from_url_slug(url)
    if title:
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

from .constants import LOW_STOCK_THRESHOLD_G
from .parsers import parse_3mf, parse_gcode
from .utils import parse_filament_product, is_filament_product, rank_spools_by_color


@login_required
def dashboard(request):
    low_stock_spools = Spool.objects.filter(remaining_g__lt=LOW_STOCK_THRESHOLD_G).order_by("remaining_g")
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
        qs = Spool.objects.all()
        if brand := self.request.GET.get("brand"):
            qs = qs.filter(brand=brand)
        if material := self.request.GET.get("material"):
            qs = qs.filter(material=material)
        if color := self.request.GET.get("color"):
            qs = qs.filter(color_name__icontains=color)
        if self.request.GET.get("low_stock"):
            qs = qs.filter(remaining_g__lt=LOW_STOCK_THRESHOLD_G)
        order = self._SORT_MAP.get(self.request.GET.get("sort", "brand_asc"), ("brand", "color_name"))
        return qs.order_by(*order)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["brands"] = Spool.objects.values_list("brand", flat=True).distinct().order_by("brand")
        ctx["materials"] = Spool.objects.values_list("material", flat=True).distinct().order_by("material")
        ctx["total_count"] = Spool.objects.count()
        ctx["f"] = self.request.GET
        return ctx


class SpoolCreateView(LoginRequiredMixin, CreateView):
    model = Spool
    form_class = SpoolForm
    template_name = "tracker/spool_form.html"
    success_url = reverse_lazy("spool-list")

    def get_context_data(self, **kwargs):
        return super().get_context_data(title="Add Spool", **kwargs)

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


class LogPrintView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "tracker/log_print.html")

    def post(self, request):
        uploaded_file = request.FILES.get("source_file")
        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return render(request, "tracker/log_print.html")

        name = uploaded_file.name.lower()
        if name.endswith(".3mf"):
            source = "threemf"
            slots = parse_3mf(uploaded_file)
        elif name.endswith(".gcode"):
            source = "gcode"
            slots = parse_gcode(uploaded_file)
        else:
            messages.error(
                request, "Unsupported file type. Upload a .3mf or .gcode file."
            )
            return render(request, "tracker/log_print.html")

        if not slots:
            messages.error(request, "No filament data found in that file.")
            return render(request, "tracker/log_print.html")

        print_log = PrintLog.objects.create(
            name=request.POST.get("name", "").strip() or uploaded_file.name,
            printed_at=timezone.now(),
            source=source,
            source_file=uploaded_file,
            status="pending_assignment",
        )

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
        all_spools = Spool.objects.all()
        slots = []
        for ps in print_log.spools_used.all():
            ranked = (
                rank_spools_by_color(ps.slicer_hex, all_spools)
                if ps.slicer_hex
                else list(all_spools)
            )
            slots.append({"print_spool": ps, "ranked_spools": ranked})
        return render(request, "tracker/spool_assignment.html", {
            "print_log": print_log,
            "slots": slots,
        })

    def post(self, request, pk):
        print_log = get_object_or_404(PrintLog, pk=pk)
        with transaction.atomic():
            for ps in print_log.spools_used.all():
                spool_id = request.POST.get(f"spool_{ps.pk}")
                if spool_id:
                    spool = get_object_or_404(Spool, pk=spool_id)
                    spool.remaining_g = max(0, spool.remaining_g - ps.grams_used)
                    spool.save()
                    ps.spool = spool
                    ps.save()
            print_log.status = "confirmed"
            print_log.save()
        messages.success(request, f'"{print_log.name}" confirmed. Inventory updated.')
        return redirect("spool-list")


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

        PrintLog.objects.create(
            name=name or url,
            printed_at=timezone.now(),
            source="threemf",
            source_url=url,
            queue_notes=notes,
            status="queued",
        )
        messages.success(request, "Added to queue.")
        return redirect("queue-list")


class QueueUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        print_log = get_object_or_404(PrintLog, pk=pk, status="queued")
        uploaded_file = request.FILES.get("source_file")

        if not uploaded_file:
            messages.error(request, "Please select a file.")
            return redirect("queue-list")

        name = uploaded_file.name.lower()
        if name.endswith(".3mf"):
            source = "threemf"
            slots = parse_3mf(uploaded_file)
        elif name.endswith(".gcode"):
            source = "gcode"
            slots = parse_gcode(uploaded_file)
        else:
            messages.error(request, "Unsupported file type. Upload a .3mf or .gcode file.")
            return redirect("queue-list")

        if not slots:
            messages.error(request, "No filament data found in that file.")
            return redirect("queue-list")

        print_log.source = source
        print_log.source_file = uploaded_file
        print_log.status = "pending_assignment"
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
        entry.name = name or url
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
        title = _fetch_page_title(url) if url else ""
        return HttpResponse(format_html(
            '<input type="text" id="name" name="name" value="{}" '
            'placeholder="e.g. Articulated Dragon" '
            'class="block w-full rounded-md border-gray-300 shadow-sm '
            'focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">',
            title,
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


class ManualEntryView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "tracker/manual_entry.html", {
            "now": timezone.now().strftime("%Y-%m-%d %H:%M"),
        })

    def post(self, request):
        name = request.POST.get("name", "").strip()
        printed_at_raw = request.POST.get("printed_at", "").strip()
        grams_list = request.POST.getlist("grams_used")
        hex_list = request.POST.getlist("slicer_hex")

        if not name:
            messages.error(request, "Print name is required.")
            return render(request, "tracker/manual_entry.html", {
                "now": timezone.now().strftime("%Y-%m-%d %H:%M"),
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
            })

        try:
            from django.utils.dateparse import parse_datetime
            printed_at = parse_datetime(printed_at_raw) or timezone.now()
        except Exception:
            printed_at = timezone.now()

        print_log = PrintLog.objects.create(
            name=name,
            printed_at=printed_at,
            source="manual",
            status="pending_assignment",
        )
        for slot in slots:
            PrintSpool.objects.create(
                print_log=print_log,
                grams_used=slot["grams"],
                slicer_hex=slot["hex"],
            )

        return redirect("spool-assignment", pk=print_log.pk)
