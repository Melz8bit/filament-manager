from decimal import Decimal

from django.db import models

from .constants import LOW_STOCK_THRESHOLD_G


class FilamentProduct(models.Model):
    """Reusable product template built from scanned/entered SKUs."""
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    brand = models.CharField(max_length=100)
    material = models.CharField(max_length=50)
    color_name = models.CharField(max_length=100, blank=True)
    color_hex = models.CharField(max_length=7, default='#808080')
    full_weight_g = models.PositiveIntegerField(default=1000)
    diameter_mm = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.75'))

    class Meta:
        ordering = ['brand', 'material', 'color_name']

    def __str__(self):
        return f"{self.brand} {self.material} {self.color_name} ({self.sku})"


class Spool(models.Model):
    sku = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=100)
    material = models.CharField(max_length=50)
    color_name = models.CharField(max_length=100)
    color_hex = models.CharField(max_length=7)
    full_weight_g = models.PositiveIntegerField()
    diameter_mm = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.75'))
    remaining_g = models.FloatField()
    price_paid = models.DecimalField(max_digits=8, decimal_places=2)
    purchase_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["brand", "color_name"]

    def __str__(self):
        return f"{self.brand} {self.color_name} ({self.material})"

    @property
    def remaining_percent(self):
        if self.full_weight_g == 0:
            return 0
        return min(round((self.remaining_g / self.full_weight_g) * 100, 1), 100)

    @property
    def is_low_stock(self):
        return self.remaining_g < LOW_STOCK_THRESHOLD_G


class PrintLog(models.Model):
    name = models.CharField(max_length=200)
    printed_at = models.DateTimeField()
    source = models.CharField(
        max_length=20,
        choices=[
            ("threemf", "3MF"),
            ("gcode", "G-code"),
            ("manual", "Manual"),
            ("script", "Script"),
        ],
    )
    source_file = models.FileField(blank=True, upload_to="prints/")
    source_url = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=50,
        choices=[
            ("queued", "Queued"),
            ("pending_assignment", "Pending Assignment"),
            ("confirmed", "Confirmed"),
        ],
        default="pending_assignment",
    )
    queue_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    @property
    def total_grams_used(self):
        return sum(ps.grams_used for ps in self.spools_used.all())

    @property
    def cost_estimate(self):
        total = Decimal("0")
        for ps in self.spools_used.all():
            if ps.spool and ps.spool.full_weight_g > 0:
                total += ps.spool.price_paid / ps.spool.full_weight_g * Decimal(str(ps.grams_used))
        return total


class PrintSpool(models.Model):
    spool = models.ForeignKey(Spool, null=True, blank=True, on_delete=models.SET_NULL)
    print_log = models.ForeignKey(
        PrintLog, on_delete=models.CASCADE, related_name="spools_used"
    )
    grams_used = models.FloatField()
    slicer_hex = models.CharField(max_length=7, blank=True)
