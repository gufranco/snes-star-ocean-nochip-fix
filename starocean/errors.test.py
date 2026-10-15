from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from starocean import editions, errors, fix


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


class OneHomeTest(unittest.TestCase):
    def named(self) -> list[str]:
        return [
            name
            for name, held in vars(errors).items()
            if isinstance(held, type) and issubclass(held, Exception)
        ]

    def test_the_module_defines_every_refusal_this_package_makes(self) -> None:
        self.assertEqual(
            sorted(self.named()),
            ["Corrupt", "Missing", "NotACartridge", "Unexpected", "UnknownEdition", "Unrecognised"],
        )

    def test_every_one_of_them_derives_from_exception(self) -> None:
        stray = [name for name in self.named() if not issubclass(getattr(errors, name), Exception)]

        self.assertEqual(stray, [])

    def test_none_of_them_is_a_subclass_of_another(self) -> None:
        held = [getattr(errors, name) for name in self.named()]

        overlapping = [
            (one.__name__, other.__name__)
            for one in held
            for other in held
            if one is not other and issubclass(one, other)
        ]

        self.assertEqual(overlapping, [])


class OneClassPerNameTest(unittest.TestCase):
    def test_the_fix_raises_the_ones_defined_here(self) -> None:
        held = {
            getattr(fix, name)
            for name in ("NotACartridge", "Unrecognised", "Corrupt", "Unexpected", "Missing")
        }

        self.assertEqual(
            held,
            {
                errors.NotACartridge,
                errors.Unrecognised,
                errors.Corrupt,
                errors.Unexpected,
                errors.Missing,
            },
        )

    def test_and_the_catalogue_raises_the_one_unknown_edition(self) -> None:
        self.assertIs(getattr(editions, "UnknownEdition"), errors.UnknownEdition)  # noqa: B009

    def test_naming_an_edition_this_package_does_not_cover_raises_it(self) -> None:
        with self.assertRaises(errors.UnknownEdition):
            editions.named("some other game")

    def test_and_the_refusal_names_the_editions_it_does_cover(self) -> None:
        with self.assertRaises(errors.UnknownEdition) as caught:
            editions.named("some other game")

        self.assertIn("japanese", str(caught.exception))


class NoCycleTest(unittest.TestCase):
    def test_it_imports_nothing_from_this_package(self) -> None:
        held = (ROOT / "starocean" / "errors.py").read_text()

        self.assertEqual(reaching_back(held), [])

    def test_the_reader_of_that_names_an_absolute_import_back(self) -> None:
        found = reaching_back("import starocean.fix\n")

        self.assertEqual(found, ["starocean.fix"])

    def test_and_a_relative_one(self) -> None:
        found = reaching_back("from . import fix\n")

        self.assertEqual(found, ["."])

    def test_and_steps_over_one_from_outside(self) -> None:
        found = reaching_back(
            "from __future__ import annotations\nimport romimage\nimport staroceantools\n"
        )

        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
