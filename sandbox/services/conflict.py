# conflict.py
from dataclasses import dataclass
from services.file_cache import generate_etag_from_metadata


@dataclass(frozen=True)
class ConflictResult:
    conflict: bool
    reason: str = ""        
    current_etag: str = ""    

def check_write_conflict(
    expected_etag: str,
    current_modified: str,
    current_size: int,
    base_mtime: str = "",
) -> ConflictResult:

    current_etag = generate_etag_from_metadata(current_modified, current_size)

    if base_mtime:
        # Stage 1 — mtime gate: if mtime has not advanced, no conflict.
        if current_modified == base_mtime:
            return ConflictResult(conflict=False)

        # Stage 2 — the file's mtime changed; check if the content also changed
        # relative to what the client last read (expected_etag was built from
        # base_mtime + size at read time).
        vscode_etag = generate_etag_from_metadata(base_mtime, current_size)
        if vscode_etag != expected_etag:
            return ConflictResult(
                conflict=True,
                reason=(
                    "File metadata changed since last read — "
                    "another process has modified this file."
                ),
                current_etag=current_etag,
            )
        return ConflictResult(conflict=False)

    # Stage 3 — strict fallback (no base_mtime supplied): flag on ANY metadata
    # change.  This is intentionally strict; callers that want optimistic
    # concurrency should supply base_mtime.
    if current_etag != expected_etag:
        return ConflictResult(
            conflict=True,
            reason=(
                "File metadata changed since last read — "
                "another process has modified this file."
            ),
            current_etag=current_etag,
        )
    return ConflictResult(conflict=False)
