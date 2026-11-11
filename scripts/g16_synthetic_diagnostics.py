"""Replay a fixed G16 source fixture without Django setup or any database access."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ewaf.ranking_diagnostics import compare_fixture
from ewaf.ranking_fixtures import FIXTURES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture', choices=tuple(FIXTURES))
    args = parser.parse_args()
    result = compare_fixture(args.fixture)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    sys.exit(main())
