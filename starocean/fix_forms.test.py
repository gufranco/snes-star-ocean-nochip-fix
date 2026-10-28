import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "snes-rom-image-python"))
sys.path.append(str(ROOT / "snes-rom-image-python" / "snes-mapper-python"))

from romimage import copier

import starocean

HEADER = 0x7FC0
WHOLE = 0xC00000


def an_image(size: int = WHOLE) -> bytes:
    rom = bytearray(size)
    rom[HEADER : HEADER + 21] = b"Star Ocean           "
    rom[HEADER + 21] = 0x32
    rom[HEADER + 22] = 0x45
    rom[HEADER + 23] = 0x0D
    rom[HEADER + 24] = 0x03
    rom[HEADER + 28 : HEADER + 32] = b"\xa5\xa5\x5a\x5a"
    return bytes(rom)


def a_link(blob: bytes, name: str) -> dict[str, Any]:
    return dict(starocean.digests_of(blob), name=name, bytes=len(blob))


def an_edition(before: bytes, forms: dict[str, Any] | None = None) -> starocean.Edition:
    after = starocean.correct(before)
    return starocean.Edition(
        name="made-up",
        summary="a stand-in",
        reads="in.sfc",
        writes="out.sfc",
        size=len(before),
        before=starocean.digests_of(before),
        after=starocean.digests_of(after),
        source=a_link(b"a cartridge" * 8, "cartridge.sfc"),
        patch=a_link(b"a patch" * 8, "patch.xdelta"),
        forms=forms,
    )


def pinned(before: bytes) -> dict[str, Any]:
    headed = copier.for_sd2snes(starocean.correct(before), starocean.fix.SD2SNES_CHIPSET)
    assert len(headed) == WHOLE + 0x200, "the sd2snes form is the image plus a copier header"
    return dict(starocean.digests_of(headed), bytes=len(headed))


class FormsTest(unittest.TestCase):
    def test_an_edition_pinning_no_sd2snes_form_gets_the_plain_folders_only(self) -> None:
        # Arrange
        before = an_image(0x100000)
        edition = an_edition(before)

        # Act
        forms = starocean.forms_of(starocean.correct(before), edition)

        # Assert
        self.assertEqual(
            [name for name, _ in forms],
            [f"{starocean.EMULATOR}/out.sfc", f"{starocean.SUPER_EVERDRIVE}/out.sfc"],
        )

    def test_the_plain_folders_get_the_corrected_image_itself(self) -> None:
        # Arrange
        before = an_image(0x100000)
        edition = an_edition(before)

        # Act
        forms = dict(starocean.forms_of(starocean.correct(before), edition))

        # Assert
        self.assertEqual(forms[f"{starocean.EMULATOR}/out.sfc"], starocean.correct(before))
        self.assertEqual(forms[f"{starocean.SUPER_EVERDRIVE}/out.sfc"], starocean.correct(before))


class Sd2snesFormTest(unittest.TestCase):
    before: bytes
    headed: bytes
    forms: dict[str, bytes]

    @classmethod
    @override
    def setUpClass(cls) -> None:
        cls.before = an_image()
        produced = starocean.correct(cls.before)
        edition = an_edition(cls.before, {starocean.SD2SNES: pinned(cls.before)})
        cls.forms = dict(starocean.forms_of(produced, edition))
        cls.headed = cls.forms[f"{starocean.SD2SNES}/out.smc"]

    def test_the_sd2snes_and_the_fxpak_folders_get_the_same_file(self) -> None:
        # Arrange
        name = f"{starocean.FXPAK}/out.smc"

        # Act
        fxpak = self.forms[name]

        # Assert
        self.assertEqual(fxpak, self.headed)

    def test_it_is_the_size_the_firmware_maps_with_an_empty_copier_header(self) -> None:
        # Arrange
        expected = WHOLE + 0x200

        # Act
        found = (len(self.headed), self.headed[:0x200])

        # Assert
        self.assertEqual(found, (expected, bytes(0x200)))

    def test_it_keeps_the_chipset_mapper_six_was_written_for(self) -> None:
        # Arrange
        at = 0x200 + HEADER + 22

        # Act
        chipset = self.headed[at]

        # Assert
        self.assertEqual(chipset, 0x45)

    def test_a_form_the_manifest_did_not_pin_is_refused(self) -> None:
        # Arrange
        edition = an_edition(
            self.before, {starocean.SD2SNES: {"sha256": "0" * 64, "bytes": WHOLE + 0x200}}
        )

        # Act
        attempt = lambda: starocean.forms_of(starocean.correct(self.before), edition)  # noqa: E731

        # Assert
        self.assertRaises(starocean.Unexpected, attempt)

    def test_running_it_writes_every_folder(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        produced = starocean.correct(self.before)
        edition = an_edition(self.before, {starocean.SD2SNES: pinned(self.before)})
        (where / edition.reads).write_bytes(self.before)

        # Act
        starocean.run(edition, where, where / "dist")

        # Assert
        written = sorted(
            str(one.relative_to(where / "dist")) for one in (where / "dist").rglob("*.*")
        )
        self.assertEqual(
            written,
            ["emulator/out.sfc", "fxpak/out.smc", "sd2snes/out.smc", "supereverdrive/out.sfc"],
        )
        self.assertEqual((where / "dist" / "emulator" / "out.sfc").read_bytes(), produced)


if __name__ == "__main__":
    unittest.main()
