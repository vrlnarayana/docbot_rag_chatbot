"""Generate the sample corpus and golden set (FR-030): `python scripts/generate_samples.py`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.samples import generate  # noqa: E402
from app.settings import Settings  # noqa: E402


def main() -> int:
    settings = Settings()
    paths = generate(settings.sample_dir, settings.golden_path)
    for path in paths:
        print(f"  {path}")
    print(f"Wrote {len(paths)} sample documents to {settings.sample_dir}/")
    print(f"Wrote the golden set to {settings.golden_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
