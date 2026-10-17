import hashlib
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import starocean
from starocean import fix

HEADER = 0x7FC0


def an_image(
    size: int = 0x100000, chipset: int = 0x45, declared: int = 0x0D, at: int = HEADER
) -> bytes:
    rom = bytearray(size)
    rom[at : at + 21] = b"Star Ocean           "
    rom[at + 21] = 0x32
    rom[at + 22] = chipset
    rom[at + 23] = declared
    rom[at + 25] = 0x00
    rom[at + 28] = 0xA5
    rom[at + 29] = 0xA5
    rom[at + 30] = 0x5A
    rom[at + 31] = 0x5A
    return bytes(rom)


def digests_of(blob: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(blob) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(blob).hexdigest(),
        "sha1": hashlib.sha1(blob).hexdigest(),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def a_link(blob: bytes, name: str) -> dict[str, Any]:
    return dict(digests_of(blob), bytes=len(blob), name=name)


def an_edition(
    before: bytes, after: bytes, name: str = "made-up", size: int = 0x100000
) -> starocean.Edition:
    return starocean.Edition(
        name=name,
        summary="a stand-in",
        reads="in.sfc",
        writes="out.sfc",
        size=size,
        before=digests_of(before),
        after=digests_of(after),
        source=a_link(b"a cartridge" * 8, "cartridge.sfc"),
        patch=a_link(b"a patch" * 8, "patch.xdelta"),
    )


class DigestTest(unittest.TestCase):
    def test_all_four_digests_are_computed(self) -> None:
        # Arrange
        blob = b"anything"

        # Act
        found = starocean.digests_of(blob)

        # Assert
        self.assertEqual(found, digests_of(blob))

    def test_each_matches_a_worked_example(self) -> None:
        # Arrange
        blob = b"abc"

        # Act
        found = starocean.digests_of(blob)

        # Assert
        self.assertEqual(
            found,
            {
                "crc32": "352441c2",
                "md5": "900150983cd24fb0d6963f7d28e17f72",
                "sha1": "a9993e364706816aba3e25717850c26c9cd0d89d",
                "sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            },
        )


class CorrectTest(unittest.TestCase):
    def test_the_coprocessor_claim_is_cleared(self) -> None:
        # Arrange
        image = an_image()

        # Act
        corrected = starocean.correct(image)

        # Assert
        self.assertEqual(corrected[HEADER + 22], 0x00)

    def test_the_declared_size_is_made_to_match_the_file(self) -> None:
        # Arrange
        image = an_image(size=0x100000, declared=0x0D)

        # Act
        corrected = starocean.correct(image)

        # Assert
        self.assertEqual(corrected[HEADER + 23], 0x0A)

    def test_the_checksum_is_recomputed_over_the_result(self) -> None:
        # Arrange
        image = an_image()

        # Act
        corrected = starocean.correct(image)

        # Assert
        low = corrected[HEADER + 30] | (corrected[HEADER + 31] << 8)
        complement = corrected[HEADER + 28] | (corrected[HEADER + 29] << 8)
        self.assertEqual(low ^ complement, 0xFFFF)

    def test_an_image_needing_nothing_comes_back_unchanged(self) -> None:
        # Arrange
        already = starocean.correct(an_image(chipset=0x00, declared=0x0A))

        # Act
        again = starocean.correct(already)

        # Assert
        self.assertEqual(again, already)

    def test_correcting_twice_changes_nothing_the_second_time(self) -> None:
        # Arrange
        once = starocean.correct(an_image())

        # Act
        twice = starocean.correct(once)

        # Assert
        self.assertEqual(twice, once)

    def test_an_image_with_no_header_is_refused(self) -> None:
        # Arrange
        blank = bytes(0x100000)

        # Act
        attempt = lambda: starocean.correct(blank)  # noqa: E731

        # Assert
        self.assertRaises(starocean.NotACartridge, attempt)


class ConfirmTest(unittest.TestCase):
    def test_an_image_the_manifest_knows_is_accepted(self) -> None:
        # Arrange
        before = an_image()
        edition = an_edition(before, starocean.correct(before))

        # Act
        confirmed = starocean.confirm(before, edition)

        # Assert
        self.assertIs(confirmed, edition)

    def test_an_image_of_the_wrong_length_is_refused_before_it_is_hashed(self) -> None:
        # Arrange
        before = an_image()
        edition = an_edition(before, starocean.correct(before), size=0x200000)

        # Act
        with self.assertRaises(starocean.Unrecognised) as raised:
            starocean.confirm(before, edition)

        # Assert
        self.assertIn("bytes", str(raised.exception))

    def test_an_image_of_the_right_length_and_wrong_content_is_refused(self) -> None:
        # Arrange
        before = an_image()
        edition = an_edition(an_image(declared=0x0B), starocean.correct(before))

        # Act
        with self.assertRaises(starocean.Unrecognised) as raised:
            starocean.confirm(before, edition)

        # Assert
        self.assertIn("sha256", str(raised.exception))

    def test_a_manifest_that_disagrees_with_itself_is_reported_as_that(self) -> None:
        # Arrange
        before = an_image()
        edition = an_edition(before, starocean.correct(before))
        edition.before = dict(edition.before, crc32="00000000")

        # Act
        with self.assertRaises(starocean.Corrupt) as raised:
            starocean.confirm(before, edition)

        # Assert
        self.assertIn("crc32", str(raised.exception))

    def test_every_kind_of_disagreement_is_caught(self) -> None:
        # Arrange
        before = an_image()
        wrong = (("md5", "0" * 32), ("sha1", "0" * 40), ("crc32", "0" * 8))
        disagreeing = []
        for name, value in wrong:
            edition = an_edition(before, starocean.correct(before))
            edition.before = dict(edition.before, **{name: value})
            disagreeing.append((name, edition))

        # Act
        caught = []
        for name, edition in disagreeing:
            with self.assertRaises(starocean.Corrupt) as raised:
                starocean.confirm(before, edition)
            caught.append(name in str(raised.exception))

        # Assert
        self.assertEqual(caught, [True, True, True])


class ApplyTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.before = an_image()
        self.after = starocean.correct(self.before)
        self.edition = an_edition(self.before, self.after)

    def test_the_corrected_image_comes_back(self) -> None:
        # Arrange
        image = self.before

        # Act
        produced = starocean.apply(image, self.edition)

        # Assert
        self.assertEqual(produced, self.after)

    def test_a_result_the_manifest_did_not_predict_is_refused(self) -> None:
        # Arrange
        wrong = an_edition(self.before, an_image(declared=0x0C))

        # Act
        with self.assertRaises(starocean.Unexpected) as raised:
            starocean.apply(self.before, wrong)

        # Assert
        self.assertIn("sha256", str(raised.exception))

    def test_the_refusal_names_what_was_produced_so_it_can_be_looked_up(self) -> None:
        # Arrange
        wrong = an_edition(self.before, an_image(declared=0x0C))

        # Act
        with self.assertRaises(starocean.Unexpected) as raised:
            starocean.apply(self.before, wrong)

        # Assert
        self.assertIn(digests_of(self.after)["sha256"], str(raised.exception))

    def test_a_result_disagreeing_with_itself_is_reported_as_corrupt(self) -> None:
        # Arrange
        edition = an_edition(self.before, self.after)
        edition.after = dict(edition.after, md5="0" * 32)

        # Act
        with self.assertRaises(starocean.Corrupt) as raised:
            starocean.apply(self.before, edition)

        # Assert
        self.assertIn("after correction", str(raised.exception))

    def test_an_image_that_is_not_the_one_named_never_reaches_the_correction(self) -> None:
        # Arrange
        other = an_edition(an_image(declared=0x0B), self.after)

        # Act
        attempt = lambda: starocean.apply(self.before, other)  # noqa: E731

        # Assert
        self.assertRaises(starocean.Unrecognised, attempt)


class OnDiskTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.where = Path(tempfile.mkdtemp())
        self.before = an_image()
        self.edition = an_edition(self.before, starocean.correct(self.before))
        (self.where / self.edition.reads).write_bytes(self.before)

    def test_a_corrected_file_is_written_beside_the_one_it_came_from(self) -> None:
        # Arrange
        expected = starocean.correct(self.before)

        # Act
        written = starocean.run(self.edition, self.where, self.where)

        # Assert
        self.assertEqual(written.read_bytes(), expected)

    def test_the_written_file_carries_the_name_the_manifest_gives_it(self) -> None:
        # Arrange
        edition = self.edition

        # Act
        written = starocean.run(edition, self.where, self.where)

        # Assert
        self.assertEqual(written.name, "out.sfc")

    def test_a_source_that_is_not_there_is_refused(self) -> None:
        # Arrange
        nowhere = Path("/nowhere/at/all")

        # Act
        with self.assertRaises(starocean.Missing) as raised:
            starocean.run(self.edition, nowhere, self.where)

        # Assert
        self.assertIn("in.sfc", str(raised.exception))

    def test_running_twice_writes_the_same_file(self) -> None:
        # Arrange
        once = starocean.run(self.edition, self.where, self.where).read_bytes()

        # Act
        twice = starocean.run(self.edition, self.where, self.where)

        # Assert
        self.assertEqual(twice.read_bytes(), once)

    def test_a_destination_that_does_not_exist_yet_is_created(self) -> None:
        # Arrange
        into = self.where / "made" / "up"

        # Act
        written = starocean.run(self.edition, self.where, into)

        # Assert
        self.assertTrue(written.is_file())


class MainTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.where = Path(tempfile.mkdtemp())

    def test_a_directory_with_neither_image_reports_that_nothing_was_done(self) -> None:
        # Arrange
        argv = [str(self.where), str(self.where)]

        # Act
        code = fix.main(argv)

        # Assert
        self.assertEqual(code, 2)

    def test_a_file_under_the_right_name_but_the_wrong_content_is_refused(self) -> None:
        # Arrange
        edition = starocean.named("japanese")
        (self.where / edition.reads).write_bytes(an_image(size=edition.size))

        # Act
        code = fix.main([str(self.where), str(self.where / "out")])

        # Assert
        self.assertEqual(code, 1)

    def test_a_refusal_writes_nothing(self) -> None:
        # Arrange
        edition = starocean.named("japanese")
        (self.where / edition.reads).write_bytes(an_image(size=edition.size))
        into = self.where / "out"

        # Act
        fix.main([str(self.where), str(into)])

        # Assert
        self.assertFalse((into / edition.writes).exists())

    def test_a_file_with_no_header_at_all_is_refused_rather_than_crashing(self) -> None:
        # Arrange
        edition = starocean.named("japanese")
        (self.where / edition.reads).write_bytes(bytes(edition.size))

        # Act
        code = fix.main([str(self.where), str(self.where / "out")])

        # Assert
        self.assertEqual(code, 1)

    def test_one_argument_uses_the_destination_in_this_repository(self) -> None:
        # Arrange
        argv = [str(self.where)]

        # Act
        code = fix.main(argv)

        # Assert
        self.assertEqual(code, 2)

    def test_an_image_it_recognises_is_corrected_and_reported(self) -> None:
        # Arrange
        before = an_image()
        edition = an_edition(before, starocean.correct(before))
        (self.where / edition.reads).write_bytes(before)
        into = self.where / "out"

        # Act
        code = fix.main([str(self.where), str(into)], catalogue=(edition,))

        # Assert
        self.assertEqual(code, 0)
        self.assertEqual((into / edition.writes).read_bytes(), starocean.correct(before))

    def test_one_present_and_one_absent_still_corrects_the_one_that_is_here(self) -> None:
        # Arrange
        before = an_image()
        here = an_edition(before, starocean.correct(before), name="here")
        absent = an_edition(before, starocean.correct(before), name="absent")
        absent.reads = "not-here.sfc"
        (self.where / here.reads).write_bytes(before)

        # Act
        code = fix.main([str(self.where), str(self.where / "out")], (here, absent))

        # Assert
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
