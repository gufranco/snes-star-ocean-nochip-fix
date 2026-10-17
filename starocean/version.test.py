import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import starocean


def copies_a_version(source: str) -> bool:
    return re.search(r"""^VERSION\s*[:=][^=\n]*=?\s*["']""", source, re.M) is not None


class VersionTest(unittest.TestCase):
    def test_a_version_is_recorded(self) -> None:
        # Arrange
        published = starocean.VERSION

        # Act
        recorded = bool(published)

        # Assert
        self.assertTrue(recorded)

    def test_it_reads_as_three_numbers(self) -> None:
        # Arrange
        published = starocean.VERSION

        # Act
        found = re.fullmatch(r"\d+\.\d+\.\d+([-+].*)?", published)

        # Assert
        self.assertIsNotNone(found, published)

    def test_and_the_dunder_spelling_is_the_same_one(self) -> None:
        # Arrange
        published = starocean.VERSION

        # Act
        dunder = starocean.__version__

        # Assert
        self.assertEqual(dunder, published)

    def test_the_release_script_writes_the_field_this_file_holds(self) -> None:
        # Arrange
        script = (ROOT / "scripts" / "set-version.sh").read_text()

        # Act
        named = "starocean/version.py" in script

        # Assert
        self.assertTrue(named)

    def test_nothing_else_in_the_package_carries_a_version_of_its_own(self) -> None:
        # Arrange
        package = ROOT / "starocean"

        # Act
        elsewhere = [
            path.name
            for path in package.glob("*.py")
            if path.name != "version.py" and copies_a_version(path.read_text())
        ]

        # Assert
        self.assertEqual(elsewhere, [])

    def test_and_a_hardcoded_copy_would_be_caught(self) -> None:
        # Arrange
        source = 'VERSION = "1.2.3"'

        # Act
        caught = copies_a_version(source)

        # Assert
        self.assertTrue(caught)

    def test_while_a_version_read_out_of_the_one_file_is_not(self) -> None:
        # Arrange
        source = "VERSION = installed_version()"

        # Act
        caught = copies_a_version(source)

        # Assert
        self.assertFalse(caught)


if __name__ == "__main__":
    unittest.main()
