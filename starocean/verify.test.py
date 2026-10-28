import hashlib
import sys
import tempfile
import unittest
import unittest.mock
import zlib
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import starocean
from starocean import verify


def digests_of(blob: bytes) -> dict[str, Any]:
    return {
        "bytes": len(blob),
        "crc32": f"{zlib.crc32(blob) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(blob).hexdigest(),
        "sha1": hashlib.sha1(blob).hexdigest(),
        "sha256": hashlib.sha256(blob).hexdigest(),
    }


def an_edition(name: str = "made-up", **files: bytes) -> starocean.Edition:
    held = {what: digests_of(blob) for what, blob in files.items()}
    return starocean.Edition(
        name=name,
        summary="a stand-in",
        reads="reads.sfc",
        writes="writes.sfc",
        size=held["reads"]["bytes"],
        before={k: v for k, v in held["reads"].items() if k != "bytes"},
        after={k: v for k, v in held["writes"].items() if k != "bytes"},
        source=dict(held["source"], name="source.sfc"),
        patch=dict(held["patch"], name="patch.xdelta"),
    )


SOURCE = b"a cartridge" * 40
PATCH = b"a patch" * 30
READS = b"the patched image" * 20
WRITES = b"the corrected image" * 20

EDITION = an_edition(source=SOURCE, patch=PATCH, reads=READS, writes=WRITES)


def states(where: Path, into: Path | None = None, edition: Any = EDITION) -> dict[str, str]:
    return {one.step.what: one.state for one in starocean.look(where, (edition,), into)}


class StateTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.where = Path(tempfile.mkdtemp())

    def test_a_file_that_is_not_there_is_reported_as_absent(self) -> None:
        # Arrange
        catalogue = (EDITION,)

        # Act
        found = starocean.look(self.where, catalogue)

        # Assert
        self.assertEqual({one.state for one in found}, {starocean.ABSENT})

    def test_a_file_that_matches_is_reported_as_matching(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(READS)

        # Act
        found = states(self.where)

        # Assert
        self.assertEqual(found["reads"], starocean.MATCHES)

    def test_a_file_of_the_right_length_and_wrong_content_is_altered(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(bytes(len(READS)))

        # Act
        found = states(self.where)

        # Assert
        self.assertEqual(found["reads"], starocean.ALTERED)

    def test_a_file_of_the_wrong_length_is_altered_too(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(b"short")

        # Act
        found = states(self.where)

        # Assert
        self.assertEqual(found["reads"], starocean.ALTERED)

    def test_a_file_matching_on_the_deciding_digest_but_not_the_rest_is_corrupt(self) -> None:
        # Arrange
        edition = an_edition(source=SOURCE, patch=PATCH, reads=READS, writes=WRITES)
        edition.before = dict(edition.before, crc32="00000000")
        (self.where / "reads.sfc").write_bytes(READS)

        # Act
        found = states(self.where, edition=edition)

        # Assert
        self.assertEqual(found["reads"], starocean.CORRUPT)

    def test_every_step_of_the_chain_is_looked_for(self) -> None:
        # Arrange
        catalogue = (EDITION,)

        # Act
        found = starocean.look(self.where, catalogue)

        # Assert
        self.assertEqual([one.step.what for one in found], ["source", "patch", "reads", "writes"])

    def test_the_place_a_file_was_looked_for_is_reported(self) -> None:
        # Arrange
        into = self.where / "out"

        # Act
        found = starocean.look(self.where, (EDITION,), into)

        # Assert
        self.assertEqual(
            [one.path.parent for one in found],
            [self.where, self.where, self.where, into / starocean.EMULATOR],
        )

    def test_a_file_this_repository_makes_is_never_looked_for_among_the_sources(self) -> None:
        # Arrange
        into = self.where / "out"
        (self.where / "writes.sfc").write_bytes(WRITES)

        # Act
        found = states(self.where, into)

        # Assert
        self.assertEqual(found["writes"], starocean.ABSENT)

    def test_a_produced_file_is_looked_for_where_it_would_be_written(self) -> None:
        # Arrange
        into = self.where / "out"
        (into / starocean.EMULATOR).mkdir(parents=True)
        (into / starocean.EMULATOR / "writes.sfc").write_bytes(WRITES)

        # Act
        found = states(self.where, into)

        # Assert
        self.assertEqual(found["writes"], starocean.MATCHES)

    def test_a_directory_beneath_holding_something_else_is_walked_past(self) -> None:
        # Arrange
        (self.where / "deep").mkdir()
        (self.where / "deep" / "reads.sfc").mkdir()

        # Act
        found = states(self.where)

        # Assert
        self.assertEqual(found["reads"], starocean.ABSENT)

    def test_a_subdirectory_is_searched_as_well(self) -> None:
        # Arrange
        (self.where / "somewhere").mkdir()
        (self.where / "somewhere" / "reads.sfc").write_bytes(READS)

        # Act
        found = states(self.where)

        # Assert
        self.assertEqual(found["reads"], starocean.MATCHES)

    def test_a_finding_prints_as_its_state_and_what_it_names(self) -> None:
        # Arrange
        finding = starocean.look(self.where, (EDITION,))[0]

        # Act
        printed = repr(finding)

        # Assert
        self.assertIn(starocean.ABSENT, printed)
        self.assertIn("source.sfc", printed)


class ReportTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.where = Path(tempfile.mkdtemp())

    def test_every_finding_makes_a_line(self) -> None:
        # Arrange
        found = starocean.look(self.where, (EDITION,))

        # Act
        lines = starocean.report(found)

        # Assert
        self.assertEqual(len(lines), 4)

    def test_a_line_names_the_edition_the_step_and_the_state(self) -> None:
        # Arrange
        found = starocean.look(self.where, (EDITION,))

        # Act
        line = starocean.report(found)[0]

        # Assert
        self.assertIn("made-up", line)
        self.assertIn("source", line)
        self.assertIn(starocean.ABSENT, line)

    def test_an_altered_file_says_what_was_computed_so_it_can_be_looked_up(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(bytes(len(READS)))
        found = starocean.look(self.where, (EDITION,))

        # Act
        lines = [line for line in starocean.report(found) if starocean.ALTERED in line]

        # Assert
        self.assertIn(hashlib.sha256(bytes(len(READS))).hexdigest()[:16], lines[0])


class VerdictTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.where = Path(tempfile.mkdtemp())

    def test_nothing_present_is_neither_pass_nor_fail(self) -> None:
        # Arrange
        found = starocean.look(self.where, (EDITION,))

        # Act
        decided = starocean.verdict(found)

        # Assert
        self.assertEqual(decided, starocean.NOTHING)

    def test_everything_present_and_matching_passes(self) -> None:
        # Arrange
        for name, blob in (
            ("source.sfc", SOURCE),
            ("patch.xdelta", PATCH),
            ("reads.sfc", READS),
            ("writes.sfc", WRITES),
        ):
            (self.where / name).write_bytes(blob)
        found = starocean.look(self.where, (EDITION,))

        # Act
        decided = starocean.verdict(found)

        # Assert
        self.assertEqual(decided, starocean.SOUND)

    def test_one_file_present_and_matching_still_passes(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(READS)
        found = starocean.look(self.where, (EDITION,))

        # Act
        decided = starocean.verdict(found)

        # Assert
        self.assertEqual(decided, starocean.SOUND)

    def test_one_altered_file_fails_whatever_else_is_right(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(READS)
        (self.where / "source.sfc").write_bytes(b"not the cartridge")
        found = starocean.look(self.where, (EDITION,))

        # Act
        decided = starocean.verdict(found)

        # Assert
        self.assertEqual(decided, starocean.WRONG)

    def test_the_three_verdicts_are_three_different_words(self) -> None:
        # Arrange
        words = (starocean.SOUND, starocean.WRONG, starocean.NOTHING)

        # Act
        distinct = set(words)

        # Assert
        self.assertEqual(distinct, {"sound", "wrong", "nothing"})


class MainTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.where = Path(tempfile.mkdtemp())

    def test_an_empty_directory_reports_that_nothing_was_found(self) -> None:
        # Arrange
        argv = [str(self.where)]

        # Act
        code = verify.main(argv, (EDITION,))

        # Assert
        self.assertEqual(code, 2)

    def test_a_directory_where_everything_matches_reports_success(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(READS)

        # Act
        code = verify.main([str(self.where)], (EDITION,))

        # Assert
        self.assertEqual(code, 0)

    def test_a_directory_with_an_altered_file_reports_failure(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(bytes(len(READS)))

        # Act
        code = verify.main([str(self.where)], (EDITION,))

        # Assert
        self.assertEqual(code, 1)

    def test_it_writes_nothing_whatever_it_finds(self) -> None:
        # Arrange
        (self.where / "reads.sfc").write_bytes(READS)
        before = sorted(path.name for path in self.where.iterdir())

        # Act
        verify.main([str(self.where)], (EDITION,))

        # Assert
        self.assertEqual(sorted(path.name for path in self.where.iterdir()), before)

    def test_no_arguments_reads_the_directories_in_this_repository(self) -> None:
        # Arrange
        argv: list[str] = []

        # Act
        code = verify.main(argv, (EDITION,))

        # Assert
        self.assertIn(code, (0, 1, 2))

    def test_a_second_argument_names_where_produced_files_are_looked_for(self) -> None:
        # Arrange
        into = self.where / "out"
        (into / starocean.EMULATOR).mkdir(parents=True)
        (into / starocean.EMULATOR / "writes.sfc").write_bytes(WRITES)

        # Act
        code = verify.main([str(self.where), str(into)], (EDITION,))

        # Assert
        self.assertEqual(code, 0)


class CommandTest(unittest.TestCase):
    def test_it_exits_with_what_the_run_decided(self) -> None:
        # Arrange
        empty = tempfile.mkdtemp()
        argv = [sys.argv[0], empty, empty]

        # Act
        with (
            unittest.mock.patch.object(sys, "argv", argv),
            self.assertRaises(SystemExit) as held,
        ):
            verify.command()

        # Assert
        self.assertEqual(held.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
