"""Database-free reproduction: python -m ewaf.revised.demo [--json]."""
import argparse
import json
from .engine import configure, calculate
from .fixtures import example_pool


def main():
    parser = argparse.ArgumentParser(description='Synthetic revised EWAF document example; never an official run.')
    parser.add_argument('--json', action='store_true', help='Print the full exact configuration, pool and results.')
    args = parser.parse_args()
    config, pool = configure(), example_pool()
    result = calculate(pool, config)
    if args.json:
        print(json.dumps({'configuration': config.data, 'pool': pool.data, 'result': result}, indent=2))
    else:
        print('Synthetic demonstration only. Illustrative reconstructed matrix.')
        validation = config.data['ahp']
        print(f'lambda={validation["lambda_max_estimate"]["exact"]}; CI={validation["ci"]["exact"]}; '
              f'CR={validation["cr"]["exact"]} follows by construction.')
        for row in result['applicants']:
            print(f'{row["applicant"]}: exact={row["score_0_100"]["exact"]}; display={row["display_score"]}; '
                  f'internal rank={row["rank"]}; {row["classification"]}')
        print('No configuration authorization, beneficiary decision or publication.')


if __name__ == '__main__':
    main()
