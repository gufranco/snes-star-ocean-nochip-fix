from __future__ import annotations

import json
import platform
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Sequence


def _version(where: Path | None = None) -> str:
    found = re.search(
        r"""VERSION\s*[:=][^"']*["']([^"']+)["']""",
        (where or Path(__file__).resolve().parent / "version.py").read_text(),
    )
    return found.group(1) if found else "unknown"


VERSION = _version()

ROOT = Path(__file__).resolve().parent.parent

from starocean import environment  # noqa: E402

MANIFEST = ROOT / "editions.manifest.json"

SOURCE = ROOT / "roms"

DESTINATION = ROOT / "dist"

WRITES = "writes"

STEPS = 4

SUBMODULES = ("snes-rom-image-python",)

OLDEST_PYTHON = (3, 12)


class Finding:
    __slots__ = ("advice", "detail", "name", "ok")

    def __init__(self, name: str, ok: bool, detail: str, advice: str | None = None) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self) -> str:
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self) -> str:
        if self.ok or not self.advice:
            return self.line
        return f"{self.line}\n         {self.advice}"

    @override
    def __repr__(self) -> str:
        return f"<Finding {self.name} {'ok' if self.ok else 'not ok'}>"


def _python() -> Finding:
    return Finding(
        "python",
        sys.version_info[:2] >= OLDEST_PYTHON,
        f"{platform.python_version()} on {platform.system()} {platform.machine()}",
        f"this package needs {OLDEST_PYTHON[0]}.{OLDEST_PYTHON[1]} or newer",
    )


def _package() -> Finding:
    return Finding("starocean", True, f"version {VERSION}")


def _loaded() -> Any:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from starocean import editions, verify

    return editions, verify


def _editions() -> Finding:
    try:
        editions, _ = _loaded()
        held = editions.EDITIONS
    except Exception as trouble:
        return Finding(
            "editions",
            False,
            f"{type(trouble).__name__}: {trouble}",
            "the package could not be imported, so nothing below it could be"
            " looked at; the submodule line says why",
        )
    short = sorted(one.name for one in held if len(one.chain()) < STEPS)
    return Finding(
        "editions",
        not short,
        ", ".join(f"{one.name} at {one.size} bytes" for one in held),
        f"{', '.join(short)} names fewer than {STEPS} steps, and a chain with a"
        " link missing cannot say which step to redo",
    )


def _chain() -> list[Finding]:
    try:
        editions, _ = _loaded()
        held = editions.EDITIONS
    except Exception:
        return []
    found = []
    for one in held:
        for step in one.chain():
            place = DESTINATION if step.what == WRITES else SOURCE
            where = place / step.name
            found.append(
                Finding(
                    f"{one.name}: {step.what}",
                    True,
                    f"{step.name} is at {place.name}/"
                    if where.is_file()
                    else f"{step.name} is not at {place.name}/",
                )
            )
    return found


def _submodule(name: str, root: Path = ROOT) -> Finding:
    where = root / name
    if (where / "pyproject.toml").is_file():
        return Finding(f"submodule {name}", True, f"checked out at {where}")
    return Finding(
        f"submodule {name}",
        False,
        f"{where} is empty" if where.is_dir() else f"{where} is not there",
        "this package imports it by name, so nothing here runs without it;"
        " git submodule update --init --recursive",
    )


def _manifest(path: Path | str = MANIFEST) -> Finding:
    try:
        held = json.loads(Path(path).read_text())
    except OSError as trouble:
        return Finding(
            "manifest",
            False,
            f"could not be read: {trouble}",
            "the manifest is what every digest is checked against; without it"
            " nothing can be identified at all",
        )
    except ValueError as trouble:
        return Finding(
            "manifest",
            False,
            f"is not readable as JSON: {trouble}",
            "the file is here and damaged, which is worse than absent",
        )
    named = held.get("editions") or []
    superseded = [one for one in named if one.get("supersedes")]
    return Finding(
        "manifest",
        bool(named),
        f"{len(named)} editions pinned"
        + (
            f", {len(superseded)} carrying superseded digests"
            if superseded
            else ", none carrying superseded digests"
        ),
        "a manifest pinning nothing identifies nothing",
    )


def _source(where: Path = SOURCE) -> Finding:
    if not where.is_dir():
        return Finding(
            "images",
            True,
            f"no {where}, so there is nothing to correct on this machine yet",
        )
    try:
        present = [one for one in where.iterdir() if one.is_file()]
    except OSError as trouble:
        return Finding("images", False, f"could not be read: {trouble}")
    return Finding(
        "images",
        True,
        f"{len(present)} files at {where}"
        if present
        else f"{where} is here and empty, so there is nothing to correct yet",
    )


def examine(
    manifest: Path | str = MANIFEST,
    root: Path = ROOT,
    source: Path = SOURCE,
) -> list[Finding]:
    return [
        _python(),
        _package(),
        _editions(),
        *(_submodule(name, root) for name in SUBMODULES),
        _manifest(manifest),
        _source(source),
        *_chain(),
    ]


def report(found: Sequence[Finding]) -> list[str]:
    unwell = [one for one in found if not one.ok]
    lines = [f"starocean {VERSION} on {platform.python_version()}, {platform.system()}", ""]
    lines.append("  the machine")
    lines.extend(environment.lines(ROOT))
    lines.append("")
    lines.append("  this package")
    lines.extend(one.report for one in found)
    lines.append("")
    if unwell:
        lines.append(f"  {len(unwell)} of {len(found)} checks did not pass")
    else:
        lines.append(f"  {len(found)} checks, nothing to report")
    return lines


def main(
    argv: Sequence[str] = (),
    examine: Callable[..., list[Finding]] = examine,
    say: Callable[[str], None] = print,
) -> int:
    found = examine()
    for line in report(found):
        say(line)
    return 1 if any(not one.ok for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
