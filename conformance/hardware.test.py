import json
import sys
import unittest
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "snes-rom-image-python"))
sys.path.insert(0, str(ROOT / "snes-rom-image-python" / "snes-mapper-python"))

import starocean

HERE = Path(__file__).resolve().parent

KILOBYTE = 1024

HEADER = 0x7FC0

SIZE_BYTE = HEADER + 23


def declared(name: str) -> dict[str, Any]:
    held = json.loads((HERE / name).read_text())
    assert isinstance(held, dict), f"{name} does not hold an object"
    return held


def an_image(size: int) -> bytes:
    rom = bytearray(size)
    rom[HEADER : HEADER + 21] = b"Star Ocean           "
    rom[HEADER + 21] = 0x32
    rom[HEADER + 22] = 0x45
    rom[SIZE_BYTE] = 0x0C
    rom[HEADER + 28 : HEADER + 32] = b"\xa5\xa5\x5a\x5a"
    return bytes(rom)


class DocumentTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.declared = declared("hardware.json")

    def test_the_authority_points_at_the_siblings_rather_than_repeating_them(self) -> None:
        # Arrange
        authority = self.declared["authority"]

        # Act
        order = authority["order"]

        # Assert
        self.assertIn("snes-rom-image-python", order[0])

    def test_and_says_why_nothing_is_copied_here(self) -> None:
        # Arrange
        record = self.declared

        # Act
        note = record["note"]

        # Assert
        self.assertIn("second source of truth", note)

    def test_what_this_package_does_not_claim_is_recorded(self) -> None:
        # Arrange
        record = self.declared

        # Act
        stated = record["notStated"]

        # Assert
        self.assertGreaterEqual(len(stated), 4)

    def test_every_fact_names_its_evidence(self) -> None:
        # Arrange
        facts = self.declared["facts"]

        # Act
        missing = [name for name, fact in facts.items() if not fact.get("evidence")]

        # Assert
        self.assertEqual(missing, [])


class ConstantTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.facts: dict[str, Any] = declared("hardware.json")["facts"]

    def test_the_declared_length_is_the_one_this_package_expects(self) -> None:
        # Arrange
        length = self.facts["imageBytes"]["value"]

        # Act
        published = starocean.EXPECTED_BYTES

        # Assert
        self.assertEqual(published, length)

    def test_and_it_is_ninety_six_megabit(self) -> None:
        # Arrange
        length = self.facts["imageBytes"]["value"]

        # Act
        megabit = length * 8 // KILOBYTE // KILOBYTE

        # Assert
        self.assertEqual(megabit, 96)

    def test_every_edition_in_the_manifest_is_that_length(self) -> None:
        # Arrange
        length = self.facts["imageBytes"]["value"]

        # Act
        wrong = [edition.name for edition in starocean.EDITIONS if edition.size != length]

        # Assert
        self.assertEqual(wrong, [])

    def test_an_image_of_another_length_is_refused_before_it_is_read(self) -> None:
        # Arrange
        length = self.facts["imageBytes"]["value"]
        edition = starocean.named("japanese")

        # Act
        with self.assertRaises(starocean.Unrecognised) as raised:
            starocean.confirm(bytes(length - 1), edition)

        # Assert
        self.assertIn(f"{length} bytes and this is {length - 1}.", str(raised.exception))

    def test_correcting_an_image_of_that_length_declares_the_recorded_size_byte(self) -> None:
        # Arrange
        image = an_image(self.facts["imageBytes"]["value"])

        # Act
        corrected = starocean.correct(image)

        # Assert
        self.assertEqual(corrected[SIZE_BYTE], self.facts["sizeByte"]["value"])

    def test_and_the_record_says_it_comes_from_a_rule_rather_than_a_row(self) -> None:
        # Arrange
        fact = self.facts["sizeByte"]

        # Act
        note = fact["note"]

        # Assert
        self.assertIn("table stops at 32 megabit", note)


class ManifestTest(unittest.TestCase):
    def test_every_edition_names_a_file_before_and_after(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        missing = [edition.name for edition in catalogue if not (edition.reads and edition.writes)]

        # Assert
        self.assertEqual(missing, [])

    def test_every_edition_carries_four_digests_at_each_end(self) -> None:
        # Arrange
        four = ["crc32", "md5", "sha1", "sha256"]

        # Act
        held = [
            sorted(held)
            for edition in starocean.EDITIONS
            for held in (edition.before, edition.after)
        ]

        # Assert
        self.assertEqual(held, [four] * 4)

    def test_only_one_of_the_four_decides(self) -> None:
        # Arrange
        expected = "sha256"

        # Act
        published = starocean.DECIDES

        # Assert
        self.assertEqual(published, expected)

    def test_and_it_is_the_widest_of_them(self) -> None:
        # Arrange
        widths = starocean.DIGEST_WIDTHS

        # Act
        widest = max(widths, key=lambda name: widths[name])

        # Assert
        self.assertEqual(widest, "sha256")

    def test_no_two_editions_read_the_same_file(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        reads = [edition.reads for edition in catalogue]

        # Assert
        self.assertEqual(len(set(reads)), len(reads))

    def test_and_no_two_produce_the_same_result(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        after = [edition.after["sha256"] for edition in catalogue]

        # Assert
        self.assertEqual(len(set(after)), len(after))


class DivergenceTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries: list[dict[str, Any]] = declared("divergences.json")["divergences"]

    def test_each_entry_says_which_source_the_package_follows(self) -> None:
        # Arrange
        allowed = {"document", "reference", "neither"}

        # Act
        followed = {entry["packageFollows"] for entry in self.entries}

        # Assert
        self.assertEqual(followed - allowed, set())

    def test_each_entry_says_what_would_settle_it(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        missing = [entry["id"] for entry in entries if not entry.get("wouldSettleIt")]

        # Assert
        self.assertEqual(missing, [])

    def test_the_input_being_a_hack_is_recorded_as_a_boundary(self) -> None:
        # Arrange
        wanted = "the-input-is-a-hack-and-that-is-the-point"

        # Act
        entry = next(item for item in self.entries if item["id"] == wanted)

        # Assert
        self.assertIn("it is the subject", entry["reasoning"])

    def test_and_that_this_package_models_no_hardware(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        named = {entry["id"] for entry in entries}

        # Assert
        self.assertIn("nothing-here-models-hardware", named)


if __name__ == "__main__":
    unittest.main(verbosity=1)
