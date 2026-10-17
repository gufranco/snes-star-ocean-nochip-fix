import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "snes-rom-image-python"))
sys.path.insert(0, str(ROOT / "snes-rom-image-python" / "snes-mapper-python"))

import mapper
from romimage import rewrite

import starocean
from starocean import fix

SOURCE = starocean.source_directory()

PRESENT = tuple(edition for edition in starocean.EDITIONS if (SOURCE / edition.reads).is_file())

WHY_NOT = (
    "neither image was found: these read a rebuild somebody else made, and it is"
    " theirs, so a copy you already own goes in the roms directory of this"
    f" repository or wherever {fix.DIRECTORY_VARIABLE} points"
)

HEADER = 0x7FC0

HEADER_BYTES = 32


def image_of(edition: starocean.Edition) -> bytes:  # pragma: no cover
    return (SOURCE / edition.reads).read_bytes()


@unittest.skipUnless(PRESENT, WHY_NOT)
class SourceTest(unittest.TestCase):  # pragma: no cover
    def test_every_image_present_is_the_length_the_manifest_pins(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        lengths = [(SOURCE / edition.reads).stat().st_size for edition in editions]

        # Assert
        self.assertEqual(lengths, [edition.size for edition in editions])

    def test_every_image_present_matches_all_four_of_its_pinned_digests(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        found = [starocean.digests_of(image_of(edition)) for edition in editions]

        # Assert
        self.assertEqual(found, [dict(edition.before) for edition in editions])

    def test_every_image_present_still_claims_the_chip_it_no_longer_has(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        claims = [rewrite.needs_rewrite(image_of(edition)) for edition in editions]

        # Assert
        self.assertEqual(claims, [True] * len(editions))


@unittest.skipUnless(PRESENT, WHY_NOT)
class ResultTest(unittest.TestCase):  # pragma: no cover
    def test_correcting_each_one_produces_exactly_what_was_promised(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        found = [
            starocean.digests_of(starocean.apply(image_of(edition), edition))
            for edition in editions
        ]

        # Assert
        self.assertEqual(found, [dict(edition.after) for edition in editions])

    def test_the_result_declares_no_coprocessor_and_the_length_it_has(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        claims = [
            rewrite.needs_rewrite(starocean.apply(image_of(edition), edition))
            for edition in editions
        ]

        # Assert
        self.assertEqual(claims, [False] * len(editions))

    def test_the_result_carries_a_checksum_that_covers_it(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        produced = [starocean.apply(image_of(edition), edition) for edition in editions]

        # Assert
        for one in produced:
            declared = mapper.read(one)
            self.assertEqual(rewrite.checksum(one, rewrite.mirrors(one)), declared.checksum)
            self.assertTrue(declared.checksum_agrees)

    def test_the_result_is_on_the_map_a_twelve_megabyte_image_uses(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        produced = [starocean.apply(image_of(edition), edition) for edition in editions]

        # Assert
        for one in produced:
            self.assertEqual(len(one), 12 * 1024 * 1024)
            self.assertEqual(
                mapper.header.board(mapper.read(one), len(one)), mapper.header.WHOLEBANK
            )

    def test_and_the_header_still_sits_where_a_low_declaration_puts_it(self) -> None:
        # Arrange
        editions = PRESENT

        # Act
        declared = [mapper.read(starocean.apply(image_of(one), one)) for one in editions]

        # Assert
        self.assertEqual(
            [(one.layout, one.at) for one in declared],
            [(mapper.header.LOROM, HEADER)] * len(editions),
        )

    def test_only_the_header_mirrors_are_touched(self) -> None:
        # Arrange
        images = [(image_of(edition), edition) for edition in PRESENT]

        # Act
        moved = [
            (
                set(rewrite.mirrors(image)),
                [at for at, (a, b) in enumerate(zip(image, after, strict=True)) if a != b],
            )
            for image, edition in images
            for after in (starocean.apply(image, edition),)
        ]

        # Assert
        for places, changed in moved:
            self.assertTrue(changed)
            outside = [
                hex(at)
                for at in changed
                if not any(place <= at < place + HEADER_BYTES for place in places)
            ]
            self.assertEqual(outside, [])

    def test_correcting_a_corrected_image_changes_nothing_further(self) -> None:
        # Arrange
        produced = [starocean.apply(image_of(edition), edition) for edition in PRESENT]

        # Act
        again = [starocean.correct(one) for one in produced]

        # Assert
        self.assertEqual(again, produced)


@unittest.skipUnless(PRESENT, WHY_NOT)
class RunTest(unittest.TestCase):  # pragma: no cover
    def test_each_one_is_written_out_under_the_name_it_was_given(self) -> None:
        # Arrange
        into = Path(tempfile.mkdtemp())

        # Act
        written = [starocean.run(edition, SOURCE, into) for edition in PRESENT]

        # Assert
        self.assertEqual([one.name for one in written], [edition.writes for edition in PRESENT])
        self.assertEqual(
            [starocean.digests_of(one.read_bytes()) for one in written],
            [dict(edition.after) for edition in PRESENT],
        )


if __name__ == "__main__":
    unittest.main()
