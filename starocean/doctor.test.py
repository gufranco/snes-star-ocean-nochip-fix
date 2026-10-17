import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
import unittest.mock
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "snes-rom-image-python"))
sys.path.append(
    str(Path(__file__).resolve().parent.parent / "snes-rom-image-python" / "snes-mapper-python")
)

import starocean
from starocean import doctor

VERDICT = re.compile(r"^  (\d+ checks, nothing to report|\d+ of \d+ checks did not pass)$")


class Complaint(Exception):
    pass


class Short:
    name = "shortened"
    size = 1

    def chain(self) -> tuple[Any, ...]:
        return ()


def refuse() -> Any:
    raise Complaint("no")


def shortened() -> Any:
    return types.SimpleNamespace(EDITIONS=(Short(),)), None


class FindingTest(unittest.TestCase):
    def test_a_finding_says_what_was_checked(self) -> None:
        # Arrange
        name = "python"

        # Act
        one = doctor.Finding(name, True, "3.14")

        # Assert
        self.assertEqual(one.name, "python")

    def test_a_healthy_finding_prints_with_a_mark_that_says_so(self) -> None:
        # Arrange
        one = doctor.Finding("python", True, "3.14")

        # Act
        line = one.line

        # Assert
        self.assertEqual(line, "  ok    python: 3.14")

    def test_and_an_unhealthy_one_prints_differently(self) -> None:
        # Arrange
        one = doctor.Finding("python", False, "3.9")

        # Act
        line = one.line

        # Assert
        self.assertEqual(line, "     !  python: 3.9")

    def test_an_unhealthy_finding_says_what_to_do_about_it(self) -> None:
        # Arrange
        one = doctor.Finding("python", False, "3.9", "upgrade")

        # Act
        printed = one.report

        # Assert
        self.assertEqual(printed, "     !  python: 3.9\n         upgrade")

    def test_a_healthy_one_keeps_its_advice_to_itself(self) -> None:
        # Arrange
        one = doctor.Finding("python", True, "3.14", "upgrade")

        # Act
        printed = one.report

        # Assert
        self.assertNotIn("upgrade", printed)

    def test_and_so_does_an_unhealthy_one_with_none_to_give(self) -> None:
        # Arrange
        one = doctor.Finding("python", False, "3.9")

        # Act
        printed = one.report

        # Assert
        self.assertEqual(printed, one.line)

    def test_a_finding_prints_as_itself(self) -> None:
        # Arrange
        one = doctor.Finding("python", False, "3.9")

        # Act
        printed = repr(one)

        # Assert
        self.assertEqual(printed, "<Finding python not ok>")

    def test_and_says_so_when_it_is_well(self) -> None:
        # Arrange
        one = doctor.Finding("python", True, "3.14")

        # Act
        printed = repr(one)

        # Assert
        self.assertEqual(printed, "<Finding python ok>")


class VersionTest(unittest.TestCase):
    def test_it_reports_the_python_it_is_running_on(self) -> None:
        # Arrange
        oldest = (3, 12)

        # Act
        one = doctor.check_python()

        # Assert
        self.assertEqual(one.ok, sys.version_info[:2] >= oldest, one.detail)

    def test_and_names_the_package(self) -> None:
        # Arrange
        expected = f"version {starocean.VERSION}"

        # Act
        one = doctor.check_package()

        # Assert
        self.assertEqual((one.name, one.detail), ("starocean", expected))

    def test_the_version_is_read_out_of_the_file_rather_than_imported(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "version.py"
        where.write_text('VERSION = "4.5.6"\n')

        # Act
        found = doctor.installed_version(where)

        # Assert
        self.assertEqual(found, "4.5.6")

    def test_and_the_one_it_reads_here_is_the_package_s_own(self) -> None:
        # Arrange
        published = starocean.VERSION

        # Act
        found = doctor.installed_version()

        # Assert
        self.assertEqual(found, published)

    def test_a_version_file_naming_nothing_reads_as_unknown(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "version.py"
        where.write_text("NOTHING = 1\n")

        # Act
        found = doctor.installed_version(where)

        # Assert
        self.assertEqual(found, "unknown")

    def test_the_repository_is_put_on_the_path_when_it_is_not_already_there(self) -> None:
        # Arrange
        held = [one for one in sys.path if one != str(doctor.ROOT)]

        # Act
        with unittest.mock.patch.object(sys, "path", held):
            doctor.check_editions()

        # Assert
        self.assertIn(str(doctor.ROOT), held)


class EditionTest(unittest.TestCase):
    def test_every_edition_names_a_full_chain(self) -> None:
        # Arrange
        expected = "japanese at 12582912 bytes, english at 12582912 bytes"

        # Act
        one = doctor.check_editions()

        # Assert
        self.assertEqual((one.ok, one.detail), (True, expected))

    def test_an_edition_with_a_link_missing_is_named(self) -> None:
        # Arrange
        load = shortened

        # Act
        one = doctor.check_editions(load)

        # Assert
        self.assertIn("shortened", one.advice or "")

    def test_and_the_finding_is_not_well(self) -> None:
        # Arrange
        load = shortened

        # Act
        one = doctor.check_editions(load)

        # Assert
        self.assertFalse(one.ok)

    def test_a_package_that_will_not_import_is_reported_as_what_it_said(self) -> None:
        # Arrange
        load = refuse

        # Act
        one = doctor.check_editions(load)

        # Assert
        self.assertEqual((one.ok, one.detail), (False, "Complaint: no"))


class ChainTest(unittest.TestCase):
    def test_every_link_of_every_chain_gets_a_line(self) -> None:
        # Arrange
        wanted = 4 * len(starocean.EDITIONS)

        # Act
        found = doctor.check_chain()

        # Assert
        self.assertEqual(len(found), wanted)

    def test_the_written_image_is_looked_for_where_it_is_written(self) -> None:
        # Arrange
        written = "writes"

        # Act
        found = [one for one in doctor.check_chain() if one.name.endswith(written)]

        # Assert
        self.assertTrue(found)
        self.assertEqual([one for one in found if " at dist/" not in one.detail], [])

    def test_and_every_other_link_where_it_is_read(self) -> None:
        # Arrange
        written = "writes"

        # Act
        found = [one for one in doctor.check_chain() if not one.name.endswith(written)]

        # Assert
        self.assertTrue(found)
        self.assertEqual([one for one in found if " at roms/" not in one.detail], [])

    def test_a_file_that_is_not_there_is_said_to_be_absent(self) -> None:
        # Arrange
        empty = Path(tempfile.mkdtemp())

        # Act
        with unittest.mock.patch.object(doctor, "SOURCE", empty):
            found = doctor.check_chain()

        # Assert
        self.assertTrue(any("is not at" in one.detail for one in found))

    def test_a_package_that_will_not_import_reports_no_chain_at_all(self) -> None:
        # Arrange
        load = refuse

        # Act
        found = doctor.check_chain(load)

        # Assert
        self.assertEqual(found, [])


class ExamineTest(unittest.TestCase):
    def test_the_examination_produces_findings(self) -> None:
        # Arrange
        expected = doctor.Finding

        # Act
        found = doctor.examine()

        # Assert
        self.assertEqual({type(one) for one in found}, {expected})

    def test_it_looks_at_every_submodule_this_repository_carries(self) -> None:
        # Arrange
        wanted = "submodule snes-rom-image-python"

        # Act
        named = {one.name for one in doctor.examine()}

        # Assert
        self.assertIn(wanted, named)

    def test_and_nothing_it_looks_at_is_unwell_on_this_machine(self) -> None:
        # Arrange
        healthy: list[str] = []

        # Act
        unwell = [one.name for one in doctor.examine() if not one.ok]

        # Assert
        self.assertEqual(unwell, healthy)


class ReportTest(unittest.TestCase):
    def test_a_clean_examination_says_there_is_nothing_to_report(self) -> None:
        # Arrange
        found = [doctor.Finding("one", True, "fine")]

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertEqual(lines[-1], "  1 checks, nothing to report")

    def test_and_a_dirty_one_counts_what_did_not_pass(self) -> None:
        # Arrange
        found = [doctor.Finding("one", True, "fine"), doctor.Finding("two", False, "not")]

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertEqual(lines[-1], "  1 of 2 checks did not pass")


class MainTest(unittest.TestCase):
    def test_a_clean_machine_exits_zero(self) -> None:
        # Arrange
        clean = [doctor.Finding("one", True, "fine")]

        # Act
        code = doctor.main((), lambda: clean, lambda _: None)

        # Assert
        self.assertEqual(code, 0)

    def test_and_a_machine_with_a_finding_exits_one(self) -> None:
        # Arrange
        dirty = [doctor.Finding("one", False, "not")]

        # Act
        code = doctor.main((), lambda: dirty, lambda _: None)

        # Assert
        self.assertEqual(code, 1)

    def test_the_report_is_said_rather_than_returned(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        doctor.main((), lambda: [doctor.Finding("one", True, "fine")], said.append)

        # Assert
        self.assertEqual(said[-1], "  1 checks, nothing to report")

    def test_it_runs_end_to_end_whatever_this_machine_holds(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = doctor.main((), doctor.examine, said.append)

        # Assert
        self.assertIn(code, (0, 1))
        self.assertRegex(said[-1], VERDICT)


class TheDoctorRunsWhereThePackageMightNotImportTest(unittest.TestCase):
    def test_a_root_that_is_not_on_the_path_is_put_there(self) -> None:
        # Arrange
        path: list[str] = []

        # Act
        added = doctor.reachable(Path("/somewhere"), path)

        # Assert
        self.assertEqual((added, path), (True, ["/somewhere"]))

    def test_a_root_already_on_the_path_is_left_alone(self) -> None:
        # Arrange
        path = ["/somewhere"]

        # Act
        added = doctor.reachable(Path("/somewhere"), path)

        # Assert
        self.assertEqual((added, path), (False, ["/somewhere"]))


class TheDoctorRunsAsTheReadmeSaysTest(unittest.TestCase):
    def test_running_it_as_a_file_from_elsewhere_prints_a_report_rather_than_a_traceback(
        self,
    ) -> None:
        # Arrange
        elsewhere = tempfile.mkdtemp()
        bare = {name: value for name, value in os.environ.items() if name != "PYTHONPATH"}
        source = Path(doctor.__file__).resolve()

        # Act
        finished = subprocess.run(
            [sys.executable, str(source)],
            capture_output=True,
            text=True,
            cwd=elsewhere,
            env=bare,
            check=False,
        )

        # Assert
        self.assertIn(finished.returncode, (0, 1))
        self.assertNotIn("Traceback", finished.stderr)
        self.assertRegex(finished.stdout.splitlines()[-1], VERDICT)


if __name__ == "__main__":
    unittest.main()
