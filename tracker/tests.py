import zipfile
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PrintLog, PrintSpool, Spool
from .parsers import estimate_remaining_by_layer
from .utils import rank_spools_by_material_and_color

FIXTURE_3MF = "uploads/prints/000ratonelectrico.gcode.3mf"


def _make_spool(brand="Test", material="PLA", color_name="Tan", color_hex="#E4BD68", remaining_g=1000):
    return Spool.objects.create(
        brand=brand,
        material=material,
        color_name=color_name,
        color_hex=color_hex,
        full_weight_g=1000,
        remaining_g=remaining_g,
        price_paid=Decimal("20.00"),
        purchase_date=timezone.localdate(),
    )


class RankSpoolsByMaterialAndColorTests(TestCase):
    def setUp(self):
        self.ht_pla_black = _make_spool(material="HT-PLA", color_name="Black", color_hex="#000000")
        self.pla_black = _make_spool(material="PLA", color_name="Black", color_hex="#050505")
        self.petg_red = _make_spool(material="PETG", color_name="Red", color_hex="#FF0000")

    def test_prefers_exact_material_match(self):
        spools = [self.ht_pla_black, self.pla_black, self.petg_red]
        ranked = rank_spools_by_material_and_color("#000000", "PLA", spools)
        self.assertEqual(ranked[0], self.pla_black)

    def test_material_match_is_case_insensitive(self):
        spools = [self.ht_pla_black, self.pla_black]
        ranked = rank_spools_by_material_and_color("#000000", "pla", spools)
        self.assertEqual(ranked[0], self.pla_black)

    def test_falls_back_to_pla_when_no_material_match(self):
        # Asking for a material nothing has (e.g. "ABS") should prefer PLA spools
        # over a closer-colored non-PLA spool.
        spools = [self.ht_pla_black, self.pla_black, self.petg_red]
        ranked = rank_spools_by_material_and_color("#020202", "ABS", spools)
        self.assertEqual(ranked[0], self.pla_black)

    def test_falls_back_to_all_spools_when_nothing_matches_material_or_pla(self):
        spools = [self.petg_red]
        ranked = rank_spools_by_material_and_color("#FF0000", "ABS", spools)
        self.assertEqual(ranked[0], self.petg_red)


class EstimateRemainingByLayerTests(TestCase):
    def test_remaining_fraction_decreases_monotonically_with_layer(self):
        fractions_over_time = []
        for layer in (1, 50, 200, 400):
            with open(FIXTURE_3MF, "rb") as f:
                remaining, total_layers = estimate_remaining_by_layer(f, "threemf", layer)
            self.assertIsNotNone(remaining)
            self.assertEqual(total_layers, 405)
            fractions_over_time.append(remaining[("#E4BD68", "PLA")])

        for earlier, later in zip(fractions_over_time, fractions_over_time[1:]):
            self.assertGreaterEqual(earlier, later)

    def test_colors_used_only_later_stay_fully_remaining_early_on(self):
        with open(FIXTURE_3MF, "rb") as f:
            remaining, _ = estimate_remaining_by_layer(f, "threemf", 50)
        # The white filament (5.56g total) is a small late-print detail — it should
        # not be credited as "used" this early just because layer 50 has passed.
        self.assertEqual(remaining[("#FFFFFF", "PLA")], 1.0)

    def test_final_layer_leaves_nothing_remaining(self):
        with open(FIXTURE_3MF, "rb") as f:
            remaining, total_layers = estimate_remaining_by_layer(f, "threemf", total_layers := 405)
        for fraction in remaining.values():
            self.assertEqual(fraction, 0.0)

    def test_out_of_range_layer_returns_none_with_total_layers(self):
        with open(FIXTURE_3MF, "rb") as f:
            remaining, total_layers = estimate_remaining_by_layer(f, "threemf", 9999)
        self.assertIsNone(remaining)
        self.assertEqual(total_layers, 405)


class PrintFailedViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pw")
        self.client.force_login(self.user)

        self.tan_spool = _make_spool(color_name="Tan", color_hex="#E4BD68", remaining_g=200)
        self.red_spool = _make_spool(color_name="Red", color_hex="#FF0000", remaining_g=200)
        self.black_spool = _make_spool(color_name="Black", color_hex="#000000", remaining_g=200)
        self.white_spool = _make_spool(color_name="White", color_hex="#FFFFFF", remaining_g=200)

        with open(FIXTURE_3MF, "rb") as f:
            file_bytes = f.read()

        self.print_log = PrintLog.objects.create(
            name="Test print",
            printed_at=timezone.now(),
            source="threemf",
            source_file=SimpleUploadedFile("test.gcode.3mf", file_bytes),
            status="confirmed",
        )
        PrintSpool.objects.create(print_log=self.print_log, spool=self.tan_spool, grams_used=312.26, slicer_hex="#E4BD68", slicer_material="PLA")
        PrintSpool.objects.create(print_log=self.print_log, spool=self.red_spool, grams_used=121.36, slicer_hex="#FF0000", slicer_material="PLA")
        PrintSpool.objects.create(print_log=self.print_log, spool=self.black_spool, grams_used=42.67, slicer_hex="#000000", slicer_material="PLA")
        PrintSpool.objects.create(print_log=self.print_log, spool=self.white_spool, grams_used=5.56, slicer_hex="#FFFFFF", slicer_material="PLA")

    def test_marking_failed_by_layer_returns_unused_filament_per_color(self):
        white_remaining_before = self.white_spool.remaining_g

        response = self.client.post(
            reverse("print-failed", args=[self.print_log.pk]),
            {"failed_layer": "50"},
        )
        self.assertRedirects(response, reverse("print-history"))

        self.print_log.refresh_from_db()
        self.assertEqual(self.print_log.status, "failed")
        self.assertEqual(self.print_log.failed_at_layer, 50)
        self.assertEqual(self.print_log.failed_total_layers, 405)

        self.white_spool.refresh_from_db()
        # White wasn't touched yet at layer 50 — essentially all of it should return.
        self.assertAlmostEqual(self.white_spool.remaining_g, white_remaining_before + 5.56, delta=0.01)

        self.tan_spool.refresh_from_db()
        tan_returned_fraction = (self.tan_spool.remaining_g - 200) / 312.26
        white_returned_fraction = (self.white_spool.remaining_g - white_remaining_before) / 5.56
        # Tan (the print's base/bulk color) is already well underway by layer 50, so a
        # much smaller share of it should come back than the still-untouched white.
        self.assertLess(tan_returned_fraction, white_returned_fraction)

    def test_marking_failed_by_percent_applies_uniformly(self):
        self.client.post(
            reverse("print-failed", args=[self.print_log.pk]),
            {"failed_percent": "50"},
        )
        self.print_log.refresh_from_db()
        self.assertEqual(self.print_log.status, "failed")

        for ps in self.print_log.spools_used.all():
            self.assertAlmostEqual(ps.grams_returned, ps.grams_used * 0.5, delta=0.01)

    def test_invalid_layer_number_does_not_mark_failed(self):
        self.client.post(
            reverse("print-failed", args=[self.print_log.pk]),
            {"failed_layer": "99999"},
        )
        self.print_log.refresh_from_db()
        self.assertEqual(self.print_log.status, "confirmed")

    def test_spool_credit_is_capped_at_full_weight(self):
        self.tan_spool.remaining_g = 999
        self.tan_spool.save()

        self.client.post(
            reverse("print-failed", args=[self.print_log.pk]),
            {"failed_percent": "100"},
        )
        self.tan_spool.refresh_from_db()
        self.assertLessEqual(self.tan_spool.remaining_g, self.tan_spool.full_weight_g)

    def test_print_history_page_renders_failed_print_controls(self):
        response = self.client.get(reverse("print-history"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Failed Print", html)
        self.assertIn(f'action="{reverse("print-failed", args=[self.print_log.pk])}"', html)
        self.assertIn('name="failed_layer"', html)
        self.assertIn('name="failed_percent"', html)

    def test_print_history_page_shows_failure_summary_after_marking_failed(self):
        self.client.post(reverse("print-failed", args=[self.print_log.pk]), {"failed_layer": "50"})
        response = self.client.get(reverse("print-history"))
        html = response.content.decode()
        self.assertIn("Failed", html)
        self.assertIn("Layer 50 of 405", html)
        # A failed print shouldn't still offer another "Failed Print" button.
        self.assertNotIn(f'action="{reverse("print-failed", args=[self.print_log.pk])}"', html)


class SpoolAssignmentDefaultSelectionTests(TestCase):
    """Confirms the material-aware ranking actually reaches the rendered dropdown
    selection on the real spool-assignment page, not just the utility function."""

    def setUp(self):
        self.user = User.objects.create_user(username="tester2", password="pw")
        self.client.force_login(self.user)

        # A closer-alphabetically HT-PLA black spool that should NOT win over plain
        # PLA black just because it's a nearer color match / earlier in the list.
        self.ht_pla_black = _make_spool(brand="AAA", material="HT-PLA", color_name="Black", color_hex="#0a0a0a")
        self.pla_black = _make_spool(brand="ZZZ", material="PLA", color_name="Black", color_hex="#000000")

        self.print_log = PrintLog.objects.create(
            name="Black PLA test",
            printed_at=timezone.now(),
            source="gcode",
            status="pending_assignment",
        )
        PrintSpool.objects.create(
            print_log=self.print_log,
            grams_used=50,
            slicer_hex="#000000",
            slicer_material="PLA",
        )

    def test_default_selection_prefers_matching_material_over_closer_color(self):
        response = self.client.get(reverse("spool-assignment", args=[self.print_log.pk]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        pla_option = f'<option value="{self.pla_black.pk}"'
        ht_pla_option_idx = html.find(f'<option value="{self.ht_pla_black.pk}"')
        pla_option_idx = html.find(pla_option)
        selected_idx = html.find("selected", pla_option_idx)
        # The PLA (not HT-PLA) black spool's <option> should carry `selected`.
        self.assertNotEqual(pla_option_idx, -1)
        self.assertNotEqual(ht_pla_option_idx, -1)
        self.assertTrue(0 < selected_idx - pla_option_idx < 200)
