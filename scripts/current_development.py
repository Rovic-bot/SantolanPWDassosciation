"""Operate the fresh local database; never seed data or fall back to an archive."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fresh_development import main


if __name__ == '__main__':
    main()
