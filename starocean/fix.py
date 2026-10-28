import hashlib
import os
import sys
import zlib
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "snes-rom-image-python"))
sys.path.append(str(ROOT / "snes-rom-image-python" / "snes-mapper-python"))

from romimage import copier, rewrite
from romimage.rewrite import NoHeader

from starocean import editions
from starocean.errors import Corrupt, Missing, NotACartridge, Unexpected, Unrecognised
from starocean.version import VERSION

DIRECTORY_VARIABLE = "STAR_OCEAN_ROM_DIR"

DEFAULT_SOURCE = ROOT / "external" / "roms"

ALONGSIDE = ROOT.parent / "external" / "roms"

DEFAULT_DESTINATION = ROOT / "dist" / f"v{VERSION}"

SD2SNES_CHIPSET = 0x45


DIRECTORY_VARIABLES = (DIRECTORY_VARIABLE,)

DEFAULT_DIRECTORY = DEFAULT_SOURCE


def directories(environment: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    held = environment if environment is not None else os.environ
    wanted = [
        Path(where)
        for variable in DIRECTORY_VARIABLES
        for where in held.get(variable, "").split(os.pathsep)
        if where
    ]
    wanted += [ALONGSIDE, DEFAULT_DIRECTORY]
    seen: list[Path] = []
    for where in wanted:
        if where not in seen:
            seen.append(where)
    return tuple(seen)


def source_directory(
    environment: Mapping[str, str] | None = None, places: Sequence[Path] | None = None
) -> Path:
    named = (environment if environment is not None else os.environ).get(DIRECTORY_VARIABLE)
    if named:
        return Path(named)
    for place in places if places is not None else directories(environment):
        if place.is_dir():
            return place
    return DEFAULT_DIRECTORY


def digests_of(image: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(image) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(image).hexdigest(),
        "sha1": hashlib.sha1(image).hexdigest(),
        "sha256": hashlib.sha256(image).hexdigest(),
    }


def correct(image: bytes) -> bytes:
    try:
        corrected: bytes = rewrite.declare_rom_only(image)
        return corrected
    except NoHeader as reason:
        raise NotACartridge(
            f"nothing in these {len(image)} bytes reads as a cartridge header,"
            " so there is no header to correct"
        ) from reason


def confirm(image: bytes, edition: editions.Edition) -> editions.Edition:
    if len(image) != edition.size:
        raise Unrecognised(
            f"{edition.name} is {edition.size} bytes and this is {len(image)}."
            " A file of the wrong length is a different build rather than a"
            " different copy of this one"
        )

    found = digests_of(image)
    if found[editions.DECIDES] != edition.before[editions.DECIDES]:
        raise Unrecognised(
            f"this is the right length for {edition.name} but not the right content:"
            f" its {editions.DECIDES} is {found[editions.DECIDES]} and the manifest"
            f" pins {edition.before[editions.DECIDES]}. A file of the right length"
            " with the wrong content is usually a different revision of the rebuild"
        )

    _cross_check(edition.name, edition.before, found)
    return edition


def _cross_check(name: str, pinned: Mapping[str, str], found: Mapping[str, str]) -> None:
    for digest in editions.DIGESTS:
        if digest == editions.DECIDES or digest not in pinned:
            continue
        if pinned[digest].lower() != found[digest]:
            raise Corrupt(
                f"{name} matches on {editions.DECIDES} but not on {digest}:"
                f" the manifest says {pinned[digest]} and the file gives {found[digest]}."
                " A manifest that disagrees with itself was edited by hand or built"
                " from two different copies"
            )


def apply(image: bytes, edition: editions.Edition) -> bytes:
    confirm(image, edition)
    produced = correct(image)
    found = digests_of(produced)

    if found[editions.DECIDES] != edition.after[editions.DECIDES]:
        raise Unexpected(
            f"correcting {edition.name} produced an image whose {editions.DECIDES} is"
            f" {found[editions.DECIDES]}, and the manifest pins"
            f" {edition.after[editions.DECIDES]}. The input was the one named, so"
            " something about the correction itself has changed"
        )

    _cross_check(f"{edition.name} after correction", edition.after, found)
    return produced


def for_sd2snes(produced: bytes, edition: editions.Edition) -> bytes:
    headed: bytes = copier.for_sd2snes(produced, SD2SNES_CHIPSET)
    pinned = edition.forms[editions.SD2SNES]
    found = digests_of(headed)
    if found[editions.DECIDES] != pinned[editions.DECIDES]:
        raise Unexpected(
            f"the sd2snes form of {edition.name} has {editions.DECIDES}"
            f" {found[editions.DECIDES]}, and the manifest pins {pinned[editions.DECIDES]}"
        )
    _cross_check(f"{edition.name} for the sd2snes firmware", pinned, found)
    return headed


def forms_of(produced: bytes, edition: editions.Edition) -> list[tuple[str, bytes]]:
    plain = [
        (f"{editions.EMULATOR}/{edition.writes}", produced),
        (f"{editions.SUPER_EVERDRIVE}/{edition.writes}", produced),
    ]
    if editions.SD2SNES not in edition.forms:
        return plain
    headed = for_sd2snes(produced, edition)
    return [
        *plain,
        (f"{editions.SD2SNES}/{edition.headed}", headed),
        (f"{editions.FXPAK}/{edition.headed}", headed),
    ]


def run(edition: editions.Edition, source: Path | str, destination: Path | str) -> Path:
    reading = Path(source) / edition.reads
    if not reading.is_file():
        raise Missing(
            f"{edition.reads} is not in {source}. A copy you already own goes there,"
            " or wherever the source directory points"
        )

    produced = apply(reading.read_bytes(), edition)
    for name, written in forms_of(produced, edition):
        target = Path(destination) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(written)
    return Path(destination) / editions.EMULATOR / edition.writes


def main(argv: Sequence[str], catalogue: Sequence[editions.Edition] | None = None) -> int:
    source = Path(argv[0]) if argv else source_directory()
    destination = Path(argv[1]) if len(argv) > 1 else DEFAULT_DESTINATION
    catalogue = editions.EDITIONS if catalogue is None else catalogue
    done = refused = 0

    for edition in catalogue:
        try:
            written = run(edition, source, destination)
        except Missing as reason:
            print(f"  {edition.name}: not here, {reason}")
            continue
        except (NotACartridge, Unrecognised, Corrupt, Unexpected) as reason:
            refused += 1
            print(f"  {edition.name}: refused, {reason}")
            continue
        done += 1
        print(f"  {edition.name}: {edition.reads}")
        print(f"    -> {written} ({edition.after[editions.DECIDES]})")

    if refused:
        print(f"  {refused} refused, nothing was written for them")
        return 1
    if not done:
        print(f"  neither image was found in {source}, so nothing was written")
        return 2
    print(f"  {done} of {len(catalogue)} corrected")
    return 0


def command() -> None:
    raise SystemExit(main(sys.argv[1:]))


if __name__ == "__main__":
    command()
