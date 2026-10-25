"""Delete DocBot's local data (database, stored files, model cache): `python scripts/reset_demo.py`.

FR-023: bulk deletion exists only here, never in the API, and only after typing RESET.
"""

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import Settings  # noqa: E402


def _refusal(data_dir: Path) -> str | None:
    target = data_dir.resolve()
    if target == Path(target.anchor) or target == Path.home().resolve():
        return f"{target} is the filesystem root or your home folder"
    if target == Path.cwd().resolve() or target in Path.cwd().resolve().parents:
        return f"{target} contains the current folder"
    if not (target / "docbot.db").exists() and not (target / "files").is_dir():
        return f"{target} does not look like a DocBot data folder (no docbot.db or files/)"
    return None


def reset(data_dir: Path, ask: Callable[[str], str] = input) -> int:
    if not data_dir.exists():
        print(f"Nothing to delete: {data_dir} does not exist.")
        return 0
    reason = _refusal(data_dir)
    if reason:
        print(f"Refusing to delete {data_dir}: {reason}. Check DOCBOT_DATA_DIR.")
        return 2
    answer = ask(f"This deletes {data_dir.resolve()} (database, uploaded files, model cache).\n"
                 "Type RESET to confirm: ")
    if answer.strip() != "RESET":
        print("Not confirmed; nothing was deleted.")
        return 1
    shutil.rmtree(data_dir)
    print(f"Deleted {data_dir}. Restart the API to begin with an empty library.")
    return 0


def main() -> int:
    return reset(Settings().data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
