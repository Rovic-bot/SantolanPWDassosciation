"""Print one pinned synthetic G17 history; never initialize Django or a database."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ewaf.recalculation_diagnostics import simulate_fixture
from ewaf.recalculation_fixtures import SCENARIOS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture', choices=tuple(SCENARIOS))
    args = parser.parse_args()
    result = simulate_fixture(args.fixture)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    sys.exit(main())
