"""Download and checksum-verify the two Matbench v0.1 source tasks."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

FILES = {
    "matbench_expt_gap.json.gz": (
        "https://ml.materialsproject.org/projects/matbench_expt_gap.json.gz",
        "783e7d1461eb83b00b2f2942da4b95fda5e58a0d1ae26b581c24cf8a82ca75b2",
    ),
    "matbench_log_kvrh.json.gz": (
        "https://ml.materialsproject.org/projects/matbench_log_kvrh.json.gz",
        "44b113ddb7e23aa18731a62c74afa7e5aa654199e0db5f951c8248a00955c9cd",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in FILES.items():
        destination = RAW / name
        if not destination.exists():
            print(f"Downloading {name}...")
            urllib.request.urlretrieve(url, destination)
        observed = sha256(destination)
        if observed != expected:
            raise RuntimeError(
                f"Checksum mismatch for {name}: expected {expected}, got {observed}"
            )
        print(f"Verified {name}: {observed}")


if __name__ == "__main__":
    main()
