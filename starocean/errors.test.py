from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import starocean
from starocean import errors

REFUSALS = ["Corrupt", "Missing", "NotACartridge", "Unexpected", "UnknownEdition", "Unrecognised"]


def reaching_back(source: str) -> list[str]:

    def inside(name: str) -> bool:
        return name.startswith(".") or name == "starocean" or name.startswith("starocean.")

    borrowed = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            borrowed += [alias.name for alias in node.names if inside(alias.name)]
        elif isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            if inside(name):
                borrowed.append(name)
    return borrowed


def defined_in(module: object) -> list[str]:
    return sorted(
        name
        for name, held in vars(module).items()
        if isinstance(held, type) and issubclass(held, Exception)
    )


class OneHomeTest(unittest.TestCase):
    def test_the_module_defines_every_refusal_this_package_makes(self) -> None:
        # Arrange
        module = errors

        # Act
        named = defined_in(module)

        # Assert
        self.assertEqual(named, REFUSALS)

    def test_and_each_one_is_published_at_the_root_as_the_same_class(self) -> None:
        # Arrange
        names = REFUSALS

        # Act
        astray = [name for name in names if getattr(starocean, name) is not getattr(errors, name)]

        # Assert
        self.assertEqual(astray, [])

    def test_none_of_them_is_a_subclass_of_another(self) -> None:
        # Arrange
        held = [getattr(starocean, name) for name in REFUSALS]

        # Act
        overlapping = [
            (one.__name__, other.__name__)
            for one in held
            for other in held
            if one is not other and issubclass(one, other)
        ]

        # Assert
        self.assertEqual(overlapping, [])


class OneClassPerNameTest(unittest.TestCase):
    def test_correcting_something_that_is_not_a_cartridge_raises_the_one_defined_here(
        self,
    ) -> None:
        # Arrange
        blank = bytes(0x100000)

        # Act
        with self.assertRaises(Exception) as raised:
            starocean.correct(blank)

        # Assert
        self.assertIs(type(raised.exception), errors.NotACartridge)

    def test_and_running_against_a_missing_source_raises_the_one_defined_here(self) -> None:
        # Arrange
        edition = starocean.named("japanese")

        # Act
        with self.assertRaises(Exception) as raised:
            starocean.run(edition, Path("/nowhere/at/all"), Path("/nowhere/either"))

        # Assert
        self.assertIs(type(raised.exception), errors.Missing)

    def test_and_the_catalogue_raises_the_one_unknown_edition(self) -> None:
        # Arrange
        name = "some other game"

        # Act
        with self.assertRaises(Exception) as raised:
            starocean.named(name)

        # Assert
        self.assertIs(type(raised.exception), errors.UnknownEdition)

    def test_and_the_refusal_names_the_editions_it_does_cover(self) -> None:
        # Arrange
        name = "some other game"

        # Act
        with self.assertRaises(starocean.UnknownEdition) as caught:
            starocean.named(name)

        # Assert
        self.assertIn("japanese", str(caught.exception))


class NoCycleTest(unittest.TestCase):
    def test_it_imports_nothing_from_this_package(self) -> None:
        # Arrange
        held = (ROOT / "starocean" / "errors.py").read_text()

        # Act
        found = reaching_back(held)

        # Assert
        self.assertEqual(found, [])

    def test_the_reader_of_that_names_an_absolute_import_back(self) -> None:
        # Arrange
        source = "import starocean.fix\n"

        # Act
        found = reaching_back(source)

        # Assert
        self.assertEqual(found, ["starocean.fix"])

    def test_and_a_relative_one(self) -> None:
        # Arrange
        source = "from . import fix\n"

        # Act
        found = reaching_back(source)

        # Assert
        self.assertEqual(found, ["."])

    def test_and_steps_over_one_from_outside(self) -> None:
        # Arrange
        source = "from __future__ import annotations\nimport romimage\nimport staroceantools\n"

        # Act
        found = reaching_back(source)

        # Assert
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
