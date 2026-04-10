import hashlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DATA_DIR  = Path(__file__).parent / "data"
SEEN_FILE = DATA_DIR / "seen_headlines.txt"
MAX_STORED = 2000  # rolling cap — old hashes drop off the bottom


def _hash(text: str) -> str:
    # MD5 is fine here, we just need stable dedup keys not cryptographic security.
    # Lowercasing catches minor title rewrites from the same story.
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def _load() -> set:
    DATA_DIR.mkdir(exist_ok=True)
    if not SEEN_FILE.exists():
        return set()
    return set(SEEN_FILE.read_text().splitlines())


def _save(seen: set):
    DATA_DIR.mkdir(exist_ok=True)
    entries = list(seen)[-MAX_STORED:]
    SEEN_FILE.write_text("\n".join(entries))


def filter_new(headlines: list[dict]) -> list[dict]:
    seen  = _load()
    new   = []
    added = set()

    for h in headlines:
        key = _hash(h["title"])
        if key not in seen:
            new.append(h)
            added.add(key)

    if added:
        seen.update(added)
        _save(seen)
        log.info(f"tracker: {len(new)} new headlines / {len(headlines)} total")
    else:
        log.info("tracker: no new headlines")

    return new
