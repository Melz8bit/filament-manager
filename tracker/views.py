from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView

from .forms import SpoolForm
from .models import Spool, PrintLog, PrintSpool
from .parsers import parse_3mf, parse_gcode


@login_required
def dashboard(request):
    return render(request, "tracker/dashboard.html")


class SpoolListView(LoginRequiredMixin, ListView):
    model = Spool
    template_name = "tracker/spool_list.html"
    context_object_name = "spools"


class SpoolCreateView(LoginRequiredMixin, CreateView):
    model = Spool
    form_class = SpoolForm
    template_name = "tracker/spool_form.html"
    success_url = reverse_lazy("spool-list")

    def get_context_data(self, **kwargs):
        return super().get_context_data(title="Add Spool", **kwargs)


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

        return redirect("spool-list")
