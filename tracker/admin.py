from django.contrib import admin
from .models import Spool, FilamentProduct, PrintLog, PrintSpool


@admin.register(FilamentProduct)
class FilamentProductAdmin(admin.ModelAdmin):
    list_display = ['sku', 'brand', 'material', 'color_name', 'full_weight_g', 'diameter_mm']
    search_fields = ['sku', 'brand', 'material', 'color_name']
    ordering = ['brand', 'material', 'color_name']


@admin.register(Spool)
class SpoolAdmin(admin.ModelAdmin):
    list_display = ['brand', 'material', 'color_name', 'remaining_g', 'full_weight_g', 'sku']
    search_fields = ['brand', 'material', 'color_name', 'sku']
    list_filter = ['material', 'brand']


@admin.register(PrintLog)
class PrintLogAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'created_at']
    list_filter = ['status']


@admin.register(PrintSpool)
class PrintSpoolAdmin(admin.ModelAdmin):
    list_display = ['print_log', 'spool', 'grams_used']
