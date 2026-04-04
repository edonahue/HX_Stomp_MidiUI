"""
test_tone_manager.py

Test suite for tone_manager.py.
Covers Tone data model and ToneManager CRUD + persistence.

Run with:
    python -m unittest test_tone_manager -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tone_manager import Tone, ToneManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tone(name="Test Tone", preset=10, snapshot=0, category=None):
    return Tone(name=name, preset=preset, snapshot=snapshot, category=category)


# ===========================================================================
# Group A: ToneManager CRUD
# ===========================================================================

class TestToneManagerCRUD(unittest.TestCase):

    def setUp(self):
        # Use a non-existent path so no file is loaded on construction
        self.tm = ToneManager(filepath="/tmp/nonexistent_test_tones_xyz.json")

    # --- add / get ---

    def test_add_and_get(self):
        t = _make_tone("Alpha")
        self.tm.add(t)
        result = self.tm.get("Alpha")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Alpha")
        self.assertEqual(result.preset, 10)

    def test_add_duplicate_raises(self):
        self.tm.add(_make_tone("Dup"))
        with self.assertRaises(ValueError):
            self.tm.add(_make_tone("Dup"))

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.tm.get("nonexistent"))

    # --- update ---

    def test_update_existing(self):
        self.tm.add(_make_tone("Beta", preset=5))
        updated = Tone(name="Beta", preset=99)
        self.tm.update(updated)
        self.assertEqual(self.tm.get("Beta").preset, 99)

    def test_update_missing_raises(self):
        with self.assertRaises(KeyError):
            self.tm.update(_make_tone("Ghost"))

    # --- remove ---

    def test_remove_existing(self):
        self.tm.add(_make_tone("Gamma"))
        self.tm.remove("Gamma")
        self.assertEqual(self.tm.tones, [])

    def test_remove_missing_raises(self):
        with self.assertRaises(KeyError):
            self.tm.remove("NoSuchTone")

    # --- tones property ---

    def test_tones_property_is_copy(self):
        self.tm.add(_make_tone("Delta"))
        lst = self.tm.tones
        lst.clear()
        self.assertEqual(len(self.tm.tones), 1)

    # --- categories ---

    def test_categories_order_preserved(self):
        self.tm.add(Tone("A", 1, category="Rock"))
        self.tm.add(Tone("B", 2, category="Jazz"))
        self.tm.add(Tone("C", 3, category="Rock"))
        cats = self.tm.categories()
        self.assertEqual(cats, ["Rock", "Jazz"])

    def test_categories_uncategorized_fallback(self):
        self.tm.add(Tone("A", 1, category=None))
        self.assertIn("Uncategorized", self.tm.categories())

    def test_tones_by_category(self):
        self.tm.add(Tone("A", 1, category="Rock"))
        self.tm.add(Tone("B", 2, category="Jazz"))
        self.tm.add(Tone("C", 3, category="Rock"))
        groups = self.tm.tones_by_category()
        self.assertEqual(len(groups["Rock"]), 2)
        self.assertEqual(len(groups["Jazz"]), 1)

    # --- validation on add ---

    def test_add_validates_tone(self):
        with self.assertRaises(ValueError):
            self.tm.add(Tone("X", preset=200))

    # --- empty manager ---

    def test_empty_manager_tones(self):
        self.assertEqual(self.tm.tones, [])


# ===========================================================================
# Group B: ToneManager persistence
# ===========================================================================

class TestToneManagerPersistence(unittest.TestCase):

    def _tmpfile(self):
        """Return a path to a temp file that does NOT exist yet."""
        f = tempfile.NamedTemporaryFile(suffix=".json", delete=True)
        path = f.name
        f.close()
        return Path(path)

    def test_save_and_reload(self):
        path = self._tmpfile()
        tm = ToneManager(filepath=path)
        tm.add(Tone("SaveMe", preset=42, snapshot=2, category="Blues"))
        tm.save()
        tm2 = ToneManager(filepath=path)
        t = tm2.get("SaveMe")
        self.assertIsNotNone(t)
        self.assertEqual(t.preset, 42)
        self.assertEqual(t.snapshot, 2)
        self.assertEqual(t.category, "Blues")

    def test_save_creates_valid_json(self):
        path = self._tmpfile()
        tm = ToneManager(filepath=path)
        tm.add(Tone("Valid", preset=0))
        tm.save()
        data = json.loads(path.read_text())
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    def test_load_bad_json_raises(self):
        path = self._tmpfile()
        path.write_text("not valid json at all")
        with self.assertRaises(ValueError):
            ToneManager(filepath=path)

    def test_load_missing_name_raises(self):
        path = self._tmpfile()
        path.write_text(json.dumps([{"preset": 1}]))
        with self.assertRaises(ValueError):
            ToneManager(filepath=path)

    def test_load_optional_fields_default(self):
        path = self._tmpfile()
        path.write_text(json.dumps([{"name": "Minimal", "preset": 5}]))
        tm = ToneManager(filepath=path)
        t = tm.get("Minimal")
        self.assertEqual(t.color, "#4A90D9")
        self.assertEqual(t.snapshot, 0)

    def test_reload_replaces_state(self):
        path = self._tmpfile()
        tm = ToneManager(filepath=path)
        tm.add(Tone("Original", preset=1))
        tm.save()
        tm.add(Tone("Extra", preset=2))
        self.assertEqual(len(tm.tones), 2)
        tm.reload()
        self.assertEqual(len(tm.tones), 1)
        self.assertIsNone(tm.get("Extra"))

    def test_save_drops_none_category(self):
        path = self._tmpfile()
        tm = ToneManager(filepath=path)
        tm.add(Tone("NoCat", preset=3, category=None))
        tm.save()
        data = json.loads(path.read_text())
        self.assertNotIn("category", data[0])

    # --- validate-on-load ---

    def test_load_invalid_preset_raises(self):
        path = self._tmpfile()
        path.write_text(json.dumps([{"name": "Bad", "preset": 200}]))
        with self.assertRaises(ValueError) as cm:
            ToneManager(filepath=path)
        self.assertIn("Bad", str(cm.exception))
        self.assertIn("preset", str(cm.exception))

    def test_load_invalid_snapshot_raises(self):
        path = self._tmpfile()
        path.write_text(json.dumps([{"name": "BadSnap", "preset": 0, "snapshot": 8}]))
        with self.assertRaises(ValueError) as cm:
            ToneManager(filepath=path)
        self.assertIn("BadSnap", str(cm.exception))
        self.assertIn("snapshot", str(cm.exception))

    # --- create_empty ---

    def test_create_empty_has_no_tones(self):
        tm = ToneManager.create_empty("/tmp/_hxstomp_test_empty.json")
        self.assertEqual(tm.tones, [])

    def test_create_empty_filepath_set(self):
        tm = ToneManager.create_empty("/tmp/_hxstomp_test_empty.json")
        self.assertEqual(tm.filepath, Path("/tmp/_hxstomp_test_empty.json"))

    def test_create_empty_save_works(self):
        path = self._tmpfile()
        tm = ToneManager.create_empty(path)
        tm.add(Tone("Fresh", preset=5))
        tm.save()
        tm2 = ToneManager(filepath=path)
        self.assertIsNotNone(tm2.get("Fresh"))


# ===========================================================================
# Group C: Tone data model
# ===========================================================================

class TestToneDataModel(unittest.TestCase):

    def test_to_dict_drops_none(self):
        t = Tone("X", preset=1, category=None)
        d = t.to_dict()
        self.assertNotIn("category", d)

    def test_to_dict_keeps_category(self):
        t = Tone("X", preset=1, category="Lead")
        d = t.to_dict()
        self.assertEqual(d["category"], "Lead")

    def test_to_dict_has_required_keys(self):
        t = Tone("X", preset=1)
        d = t.to_dict()
        for key in ("name", "preset", "snapshot", "bank_msb", "bank_lsb", "color"):
            self.assertIn(key, d)

    def test_from_dict_all_fields(self):
        d = {
            "name": "Full", "preset": 7, "snapshot": 3,
            "bank_msb": 1, "bank_lsb": 2, "color": "#aabbcc", "category": "Metal"
        }
        t = Tone.from_dict(d)
        self.assertEqual(t.name, "Full")
        self.assertEqual(t.preset, 7)
        self.assertEqual(t.snapshot, 3)
        self.assertEqual(t.bank_msb, 1)
        self.assertEqual(t.bank_lsb, 2)
        self.assertEqual(t.color, "#aabbcc")
        self.assertEqual(t.category, "Metal")

    def test_from_dict_missing_optionals(self):
        t = Tone.from_dict({"name": "Min", "preset": 0})
        self.assertEqual(t.snapshot, 0)
        self.assertEqual(t.bank_msb, 0)
        self.assertEqual(t.bank_lsb, 0)
        self.assertEqual(t.color, "#4A90D9")
        self.assertIsNone(t.category)

    def test_validate_bank_lsb_boundary(self):
        t = Tone("X", preset=0, bank_lsb=127)
        t.validate()  # should not raise

    def test_validate_snapshot_max_valid(self):
        t = Tone("X", preset=0, snapshot=7)
        t.validate()  # 7 is valid

    def test_validate_snapshot_8_raises(self):
        t = Tone("X", preset=0, snapshot=8)
        with self.assertRaises(ValueError):
            t.validate()

    def test_validate_preset_boundary_127(self):
        t = Tone("X", preset=127)
        t.validate()  # should not raise

    def test_validate_preset_boundary_128_raises(self):
        t = Tone("X", preset=128)
        with self.assertRaises(ValueError):
            t.validate()

    def test_round_trip_from_dict_to_dict(self):
        original = Tone("RoundTrip", preset=55, snapshot=2, category="Funk")
        d = original.to_dict()
        restored = Tone.from_dict(d)
        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.preset, original.preset)
        self.assertEqual(restored.category, original.category)


if __name__ == "__main__":
    unittest.main()
