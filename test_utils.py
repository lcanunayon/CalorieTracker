"""
Tests for the calorie estimation utility (utils.py).

Runs entirely offline — no real image files or network calls needed.
Uses monkeypatching to inject controlled inputs for each code path.
"""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal PIL stub so the module imports even without Pillow installed
# ---------------------------------------------------------------------------
if 'PIL' not in sys.modules:
    pil_stub = types.ModuleType('PIL')
    image_stub = types.ModuleType('PIL.Image')
    stat_stub  = types.ModuleType('PIL.ImageStat')

    class _FakeImage:
        def convert(self, *a, **kw):  return self
        def resize(self, *a, **kw):   return self
        def point(self, fn):
            self._point_fn = fn
            return self
        def getdata(self):            return []

    class _FakeStat:
        def __init__(self, img):
            self.mean = [128.0]

    image_stub.Image = _FakeImage
    image_stub.open  = lambda *a, **kw: _FakeImage()
    stat_stub.Stat   = _FakeStat

    pil_stub.Image     = image_stub
    pil_stub.ImageStat = stat_stub
    sys.modules['PIL']           = pil_stub
    sys.modules['PIL.Image']     = image_stub
    sys.modules['PIL.ImageStat'] = stat_stub

import utils  # noqa: E402 — must come after stub injection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_path(name: str) -> str:
    """Return a fake absolute path whose basename is *name*."""
    return os.path.join('/tmp', name)


# ---------------------------------------------------------------------------
# 1. Filename label extraction (_label_from_filename)
# ---------------------------------------------------------------------------

class TestLabelFromFilename(unittest.TestCase):

    def test_exact_keyword(self):
        self.assertEqual(utils._label_from_filename('pizza.jpg'), 'pizza')

    def test_keyword_with_prefix(self):
        self.assertEqual(utils._label_from_filename('my_pizza_photo.jpg'), 'pizza')

    def test_hyphen_separated(self):
        self.assertEqual(utils._label_from_filename('french-fries.png'), 'french_fries')

    def test_mixed_case(self):
        self.assertEqual(utils._label_from_filename('BANANA.JPG'), 'banana')

    def test_no_match_returns_none(self):
        self.assertIsNone(utils._label_from_filename('IMG_20240101.jpg'))

    def test_empty_filename_returns_none(self):
        self.assertIsNone(utils._label_from_filename(''))

    def test_none_filename_returns_none(self):
        self.assertIsNone(utils._label_from_filename(None))

    def test_partial_match(self):
        # 'egg' is a substring of 'eggs_benedict'
        self.assertEqual(utils._label_from_filename('eggs_benedict.jpg'), 'egg')


# ---------------------------------------------------------------------------
# 2. estimate_calories — filename heuristic path (no HF key, with img)
# ---------------------------------------------------------------------------

class TestEstimateCaloriesFilenameHeuristic(unittest.TestCase):

    def _run(self, filename, area_proportion=0.15):
        """
        Patch out HF call (returns None), Image.open (returns mock),
        and _area_proportion to return a controlled value.
        """
        fake_img = MagicMock()
        with patch.object(utils, '_call_hf_inference', return_value=None), \
             patch('PIL.Image.open', return_value=fake_img), \
             patch.object(utils, '_area_proportion', return_value=area_proportion):
            return utils.estimate_calories(_make_path(filename))

    # ── known foods ──────────────────────────────────────────────────────────

    def test_pizza_label_and_plausible_calories(self):
        label, cal, conf = self._run('pizza.jpg')
        self.assertEqual(label, 'pizza')
        self.assertGreater(cal, 0)
        self.assertLess(cal, 1000)

    def test_salad_lower_than_steak(self):
        _, salad_cal, _ = self._run('salad.jpg', area_proportion=0.15)
        _, steak_cal, _ = self._run('steak.jpg', area_proportion=0.15)
        self.assertLess(salad_cal, steak_cal)

    def test_banana_calories(self):
        label, cal, _ = self._run('banana.jpg')
        self.assertEqual(label, 'banana')
        # base = 105, mult depends on area_proportion (0.15 → 1.1) → ~116
        self.assertAlmostEqual(cal, round(105 * 1.1), delta=20)

    def test_apple_calories(self):
        label, cal, _ = self._run('apple.png')
        self.assertEqual(label, 'apple')
        self.assertGreater(cal, 0)

    # ── portion-size multiplier ──────────────────────────────────────────────

    def test_large_portion_increases_calories(self):
        _, cal_small, _ = self._run('pizza.jpg', area_proportion=0.05)
        _, cal_large, _ = self._run('pizza.jpg', area_proportion=0.30)
        self.assertGreater(cal_large, cal_small)

    def test_exact_small_portion(self):
        # prop 0.05 → mult 0.8
        _, cal, _ = self._run('pizza.jpg', area_proportion=0.05)
        expected = round(utils.CALORIE_MAP['pizza'] * 0.8)
        self.assertEqual(cal, expected)

    def test_exact_medium_portion(self):
        # prop 0.15 → mult 1.1  (0.12 < 0.15 <= 0.25)
        _, cal, _ = self._run('pizza.jpg', area_proportion=0.15)
        expected = round(utils.CALORIE_MAP['pizza'] * 1.1)
        self.assertEqual(cal, expected)

    def test_exact_large_portion(self):
        # prop 0.30 → mult 1.6  (> 0.25)
        _, cal, _ = self._run('pizza.jpg', area_proportion=0.30)
        expected = round(utils.CALORIE_MAP['pizza'] * 1.6)
        self.assertEqual(cal, expected)

    # ── confidence ───────────────────────────────────────────────────────────

    def test_confidence_with_image_is_0_75(self):
        _, _, conf = self._run('pizza.jpg')
        self.assertAlmostEqual(conf, 0.75)

    def test_confidence_without_image_is_0_7(self):
        with patch.object(utils, '_call_hf_inference', return_value=None), \
             patch('PIL.Image.open', side_effect=IOError('no file')):
            _, _, conf = utils.estimate_calories(_make_path('pizza.jpg'))
        self.assertAlmostEqual(conf, 0.7)


# ---------------------------------------------------------------------------
# 3. estimate_calories — no filename match, image color heuristic
# ---------------------------------------------------------------------------

class TestEstimateCaloriesColorHeuristic(unittest.TestCase):

    def _run_with_color(self, r, g, b, area_proportion=0.15):
        fake_img = MagicMock()
        fake_stat = MagicMock()
        fake_stat.mean = [r, g, b]
        with patch.object(utils, '_call_hf_inference', return_value=None), \
             patch('PIL.Image.open', return_value=fake_img), \
             patch('PIL.ImageStat.Stat', return_value=fake_stat), \
             patch.object(utils, '_area_proportion', return_value=area_proportion):
            return utils.estimate_calories(_make_path('IMG_001.jpg'))

    def test_yellow_hue_detected_as_banana(self):
        # r>120, g>110, b<100 → banana
        label, _, _ = self._run_with_color(r=180, g=160, b=60)
        self.assertEqual(label, 'banana')

    def test_non_yellow_detected_as_meal(self):
        label, _, _ = self._run_with_color(r=80, g=80, b=200)
        self.assertEqual(label, 'meal')

    def test_meal_default_300_base(self):
        _, cal, _ = self._run_with_color(r=80, g=80, b=200, area_proportion=0.05)
        # base 300, mult 0.85
        self.assertEqual(cal, round(300 * 0.85))

    def test_confidence_is_0_45(self):
        _, _, conf = self._run_with_color(r=80, g=80, b=200)
        self.assertAlmostEqual(conf, 0.45)


# ---------------------------------------------------------------------------
# 4. estimate_calories — Hugging Face API path
# ---------------------------------------------------------------------------

class TestEstimateCaloriesHuggingFace(unittest.TestCase):

    def _run_hf(self, hf_results):
        with patch.object(utils, '_call_hf_inference', return_value=hf_results):
            return utils.estimate_calories(_make_path('food.jpg'))

    def test_hf_known_label_maps_to_calories(self):
        label, cal, conf = self._run_hf([('pizza', 0.92)])
        self.assertEqual(label, 'pizza')
        self.assertGreater(cal, 0)
        self.assertAlmostEqual(conf, 0.92)

    def test_hf_unknown_label_returns_300_default(self):
        _, cal, _ = self._run_hf([('xylophone', 0.9)])
        self.assertEqual(cal, 300)

    def test_hf_high_confidence_scales_up(self):
        _, cal_low,  _ = self._run_hf([('pizza', 0.01)])
        _, cal_high, _ = self._run_hf([('pizza', 1.0)])
        self.assertLess(cal_low, cal_high)

    def test_hf_label_with_spaces(self):
        # HF sometimes returns "french fries" with spaces
        label, cal, _ = self._run_hf([('french fries', 0.85)])
        self.assertGreater(cal, 0)

    def test_hf_unavailable_falls_back_to_heuristic(self):
        # _call_hf_inference returns None → falls back to filename
        fake_img = MagicMock()
        with patch.object(utils, '_call_hf_inference', return_value=None), \
             patch('PIL.Image.open', return_value=fake_img), \
             patch.object(utils, '_area_proportion', return_value=0.15):
            label, cal, _ = utils.estimate_calories(_make_path('pizza.jpg'))
        self.assertEqual(label, 'pizza')


# ---------------------------------------------------------------------------
# 5. estimate_calories — final fallback (no image, no filename match)
# ---------------------------------------------------------------------------

class TestEstimateCaloriesFallback(unittest.TestCase):

    def test_unknown_label_and_300_calories(self):
        with patch.object(utils, '_call_hf_inference', return_value=None), \
             patch('PIL.Image.open', side_effect=IOError):
            label, cal, conf = utils.estimate_calories(_make_path('IMG_001.jpg'))
        self.assertEqual(label, 'unknown')
        self.assertEqual(cal, 300)
        self.assertAlmostEqual(conf, 0.4)


# ---------------------------------------------------------------------------
# 6. CALORIE_MAP sanity checks
# ---------------------------------------------------------------------------

class TestCalorieMap(unittest.TestCase):

    def test_all_values_positive(self):
        for food, cal in utils.CALORIE_MAP.items():
            with self.subTest(food=food):
                self.assertGreater(cal, 0, f"{food} should have positive calories")

    def test_salad_less_than_cheeseburger(self):
        self.assertLess(utils.CALORIE_MAP['salad'], utils.CALORIE_MAP['cheeseburger'])

    def test_apple_less_than_cake(self):
        self.assertLess(utils.CALORIE_MAP['apple'], utils.CALORIE_MAP['cake'])

    def test_known_foods_present(self):
        expected = ['pizza', 'banana', 'apple', 'salad', 'steak', 'rice']
        for food in expected:
            self.assertIn(food, utils.CALORIE_MAP)


if __name__ == '__main__':
    unittest.main(verbosity=2)
