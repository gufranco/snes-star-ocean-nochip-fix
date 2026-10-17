import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import starocean
from starocean import fix


class SourceDirectoryTest(unittest.TestCase):
    def test_the_directory_comes_from_the_environment_when_one_is_named(self) -> None:
        # Arrange
        environment = {"STAR_OCEAN_ROM_DIR": "/x"}

        # Act
        chosen = starocean.source_directory(environment)

        # Assert
        self.assertEqual(chosen, Path("/x"))

    def test_a_named_directory_wins_even_when_it_is_not_there(self) -> None:
        # Arrange
        environment = {fix.DIRECTORY_VARIABLE: "/nowhere"}

        # Act
        chosen = starocean.source_directory(environment)

        # Assert
        self.assertEqual(chosen, Path("/nowhere"))

    def test_and_the_folder_in_this_repository_is_used_when_none_is(self) -> None:
        # Arrange
        environment: dict[str, str] = {}

        # Act
        chosen = starocean.source_directory(environment)

        # Assert
        self.assertEqual(chosen, fix.DEFAULT_SOURCE)

    def test_the_project_this_sits_inside_is_looked_at_too(self) -> None:
        # Arrange
        environment: dict[str, str] = {}

        # Act
        found = starocean.directories(environment)

        # Assert
        self.assertIn(fix.ALONGSIDE, found)

    def test_a_named_directory_comes_before_either_of_them(self) -> None:
        # Arrange
        environment = {fix.DIRECTORY_VARIABLE: "/x"}

        # Act
        found = starocean.directories(environment)

        # Assert
        self.assertEqual(found[0], Path("/x"))

    def test_the_first_place_that_is_actually_there_is_the_one_used(self) -> None:
        # Arrange
        here = Path(tempfile.mkdtemp())

        # Act
        chosen = starocean.source_directory({}, places=[Path("/nowhere"), here])

        # Assert
        self.assertEqual(chosen, here)

    def test_and_when_no_place_is_there_the_folder_here_is_named(self) -> None:
        # Arrange
        places = [Path("/nowhere"), Path("/nor/here")]

        # Act
        chosen = starocean.source_directory({}, places=places)

        # Assert
        self.assertEqual(chosen, fix.DEFAULT_SOURCE)


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
            fix.command()

        # Assert
        self.assertEqual(held.exception.code, 2)


class SharedDirectoryRuleTest(unittest.TestCase):
    def test_the_project_above_is_looked_at_before_the_package_itself(self) -> None:
        # Arrange
        environment: dict[str, str] = {}

        # Act
        found = starocean.directories(environment)

        # Assert
        self.assertLess(found.index(fix.ALONGSIDE), found.index(fix.DEFAULT_DIRECTORY))

    def test_more_than_one_can_be_named_at_once(self) -> None:
        # Arrange
        environment = {fix.DIRECTORY_VARIABLE: f"/x{os.pathsep}/y"}

        # Act
        found = starocean.directories(environment)

        # Assert
        self.assertEqual(found[:2], (Path("/x"), Path("/y")))

    def test_an_empty_entry_between_two_names_is_passed_over(self) -> None:
        # Arrange
        environment = {fix.DIRECTORY_VARIABLE: f"/x{os.pathsep}{os.pathsep}/y"}

        # Act
        found = starocean.directories(environment)

        # Assert
        self.assertEqual(found[:2], (Path("/x"), Path("/y")))

    def test_no_directory_appears_twice(self) -> None:
        # Arrange
        environment = {fix.DIRECTORY_VARIABLE: str(fix.DEFAULT_DIRECTORY)}

        # Act
        found = starocean.directories(environment)

        # Assert
        self.assertEqual(len(found), len(set(found)))


if __name__ == "__main__":
    unittest.main()
