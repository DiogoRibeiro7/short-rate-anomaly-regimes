"""Verification of provider downloads against the frozen vintage.

Every public source this project uses is served from a current-vintage endpoint:
``fredgraph.csv?id=FEDFUNDS`` returns the latest revision, and the Kenneth
French, global-q, and Wharton files are whatever the provider publishes today.
Downloading such a URL and recording the checksum of whatever arrived describes
a download; it does not reconstruct a vintage.

This module inverts that relationship. The checksums committed in
``artifacts/provenance`` are treated as *expected* hashes. An acquisition run
downloads, hashes, and compares; on a mismatch it aborts before writing anything
and leaves the recorded hash untouched. Only an explicit update run --- the
``--update-vintage`` flag, reached through the ``make update-vintage-*``
targets --- may record a new expected hash.

A verification run also short-circuits the network when the immutable raw file
is already on disk and already hashes to the expected value, which makes a
rebuild from restored raw bytes fully offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from short_rate_anomaly_regimes.exceptions import FrozenVintageError
from short_rate_anomaly_regimes.provenance import sha256_file

#: The only flag that may overwrite a recorded expected hash. It is never passed
#: by ``make reproduce``; it is reached only through ``make update-vintage-*``.
UPDATE_VINTAGE_FLAG = "--update-vintage"

#: The manifest field carrying the expected hash of the raw provider bytes.
RAW_SHA256_FIELD = "raw_sha256"


class VintageMode(str, Enum):
    """Whether an acquisition run verifies the frozen vintage or replaces it."""

    #: Download, compare against the recorded expected hash, abort on mismatch,
    #: and never rewrite a committed provenance manifest.
    VERIFY = "verify"
    #: Download and record a new expected hash, overwriting the committed one.
    UPDATE = "update"

    @property
    def writes_provenance(self) -> bool:
        """Return whether a run in this mode may write a provenance manifest."""
        return self is VintageMode.UPDATE


#: Where each acquisition path's fetcher returns bytes and response headers.
FetchCallable = Callable[[], tuple[bytes, Mapping[str, str]]]


@dataclass(frozen=True, slots=True)
class VerifiedPayload:
    """Provider bytes that are known to match the frozen vintage, or to replace it."""

    payload: bytes
    sha256: str
    headers: dict[str, str]
    mode: VintageMode
    manifest_path: Path
    #: ``frozen_local_raw_file`` when the download was skipped because the
    #: immutable raw file already matched, ``provider_download`` otherwise.
    byte_source: str

    @property
    def reused_local_raw(self) -> bool:
        """Return whether the bytes came from the local raw file rather than the network."""
        return self.byte_source == "frozen_local_raw_file"


def recorded_sha256(manifest_path: Path, *, field: str = RAW_SHA256_FIELD) -> str | None:
    """Return the expected hash recorded in a shipped provenance manifest.

    Args:
        manifest_path: Path to the committed provenance manifest for one source.
        field: Manifest field carrying the expected hash.

    Returns:
        The recorded hexadecimal digest, or ``None`` when the manifest is absent,
        is not readable as JSON, or does not carry a usable value in ``field``.
    """
    if not manifest_path.is_file():
        return None
    try:
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _mismatch_message(
    *,
    source_label: str,
    url: str,
    expected: str,
    received: str,
    manifest_path: Path,
    raw_path: Path,
    update_command: str,
) -> str:
    return "\n".join(
        (
            f"Frozen-vintage verification failed for {source_label}.",
            f"  expected sha256 {expected}",
            f"  received sha256 {received}",
            f"  expected hash recorded in {manifest_path.as_posix()}",
            f"  bytes received from {url}",
            "The provider is serving different bytes than the vintage this archive's published "
            "results were built from, so the rebuild would not reproduce them. Nothing was "
            "written and no recorded hash was changed.",
            "What to do next:",
            "  1. To reproduce the published results, obtain the frozen vintage from an "
            "immutable source (ALFRED for FRED series, Internet Archive snapshots for the "
            "publication-era files; see docs/DATA_ACQUISITION.md), place those bytes at "
            f"{raw_path.as_posix()}, and run this command again.",
            "  2. To move this archive onto the vintage the provider serves now, run "
            f"`{update_command}`. That is the only operation permitted to overwrite a recorded "
            "expected hash. It changes the inputs of every downstream result, so re-run "
            "`make reproduce` in full afterwards and report the new vintage.",
        )
    )


def _unrecorded_message(
    *,
    source_label: str,
    url: str,
    received: str,
    manifest_path: Path,
    reason: str,
    update_command: str,
) -> str:
    return "\n".join(
        (
            f"No frozen-vintage hash is recorded for {source_label}.",
            f"  expected sha256 none recorded ({reason})",
            f"  received sha256 {received}",
            f"  expected hash would be read from {manifest_path.as_posix()}",
            f"  bytes received from {url}",
            "A verification run may not establish a frozen vintage, because there would be "
            "nothing to verify the download against. Nothing was written.",
            "What to do next:",
            "  1. If this archive should already carry the vintage, restore "
            f"{manifest_path.as_posix()} from the release rather than regenerating it.",
            "  2. To record this download as the frozen vintage deliberately, run "
            f"`{update_command}`. That is the only operation permitted to write an expected "
            "hash. It defines the inputs of every downstream result, so re-run `make reproduce` "
            "in full afterwards and report the new vintage.",
        )
    )


def acquire_frozen_payload(
    *,
    source_label: str,
    url: str,
    manifest_path: Path,
    raw_path: Path,
    mode: VintageMode,
    update_command: str,
    fetch: FetchCallable,
    field: str = RAW_SHA256_FIELD,
) -> VerifiedPayload:
    """Obtain provider bytes that are known to match the frozen vintage.

    In :attr:`VintageMode.VERIFY` the recorded expected hash must exist and the
    bytes must hash to it. The immutable raw file is consulted first: when it is
    present and already matches, ``fetch`` is never called and the run needs no
    network. In :attr:`VintageMode.UPDATE` the bytes are fetched and returned
    without comparison, so that the caller may record them as the new vintage.

    Args:
        source_label: Human-readable identifier naming the series or dataset,
            reported verbatim in the abort message.
        url: Provider URL the bytes would be or were fetched from.
        manifest_path: Committed provenance manifest carrying the expected hash.
        raw_path: Immutable path of the raw provider bytes.
        mode: Verification or update.
        update_command: The command that is allowed to overwrite the expected
            hash, quoted in the abort message.
        fetch: Callable returning the downloaded bytes and the response headers.
        field: Manifest field carrying the expected hash.

    Returns:
        The verified payload with its digest and the response headers.

    Raises:
        FrozenVintageError: In verification mode, when no expected hash is
            recorded or when the bytes do not hash to the recorded value.
    """
    if mode is VintageMode.UPDATE:
        payload, headers = fetch()
        return VerifiedPayload(
            payload=payload,
            sha256=hashlib.sha256(payload).hexdigest(),
            headers=dict(headers),
            mode=mode,
            manifest_path=manifest_path,
            byte_source="provider_download",
        )

    expected = recorded_sha256(manifest_path, field=field)
    if expected is not None and raw_path.is_file() and sha256_file(raw_path) == expected:
        return VerifiedPayload(
            payload=raw_path.read_bytes(),
            sha256=expected,
            headers={},
            mode=mode,
            manifest_path=manifest_path,
            byte_source="frozen_local_raw_file",
        )

    payload, headers = fetch()
    received = hashlib.sha256(payload).hexdigest()
    if expected is None:
        reason = (
            f"{manifest_path.as_posix()} is absent"
            if not manifest_path.is_file()
            else f"{manifest_path.as_posix()} carries no usable {field!r} field"
        )
        raise FrozenVintageError(
            _unrecorded_message(
                source_label=source_label,
                url=url,
                received=received,
                manifest_path=manifest_path,
                reason=reason,
                update_command=update_command,
            )
        )
    if received != expected:
        raise FrozenVintageError(
            _mismatch_message(
                source_label=source_label,
                url=url,
                expected=expected,
                received=received,
                manifest_path=manifest_path,
                raw_path=raw_path,
                update_command=update_command,
            )
        )
    return VerifiedPayload(
        payload=payload,
        sha256=received,
        headers=dict(headers),
        mode=mode,
        manifest_path=manifest_path,
        byte_source="provider_download",
    )


def parse_vintage_mode(argv: Sequence[str] | None, *, description: str) -> VintageMode:
    """Parse an acquisition script's arguments into a vintage mode.

    Verification is the default and the only mode ``make reproduce`` ever runs.
    Abbreviation matching is disabled so that no shorter prefix can select the
    update flag by accident.

    Args:
        argv: Command-line arguments, or ``None`` to read ``sys.argv``.
        description: Script description shown in ``--help``.

    Returns:
        :attr:`VintageMode.UPDATE` when the explicit flag is given, otherwise
        :attr:`VintageMode.VERIFY`.
    """
    parser = argparse.ArgumentParser(description=description, allow_abbrev=False)
    parser.add_argument(
        UPDATE_VINTAGE_FLAG,
        action="store_true",
        help=(
            "Replace the frozen vintage with whatever the providers serve now and overwrite the "
            "recorded expected hashes. This is the only way to change a frozen vintage, it "
            "changes the inputs of every downstream result, and `make reproduce` never passes "
            "it. Without this flag the run verifies the download against the recorded hash and "
            "aborts on a mismatch."
        ),
    )
    arguments = parser.parse_args(argv)
    return VintageMode.UPDATE if arguments.update_vintage else VintageMode.VERIFY


def announce_mode(mode: VintageMode) -> str:
    """Return the banner an acquisition script prints before it touches a provider."""
    if mode is VintageMode.UPDATE:
        return (
            "MODE update-vintage: recorded expected hashes WILL be overwritten with whatever "
            "the providers serve now. Every downstream result changes; re-run `make reproduce` "
            "in full."
        )
    return (
        "MODE verify: downloads are checked against the expected hashes recorded in "
        "artifacts/provenance and the run aborts on a mismatch. No provenance manifest is "
        "rewritten."
    )
