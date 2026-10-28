import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import starocean

MANIFEST = ROOT / "editions.manifest.json"

WIDTHS = {"crc32": 8, "md5": 32, "sha1": 40, "sha256": 64}

TWELVE_MEGABYTES = 12 * 1024 * 1024


class CatalogueTest(unittest.TestCase):
    def test_both_editions_are_listed(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        names = [edition.name for edition in catalogue]

        # Assert
        self.assertEqual(names, ["japanese", "english"])

    def test_each_edition_names_the_file_it_reads_and_the_file_it_writes(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        pairs = [(edition.reads, edition.writes) for edition in catalogue]

        # Assert
        self.assertEqual([pair for pair in pairs if not all(pair) or pair[0] == pair[1]], [])

    def test_both_editions_are_the_same_length(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        lengths = {edition.size for edition in catalogue}

        # Assert
        self.assertEqual(lengths, {TWELVE_MEGABYTES})

    def test_that_length_is_the_one_the_whole_bank_map_has(self) -> None:
        # Arrange
        expected = 0xC00000

        # Act
        published = starocean.EXPECTED_BYTES

        # Assert
        self.assertEqual(published, expected)

    def test_an_edition_prints_as_its_name_and_length(self) -> None:
        # Arrange
        edition = starocean.named("japanese")

        # Act
        printed = repr(edition)

        # Assert
        self.assertEqual(printed, "<Edition japanese, 12582912 bytes>")

    def test_the_table_is_read_from_the_manifest_rather_than_written_in_code(self) -> None:
        # Arrange
        held = json.loads(MANIFEST.read_text())

        # Act
        loaded = starocean.load()

        # Assert
        self.assertEqual(
            [edition.name for edition in loaded], [one["name"] for one in held["editions"]]
        )

    def test_a_manifest_somewhere_else_can_be_read_instead(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "other.json"
        where.write_text(json.dumps({"editions": []}))

        # Act
        loaded = starocean.load(where)

        # Assert
        self.assertEqual(loaded, ())


class DigestTest(unittest.TestCase):
    def test_every_edition_pins_all_four_digests_of_what_it_reads(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        widths = [{name: len(value) for name, value in one.before.items()} for one in catalogue]

        # Assert
        self.assertEqual(widths, [WIDTHS, WIDTHS])

    def test_and_all_four_of_what_it_writes(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        widths = [{name: len(value) for name, value in one.after.items()} for one in catalogue]

        # Assert
        self.assertEqual(widths, [WIDTHS, WIDTHS])

    def test_the_published_widths_are_those_of_the_four_digests(self) -> None:
        # Arrange
        expected = WIDTHS

        # Act
        published = dict(starocean.DIGEST_WIDTHS)

        # Assert
        self.assertEqual(published, expected)

    def test_no_edition_reads_and_writes_the_same_bytes(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        same = [one.name for one in catalogue if one.before["sha256"] == one.after["sha256"]]

        # Assert
        self.assertEqual(same, [])

    def test_no_two_editions_share_a_deciding_digest(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        seen = [one.before["sha256"] for one in catalogue] + [
            one.after["sha256"] for one in catalogue
        ]

        # Assert
        self.assertEqual(len(seen), len(set(seen)))

    def test_every_digest_is_written_in_lower_case_hexadecimal(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        values = [
            value
            for one in catalogue
            for held in (one.before, one.after)
            for value in held.values()
        ]

        # Assert
        self.assertEqual(
            [
                value
                for value in values
                if value != value.lower() or not all(c in "0123456789abcdef" for c in value)
            ],
            [],
        )


class ChainTest(unittest.TestCase):
    def test_the_patch_is_named_with_its_author_and_where_it_lives(self) -> None:
        # Arrange
        patch = starocean.PATCH

        # Act
        held = (patch.author, patch.where.startswith("https://"), bool(patch.version))

        # Assert
        self.assertEqual(held, ("neviksti", True, True))

    def test_the_archive_carrying_the_patch_is_pinned(self) -> None:
        # Arrange
        archive = starocean.PATCH.archive

        # Act
        widths = {name: len(str(archive[name])) for name in WIDTHS}

        # Assert
        self.assertEqual(widths, WIDTHS)

    def test_every_edition_names_the_cartridge_it_starts_from(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        unnamed = [
            one.name for one in catalogue if not one.source["name"] or one.source["bytes"] <= 0
        ]

        # Assert
        self.assertEqual(unnamed, [])

    def test_and_the_patch_that_turns_it_into_the_image_read(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        astray = [
            one.patch["name"] for one in catalogue if not one.patch["name"].endswith(".xdelta")
        ]

        # Assert
        self.assertEqual(astray, [])

    def test_each_edition_uses_a_patch_of_its_own(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        used = [one.patch["name"] for one in catalogue]

        # Assert
        self.assertEqual(len(used), len(set(used)))

    def test_each_edition_starts_from_a_cartridge_of_its_own(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        used = [one.source["sha256"] for one in catalogue]

        # Assert
        self.assertEqual(len(used), len(set(used)))

    def test_every_link_in_the_chain_pins_all_four_digests(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        widths = [
            {name: len(link[name]) for name in WIDTHS}
            for one in catalogue
            for link in (one.source, one.patch, one.before, one.after)
        ]

        # Assert
        self.assertEqual(widths, [WIDTHS] * 8)

    def test_the_cartridge_is_smaller_than_what_the_patch_makes_of_it(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        grown = [one.source["bytes"] < one.size for one in catalogue]

        # Assert
        self.assertEqual(grown, [True, True])

    def test_every_link_of_every_edition_is_a_distinct_file(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        seen = [
            link["sha256"]
            for one in catalogue
            for link in (one.source, one.patch, one.before, one.after)
        ]

        # Assert
        self.assertEqual(len(seen), len(set(seen)))

    def test_the_chain_is_offered_in_the_order_it_is_walked(self) -> None:
        # Arrange
        edition = starocean.named("japanese")

        # Act
        walked = edition.chain()

        # Assert
        self.assertEqual(
            [step.what for step in walked], ["source", "patch", "reads", "writes", "writes"]
        )

    def test_every_step_of_the_chain_carries_a_name_and_a_length(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        bare = [
            (one.name, step.what)
            for one in catalogue
            for step in one.chain()
            if not step.name or step.bytes <= 0
        ]

        # Assert
        self.assertEqual(bare, [])

    def test_a_step_prints_as_what_it_is_and_what_it_names(self) -> None:
        # Arrange
        step = starocean.named("japanese").chain()[2]

        # Act
        printed = repr(step)

        # Assert
        self.assertEqual(printed, f"<Step reads: {step.name}, 12582912 bytes>")

    def test_a_patch_prints_as_its_name_version_and_author(self) -> None:
        # Arrange
        patch = starocean.PATCH

        # Act
        printed = repr(patch)

        # Assert
        self.assertEqual(printed, f"<Patch {patch.name} {patch.version}, by neviksti>")

    def test_a_step_offers_the_digest_that_decides_by_default(self) -> None:
        # Arrange
        step = starocean.named("japanese").chain()[0]

        # Act
        found = step.digest()

        # Assert
        self.assertEqual(found, step.held["sha256"])

    def test_and_any_other_when_asked(self) -> None:
        # Arrange
        step = starocean.named("japanese").chain()[0]

        # Act
        found = step.digest("crc32")

        # Assert
        self.assertEqual(found, step.held["crc32"])

    def test_only_the_written_steps_are_ones_this_repository_produces(self) -> None:
        # Arrange
        catalogue = starocean.EDITIONS

        # Act
        produced = [[step.what for step in one.chain() if step.produced] for one in catalogue]

        # Assert
        self.assertEqual(produced, [["writes", "writes"], ["writes", "writes"]])


class LookupTest(unittest.TestCase):
    def test_an_edition_is_found_by_the_digest_of_what_it_reads(self) -> None:
        # Arrange
        wanted = starocean.named("english")

        # Act
        found = starocean.matching(wanted.before["sha256"])

        # Assert
        self.assertIs(found, wanted)

    def test_a_digest_no_edition_carries_finds_nothing(self) -> None:
        # Arrange
        digest = "0" * 64

        # Act
        found = starocean.matching(digest)

        # Assert
        self.assertIsNone(found)

    def test_an_edition_is_found_by_name(self) -> None:
        # Arrange
        name = "english"

        # Act
        found = starocean.named(name)

        # Assert
        self.assertEqual(found.name, name)

    def test_a_name_no_edition_carries_is_refused(self) -> None:
        # Arrange
        name = "nonsense"

        # Act
        attempt = lambda: starocean.named(name)  # noqa: E731

        # Assert
        self.assertRaises(starocean.UnknownEdition, attempt)

    def test_the_refusal_lists_the_editions_there_are(self) -> None:
        # Arrange
        name = "nonsense"

        # Act
        with self.assertRaises(starocean.UnknownEdition) as raised:
            starocean.named(name)

        # Assert
        self.assertEqual(
            str(raised.exception),
            "nonsense is not an edition this corrects; there are japanese, english",
        )

    def test_a_lookup_by_name_can_be_pointed_at_a_different_set(self) -> None:
        # Arrange
        only = (starocean.named("english"),)

        # Act
        found = starocean.named("english", among=only)

        # Assert
        self.assertIs(found, only[0])

    def test_and_so_can_a_lookup_by_digest(self) -> None:
        # Arrange
        only = (starocean.named("english"),)

        # Act
        found = starocean.matching(starocean.named("japanese").before["sha256"], among=only)

        # Assert
        self.assertIsNone(found)


class DecidingDigestTest(unittest.TestCase):
    def held(self) -> str:
        return str(json.loads(MANIFEST.read_text())["decides"])

    def test_the_manifest_names_the_digest_that_decides(self) -> None:
        # Arrange
        published = starocean.DECIDES

        # Act
        said = self.held()

        # Assert
        self.assertEqual(published, "sha256")
        self.assertIn(published, said)

    def test_and_says_the_others_decide_nothing(self) -> None:
        # Arrange
        phrase = "decides anything on its own"

        # Act
        said = self.held()

        # Assert
        self.assertIn(phrase, said)


if __name__ == "__main__":
    unittest.main()
