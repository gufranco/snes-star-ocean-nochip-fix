# Working in this repository

Read [FAMILY.md](FAMILY.md) first. It is the standard every member of this
family carries, byte for byte, and it decides most questions before they are
asked. What follows is only what is true of this member. [README.md](README.md)
is the document written for a person.

## What this project is, in one paragraph

An image of Star Ocean that somebody else has already decompressed carries a
header describing a cartridge that no longer exists: it declares a coprocessor
that was removed and a size that is no longer its own. This corrects that header
in every mirror and recomputes the checksum. It decompresses nothing, models no
part, and knows nothing about time.

## The interface a caller drives

Two commands and a small library. `look` reads, `apply` corrects a supplied image
and hands back the bytes, and neither writes anything. `run` is the one that
writes.

- `look(where, editions, into)` reads every link of every chain and reports each
  as absent, matching, altered or corrupt. `report` turns those into lines and
  `verdict` into one word: `sound`, `wrong` or `nothing`. The last two are
  different answers on purpose, because a run that found nothing to check is not
  a run that found something broken.
- `apply(image, edition)` corrects a supplied image in memory.
- `confirm(data, edition)` is the check both ends of the run make.
- `named(name)` and `matching(digests)` reach an edition by its name or by what a
  file turned out to be.

Everything the package raises lives in
[`starocean/errors.py`](starocean/errors.py) and nowhere else, and that module
imports nothing from this package, nor from the member it consumes. There are
six, and they are separate classes because their fixes are separate: a file that
is not a file, one that matches nothing, one that matches a known bad dump, one
that is a cartridge but the wrong one, one that is absent, and a name no edition
goes by. A single refusal saying the digest did not match would tell a reader
nothing they could act on.

There is no clock and no part. These are files.

## The authority ladder

This one pins almost nothing, and that is the point.

1. **`snes-rom-image-python`**, which pins what a header means against Nintendo's
   development manual and does the rewrite.
2. **`snes-mapper-python`**, which pins where a header sits.
3. **The image itself**, confirmed by four digests before anything touches it and
   four more before the result is written.

`conformance/hardware.json` holds two facts and no more: the image length and the
size byte that follows from it. Everything else a reader might expect to find
here is in a sibling, on purpose. **A fact in two files is a fact that will
drift**, and the sibling is the one pinned against the manual.

## What is settled and what is not

**Settled: what changes.** Twelve bytes per image, six per header mirror across
two mirrors, and a test asserts that nothing outside a mirror moves.

**Settled: that the correction is idempotent.** The conformance run performs it
twice and compares what came out.

**Settled: every link of both chains.** Four digests each, at every step between
a cartridge somebody owns and the image this writes.

**Not settled: 3 things**, each in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with
what would close it. One is a size byte that comes from a rule rather than a
printed row, and two are boundaries listed so nobody mistakes them for gaps.

## The order matters, and it is the whole design

An image is confirmed against four digests _before_ the rewrite, so a file that
is not the one named never reaches it. The result is confirmed against four more
_before_ it is written, so a rewrite that produced something unforeseen ends as a
refusal rather than as a file on somebody's disk.

Weakening either end makes this unsafe to run unattended, which is the only
reason it exists in this shape.

## Test cartridges

[`conformance/testroms.json`](conformance/testroms.json) lists none, and says
why under `none`. Every image this tool touches is confirmed against the
digests of one of its two editions before anything reads it, so a test
cartridge is refused at the first step and exercises nothing here. On
2026-10-19 none of the 56 files under `snes-roms/5 Tools & Service Test Carts/`
matched either edition. There is no runner and no command. Header reading and
rewriting, which a test cartridge can exercise, are the work of
`snes-rom-image-python`, the submodule this member consumes.

## Files kept in `external/`

Everything this member reads and may not ship sits in `external/`, which git
ignores and Dropbox is told to leave alone, per FAMILY.md's "Where the files a
member reads are kept". [`artifacts.manifest.json`](artifacts.manifest.json)
names all 6 by size, CRC32, MD5, SHA-1 and SHA-256:

- `external/roms/`, the game, both patches and the images each patch produces,
  the links [`editions.manifest.json`](editions.manifest.json) pins and
  [ROMS.md](ROMS.md) lists. The fix and the verifier read them there, and the
  rebuilt images still go to `dist/`.

```bash
python3 -m conformance.external
python3 -m conformance.external --describe external/<file>
```

The first says which are here, verified, missing or wrong. The second prints
the manifest entry for a file being added, which gets its entry in the same
change.

## Every gate, in the order to run them

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
pnpm run format:check
uvx yamllint==1.38.0 --strict .
cov=(uvx --python 3.12 --from coverage==7.6.10 coverage)
"${cov[@]}" erase
for file in $(find starocean conformance -name '*.test.py' | sort); do
  "${cov[@]}" run -a "$file"
done
"${cov[@]}" report
```

Then the throughput floor, which runs outside the coverage step because a tracer
costs about ten times what the digests do:

```bash
python3 -m conformance.speed
```

And, with an image present, the run against the real files:

```bash
python3 conformance/against_images.test.py
```

`conformance/hardware.test.py` is in the coverage loop and needs no image. The
tests that need one skip rather than pass when it is absent, so a run that proved
nothing never reads as a run that proved something.

Everything under `conformance/` runs as a module. Run as a script, its own
directory goes on the import path and a file there shadows any standard library
module of the same name.

## Conventions that are not negotiable

| Thing                       | Rule                                                                                          |
| :-------------------------- | :-------------------------------------------------------------------------------------------- |
| Language                    | Python only                                                                                   |
| Comments                    | None in source, and a docstring counts as one                                                 |
| Test layout                 | `<module>.test.py` beside the module it covers                                                |
| Test structure              | Arrange, act, assert, each opened by its bare marker                                          |
| Package manager for tooling | pnpm, never npm                                                                               |
| Commits                     | Conventional Commits                                                                          |
| Coverage                    | 100% statements and branches, enforced                                                        |
| Types                       | `mypy` at strict, plus every optional error class                                             |
| Images                      | Never committed, in any form, for any reason. A digest is published; a byte of content is not |
| Header knowledge            | Belongs in the siblings. Adding a copy here creates a second source of truth                  |
| The dependency              | A submodule pinned by commit, never a copied file. See [FAMILY.md](FAMILY.md)                 |

The settings in [`pyproject.toml`](pyproject.toml) carry no comments, so their
reasons live here:

- No `[project]` table: this consumes a sibling member as a submodule, so a
  wheel built from here would install and then fail on its first import. The
  check that the dependency tree is empty reads the imports instead.
- `N818`: some exceptions are control flow signals rather than failures, named
  the way the standard library names `StopIteration`. Real failures end in
  `Error`.
- `BLE001` and `T201` in `environment.py` and the doctor: a check that throws
  has to become a line in the report rather than end the run, and printing is
  their output.
- `T201` in `fix.py`, `verify.py`, and the link, document and speed surveys:
  these are command line tools whose printed report is their output, and each
  exit code is the verdict.
- `E402` in `fix.py`, `verify.py` and the tests: the submodules go on `sys.path`
  before they can be imported, and nothing else runs first.
- `RUF100` in `conformance/family_*.py`: the
  shared file carries directives for rules a member may have off. The reference
  copy catches a stale one.
- `N999` and `PLR2004` in tests: a test file is named after its module with a
  dot, and its literals are the expected values.
- The `romimage.*` and `mapper.*` override in mypy: the submodules are checked
  in their own repositories, against their own gates.
- The `__main__` guard and `def command():` in coverage: each hands argv to a
  function that is itself tested.
  [starocean/package.test.py](starocean/package.test.py) asserts that the entry
  points resolve to `command`.
- `TYPE_CHECKING` blocks and bare `...` bodies in coverage: they never run, and
  Python 3.14 drops them before coverage sees them while 3.12 does not.
- `@unittest\.skipUnless\(CLOCKED,` in the coverage exclusions: this member is
  not a clocked part, so the family tests that drive a clock are skipped here
  and their bodies never run.
- `@unittest\.skipUnless\(A_PART,`,
  `@unittest\.skipUnless\(A_PART and BUILDABLE,` and
  `^def accounts_for_a_reset\(` in the coverage exclusions: this member is not a
  part, so the family tests that build a `Chip` and account for its reset are
  skipped here and their bodies never run.
- `@unittest\.skipUnless\(QUOTED,` in the coverage exclusions: this record
  quotes no document, so the family tests that hold a quote checker to the
  pipeline are skipped here.
- `@unittest\.skipUnless\(VARIANTS,` and `^def built\(` in the coverage
  exclusions: this package names no variants, so the family test that finds each
  one built in the readme is skipped here.
- `@unittest\.skipUnless\(SOLD_AS_A_COMPONENT,`, `^def machine_mentions\(` and
  `^def listing\(` in the coverage exclusions: this part only existed inside one
  machine, so the family sweep for machine names is skipped here.

The formatter's ignores in [`.prettierignore`](.prettierignore) carry no
comments either, so their reasons live here:

- `pnpm-lock.yaml` and `package-lock.json`: the package manager writes them, in
  its own layout, on every install.
- `node_modules/`, `.venv/`, `venv/`, `build/`, `dist/` and `*.egg-info/`:
  installed or built, never written by hand.
- `.coverage`, `coverage.json`, `htmlcov/` and the tool caches: the output of a
  run, never committed.
- `docs/`, `specs/`, `.work/` and `.claude/`: local working material, never
  committed.
- `snes-rom-image-python/`: a submodule. It is a member that formats and checks
  itself, and the commit pinned here is not this repository's to change.

## Layout

```
starocean/
  editions.py    the two chains, their digests, and looking one up
  fix.py         confirming, correcting, confirming again, writing
  verify.py      reading only, and what each link turned out to be
  errors.py      everything this package raises, importing nothing from it or from romimage
  doctor.py      what the machine and the package look like, for a report
  environment.py what the doctor reads about the machine
  version.py     rewritten by the release job and by nothing else
conformance/
  against_images.test.py  the real files, when they are here
  hardware.json           the two facts this file pins, and no more
  divergences.json        where a figure comes from a rule rather than a printed row
  documents.json          the development manual, by digest
  documents.py            checks a copy you hold and refuses any other file
  readme.test.py          the readme's examples, run as written
  links.py                the weekly check that every cited address still answers
  speed.py                the throughput floor
  family_*.test.py        the family standard, held as tests, one topic a file
  family_member.py        what this member answers to them
  family_shared.py        what more than one of them reads
  external.py       which files in external/ are here, verified, missing or wrong
editions.manifest.json        every filename and four digests per link, and the superseded ones
snes-rom-image-python/    the header reader, a submodule, with the memory map nested below it
external/           the game, the patches and the images they produce, never committed
artifacts.manifest.json  every file in external/, by size and every digest
```

## Things that will bite you

**The size byte comes from a rule, not a row.** Nintendo tabulates five sizes and
the largest is 64 megabit. Ninety six is not among them, so 0x0E comes from the
manual's rule that the byte is the base two logarithm of the length in kilobytes.
A reader checking the table will not find this value in it, which is why it is
named in `conformance/divergences.json`.

**Every mirror, not the first.** The rewrite belongs to the sibling and it changes
all of them. An image with one corrected header works in the tool it was tested
in and not on the machine it was built for.

**No image is in this repository**, only a manifest of names, lengths and four
digests each.

## Before calling anything finished

[`FAMILY.md`](FAMILY.md) carries a checklist under "What a new repository has to
have before it is a member". Every line on it was a defect found in one of these
repositories and fixed in all of them, so it is the list of things that have
actually gone wrong here rather than a list of good intentions. Read it before
adding a surface, and read it again before saying a change is done.

A change to `FAMILY.md` is a change to every member. Nothing here can catch it
being made in one of them and forgotten in the others, because a test in this
repository cannot see the others, so the check is a command rather than a suite:

```sh
shared() { sed '/^_Everything above this line/q' "$1"; }

grep -o 'github\.com/[^/]*/\([a-z0-9-]*\))' FAMILY.md | sed 's|.*/||; s|)||' | sort -u |
while read -r member; do
  other="../$member/FAMILY.md"
  [ -f "$other" ] || { echo "not on this machine: $member"; continue; }
  cmp <(shared FAMILY.md) <(shared "$other") && echo "match: $member"
done
```

The members come from the table at the top of `FAMILY.md` rather than from a glob
over the parent directory. The submodule under this repository carries a copy of
that file too, and it is a member in its own right rather than a copy to compare
against from here.

Two rules from that file are worth repeating because they are the ones skipped
most often:

**A check nobody has seen fail is not known to work.** Drive it, once,
deliberately, against input that should fail it.

**Silence and success produce the same output.** A run that found no image
reports `nothing` rather than `sound`, which is the whole reason those are two
words.

## What a change is expected to leave behind

A gate that would have caught the bug. A change that alters what this writes also
updates the manifest, records the digests it replaces under `supersedes` with the
upstream commit and the reason, and never the other way round.
