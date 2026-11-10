# artifacts.py
# Audio artifact storage for the Darwin audio engine: seed uploads and
# candidate WAVs live under a dedicated data directory (gitignored), addressed
# by strictly-validated hex ids (path-traversal safe by construction).

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.speech.exceptions import SpeechError

_SAFE_ID = re.compile(r"^[a-f0-9]{8,64}$")


class ArtifactError(SpeechError):
    """Invalid artifact id or unavailable artifact."""


class AudioArtifactStore:
    def __init__(self, base_dir: Path | str) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, ref: str) -> Path:
        # refs look like "<run_id>/<genome_id>.wav" with hex-only components
        parts = ref.split("/")
        if len(parts) != 2 or not _SAFE_ID.match(parts[0]) or not _SAFE_ID.match(
            parts[1].split(".", 1)[0]
        ):
            raise ArtifactError(f"Invalid audio artifact reference: {ref!r}")
        path = (self.base_dir / parts[0] / parts[1]).resolve()
        if self.base_dir.resolve() not in path.parents:
            raise ArtifactError(f"Artifact path escapes storage root: {ref!r}")
        return path

    def new_ref(self, run_scope: str) -> tuple[str, Path]:
        """Allocate a fresh reference and its path. run_scope must be hex."""
        scope = run_scope if _SAFE_ID.match(run_scope) else uuid.uuid4().hex[:12]
        artifact_id = uuid.uuid4().hex[:16]
        ref = f"{scope}/{artifact_id}.wav"
        path = self.base_dir / scope / f"{artifact_id}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        return ref, path

    def read_bytes(self, ref: str) -> bytes:
        path = self._resolve(ref)
        if not path.exists():
            raise ArtifactError(f"Audio artifact not found: {ref!r}")
        return path.read_bytes()

    def write_bytes(self, path: Path, blob: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)

    def exists(self, ref: str) -> bool:
        try:
            return self._resolve(ref).exists()
        except ArtifactError:
            return False
