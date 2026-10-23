"""Source verification against a SHA-256 manifest.

The manifest is a plain text file in the format ``sha256sum`` writes and
``sha256sum -c`` (or ``shasum -a 256 -c``) reads: one line per file, the
64-character hex digest, two spaces, then the path relative to the
manifest's directory. Using that format means a registered input can be
verified with standard tools, without Python and without this package.

What this module does and does not do. ``verify_sources`` checks that each
listed file exists and that its bytes match the registered digest, and
raises on the first mismatch or missing file unless asked to collect
everything. It does not fetch files, does not decide which files a pipeline
needs, and does not know a source's vintage or licence: those are recorded
by hand alongside the manifest (in a paper's ``SOURCES.md``). A pipeline is
only as verified as the manifest it is checked against.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

_LINE = re.compile(r"^([0-9a-fA-F]{64}) [ *](.+)$")


@dataclass
class VerificationResult:
    verified: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    mismatched: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.mismatched


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    """Hex SHA-256 of a file, read in chunks (inputs can be hundreds of MB)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def read_manifest(path: str | Path) -> dict[str, str]:
    """Parse a sha256sum-format manifest into {relative path: digest}.

    Blank lines and lines starting with '#' are ignored. Any other line that
    is not a well-formed entry raises, as does a path listed twice: a
    manifest that cannot be read unambiguously cannot verify anything.
    """
    entries: dict[str, str] = {}
    for n, raw in enumerate(Path(path).read_text(encoding="utf-8")
                            .splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            raise ValueError(f"{path}:{n}: not a sha256sum entry: {raw!r}")
        digest, rel = m.group(1).lower(), m.group(2)
        if rel in entries:
            raise ValueError(f"{path}:{n}: {rel!r} listed more than once")
        entries[rel] = digest
    return entries


def verify_sources(manifest: str | Path, only: list[str] | None = None,
                   raise_on_error: bool = True) -> VerificationResult:
    """Check files against a manifest; paths resolve against its directory.

    `only` restricts the check to the listed relative paths (each must be in
    the manifest). With raise_on_error=True (the default) the call raises on
    the first missing or mismatched file, so a pipeline that calls it cannot
    proceed on unverified inputs. With raise_on_error=False every entry is
    checked and the result lists all problems, for reporting.
    """
    manifest = Path(manifest)
    entries = read_manifest(manifest)
    if only is not None:
        unknown = [p for p in only if p not in entries]
        if unknown:
            raise ValueError(f"not registered in {manifest}: {unknown}")
        entries = {p: entries[p] for p in only}
    base = manifest.parent
    res = VerificationResult()
    for rel, want in entries.items():
        target = base / rel
        if not target.is_file():
            if raise_on_error:
                raise FileNotFoundError(
                    f"registered source missing: {rel} (expected at "
                    f"{target}); obtain it as described in SOURCES.md")
            res.missing.append(rel)
            continue
        got = sha256_file(target)
        if got != want:
            if raise_on_error:
                raise ValueError(
                    f"registered source differs from the manifest: {rel}\n"
                    f"  expected {want}\n  found    {got}\n"
                    f"  the file is a different vintage or has been altered")
            res.mismatched.append((rel, want, got))
            continue
        res.verified.append(rel)
    return res


def write_manifest(paths: list[str | Path], manifest: str | Path) -> None:
    """Write a sha256sum-format manifest for `paths`, relative to its folder."""
    manifest = Path(manifest)
    base = manifest.parent.resolve()
    lines = []
    for p in sorted(Path(x).resolve() for x in paths):
        lines.append(f"{sha256_file(p)}  {p.relative_to(base).as_posix()}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8",
                        newline="\n")
