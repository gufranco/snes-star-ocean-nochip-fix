import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, override

from .errors import UnknownEdition

ROOT = Path(__file__).resolve().parent.parent

MANIFEST = ROOT / "editions.manifest.json"

DIGESTS = ("crc32", "md5", "sha1", "sha256")

DECIDES = "sha256"

DIGEST_WIDTHS = {"crc32": 8, "md5": 32, "sha1": 40, "sha256": 64}

EXPECTED_BYTES = 0xC00000

EMULATOR = "emulator"
SUPER_EVERDRIVE = "supereverdrive"
SD2SNES = "sd2snes"
FXPAK = "fxpak"
DEVICES = (EMULATOR, SUPER_EVERDRIVE, SD2SNES, FXPAK)
HEADED_SUFFIX = ".smc"


class Patch:
    __slots__ = ("archive", "author", "name", "note", "version", "where")

    def __init__(
        self,
        name: str,
        version: str,
        author: str,
        where: str,
        note: str,
        archive: Mapping[str, Any],
    ) -> None:
        self.name = name
        self.version = version
        self.author = author
        self.where = where
        self.note = note
        self.archive = archive

    @override
    def __repr__(self) -> str:
        return f"<Patch {self.name} {self.version}, by {self.author}>"


class Step:
    __slots__ = ("held", "name", "produced", "what")

    def __init__(
        self, what: str, name: str, held: Mapping[str, Any], produced: bool = False
    ) -> None:
        self.what = what
        self.name = name
        self.held = held
        self.produced = produced

    @property
    def bytes(self) -> int:
        held: int = self.held["bytes"]
        return held

    def digest(self, which: str | None = None) -> str:
        held: str = self.held[which or DECIDES]
        return held

    @override
    def __repr__(self) -> str:
        return f"<Step {self.what}: {self.name}, {self.bytes} bytes>"


class Edition:
    __slots__ = (
        "after",
        "before",
        "forms",
        "name",
        "patch",
        "reads",
        "size",
        "source",
        "summary",
        "writes",
    )

    def __init__(
        self,
        name: str,
        summary: str,
        reads: str,
        writes: str,
        size: int,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        source: Mapping[str, Any],
        patch: Mapping[str, Any],
        forms: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.name = name
        self.summary = summary
        self.reads = reads
        self.writes = writes
        self.size = size
        self.before = before
        self.after = after
        self.source = source
        self.patch = patch
        self.forms = dict(forms or {})

    @property
    def headed(self) -> str:
        return Path(self.writes).with_suffix(HEADED_SUFFIX).name

    def chain(self) -> tuple[Step, ...]:
        plain = Step(
            "writes", f"{EMULATOR}/{self.writes}", dict(self.after, bytes=self.size), produced=True
        )
        headed = (
            (Step("writes", f"{SD2SNES}/{self.headed}", self.forms[SD2SNES], produced=True),)
            if SD2SNES in self.forms
            else ()
        )
        return (
            Step("source", self.source["name"], self.source),
            Step("patch", self.patch["name"], self.patch),
            Step("reads", self.reads, dict(self.before, bytes=self.size)),
            plain,
            *headed,
        )

    @override
    def __repr__(self) -> str:
        return f"<Edition {self.name}, {self.size} bytes>"


def load_patch(path: Path | str | None = None) -> Patch:
    with Path(path or MANIFEST).open() as handle:
        held = json.load(handle)["patch"]
    return Patch(
        name=held["name"],
        version=held["version"],
        author=held["author"],
        where=held["where"],
        note=held["note"],
        archive=held["archive"],
    )


def load(path: Path | str | None = None) -> tuple[Edition, ...]:
    with Path(path or MANIFEST).open() as handle:
        held = json.load(handle)
    return tuple(
        Edition(
            name=entry["name"],
            summary=entry["summary"],
            reads=entry["reads"],
            writes=entry["writes"],
            size=entry["bytes"],
            before=entry["before"],
            after=entry["after"],
            source=entry["source"],
            patch=entry["patch"],
            forms=entry.get("forms"),
        )
        for entry in held["editions"]
    )


EDITIONS = load()

PATCH = load_patch()


def matching(digest: str, among: Sequence[Edition] | None = None) -> Edition | None:
    for edition in EDITIONS if among is None else among:
        if edition.before[DECIDES] == digest:
            return edition
    return None


def named(name: str, among: Sequence[Edition] | None = None) -> Edition:
    among = EDITIONS if among is None else among
    for edition in among:
        if edition.name == name:
            return edition
    raise UnknownEdition(
        f"{name} is not an edition this corrects;"
        f" there are {', '.join(edition.name for edition in among)}"
    )
