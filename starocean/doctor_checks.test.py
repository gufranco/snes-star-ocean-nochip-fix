import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "snes-rom-image-python"))
sys.path.append(
    str(Path(__file__).resolve().parent.parent / "snes-rom-image-python" / "snes-mapper-python")
)

from starocean import doctor


def a_file(body: str) -> Path:
    where = Path(tempfile.mkdtemp()) / "held.json"
    where.write_text(body)
    return where


class SubmoduleTest(unittest.TestCase):
    def test_every_submodule_this_repository_carries_is_checked_out(self) -> None:
        # Arrange
        name = "snes-rom-image-python"

        # Act
        one = doctor.check_submodule(name)

        # Assert
        self.assertTrue(one.ok, one.detail)

    def test_a_submodule_that_is_not_there_is_reported(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())

        # Act
        one = doctor.check_submodule("absent", where)

        # Assert
        self.assertIn("is not there", one.detail)

    def test_a_directory_git_left_empty_is_reported_as_empty(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "hollow").mkdir()

        # Act
        one = doctor.check_submodule("hollow", where)

        # Assert
        self.assertIn("is empty", one.detail)

    def test_and_neither_is_well_because_nothing_here_runs_without_it(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())

        # Act
        one = doctor.check_submodule("absent", where)

        # Assert
        self.assertFalse(one.ok)


class ManifestTest(unittest.TestCase):
    def test_the_manifest_beside_the_package_pins_editions(self) -> None:
        # Arrange
        where = doctor.MANIFEST

        # Act
        one = doctor.check_manifest(where)

        # Assert
        self.assertTrue(one.ok, one.detail)

    def test_and_records_the_outputs_a_previous_correction_produced(self) -> None:
        # Arrange
        where = doctor.MANIFEST

        # Act
        one = doctor.check_manifest(where)

        # Assert
        self.assertEqual(one.detail, "2 editions pinned, 2 carrying superseded digests")

    def test_a_manifest_that_is_not_there_is_reported(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "absent.json"

        # Act
        one = doctor.check_manifest(where)

        # Assert
        self.assertFalse(one.ok)

    def test_a_manifest_that_is_not_json_is_reported_differently(self) -> None:
        # Arrange
        where = a_file("{")

        # Act
        one = doctor.check_manifest(where)

        # Assert
        self.assertIn("not readable as JSON", one.detail)

    def test_a_manifest_pinning_nothing_is_not_well(self) -> None:
        # Arrange
        where = a_file('{"editions": []}')

        # Act
        one = doctor.check_manifest(where)

        # Assert
        self.assertFalse(one.ok)

    def test_a_manifest_with_no_superseded_digests_says_that_rather_than_nothing(self) -> None:
        # Arrange
        where = a_file(json.dumps({"editions": [{"name": "one"}]}))

        # Act
        one = doctor.check_manifest(where)

        # Assert
        self.assertIn("none carrying superseded digests", one.detail)


class SourceTest(unittest.TestCase):
    def test_a_directory_of_images_is_counted(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "one.sfc").write_bytes(b"\x00")

        # Act
        one = doctor.check_source(where)

        # Assert
        self.assertIn("1 files", one.detail)

    def test_a_directory_that_is_not_there_is_reported_as_nothing_to_do(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "absent"

        # Act
        one = doctor.check_source(where)

        # Assert
        self.assertIn("nothing to correct", one.detail)

    def test_and_is_not_a_fault_because_a_fresh_checkout_has_none(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "absent"

        # Act
        one = doctor.check_source(where)

        # Assert
        self.assertTrue(one.ok)

    def test_an_empty_directory_says_so_too(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())

        # Act
        one = doctor.check_source(where)

        # Assert
        self.assertIn("is here and empty", one.detail)

    def test_a_directory_that_cannot_be_read_is_reported_as_what_it_said(self) -> None:
        # Arrange
        def refuse_to_list(*_: Any, **__: Any) -> Any:
            raise OSError("permission denied")

        where = Path(tempfile.mkdtemp())

        # Act
        with unittest.mock.patch.object(Path, "iterdir", refuse_to_list):
            one = doctor.check_source(where)

        # Assert
        self.assertIn("permission denied", one.detail)


if __name__ == "__main__":
    unittest.main()
