"""Read-only preservation/test evidence for the owner's remaining-phase review."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/remaining-phases-2026-10-23'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main():
    phase = sys.argv[1]
    destination = BASE / phase
    baseline = json.loads((BASE / 'baseline.json').read_text(encoding='utf-8'))
    changed = {name: {'before': old, 'after': digest(ROOT / name)}
               for name, old in baseline['files'].items() if digest(ROOT / name) != old}
    protected = [name for name, old in baseline['protected'].items() if digest(ROOT / name) != old]
    original = json.loads((ROOT / 'docs/added-targets-phase1-2026-10-23/baseline.json').read_text(encoding='utf-8'))
    original_files = {item['path']: item['sha256'] for item in original['files']}
    original_protected_diff = [name for name in original['protected_paths']
                              if digest(ROOT / name) != original_files[name]]
    migrations = [name for name in changed if '/migrations/' in name]
    pattern = rb'^## 8\. .*?(?=^## 9\. )'
    sections = [re.search(pattern, (ROOT / name).read_bytes(), re.M | re.S).group()
                for name in ('OVERALL_SYSTEM_SPECIFICATION.md', 'OVERALL_SYSTEM_SPECIFICATION_INTEGRATED.md')]
    logs = {}
    for path in destination.glob('*.log'):
        raw = path.read_bytes()
        content = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig', errors='replace').replace('\r\n', '\n')
        logs[path.name] = {'sha256': digest(path), 'bytes': len(raw),
            'last_written_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            'result': re.findall(r'Ran \d+ tests? in [\d.]+s|^OK(?: \([^\n]+\))?$|^FAILED[^\n]*', content, re.M),
            'ewaf_single_line_passes': len(re.findall(r'^test_.*\(ewaf\..*\) \.\.\. ok$', content, re.M)),
            'failures': re.findall(r'^(?:ERROR|FAIL): (.*)$', content, re.M),
            'isolation': [line for line in content.splitlines() if any(term in line.lower() for term in
                         ('server uuid', 'server_uuid', 'datadir', 'private media', 'port=', 'disposable mysql', 'isolated test identity'))]}
        if path.name == 'full-validated-suite.log':
            inventory = json.loads((destination / 'final-suite-inventory.json').read_text(encoding='utf-8'))
            complete = bool(re.search(r'^Ran ' + str(len(inventory['included'])) + r' tests in [\d.]+s\n\nOK$', content, re.M))
            logs[path.name]['complete_success_without_skips'] = complete
            logs[path.name]['selected_tests'] = len(inventory['included'])
            logs[path.name]['selected_ewaf_tests'] = sum(name.startswith('ewaf.') for name in inventory['included'])
            logs[path.name]['historical_migration_tests_not_run'] = len(inventory['not_run_historical_migrations'])
            logs[path.name]['count_note'] = 'Inventory counts include tests whose diagnostic output splits their result across lines; overall OK verifies all selected tests.'
    progress = 'docs/added-targets-phase1-2026-10-23/progress-and-decisions.md'
    original_progress = (ROOT / progress).read_bytes()[-baseline['previous_progress_bytes']:]
    historical_evidence_diff = [name for name in changed if name.startswith('docs/') and name != progress]
    source_diff = [name for name, old in baseline['source_hashes'].items() if digest(ROOT / name) != old]
    result = {'verified_utc': datetime.now(timezone.utc).isoformat(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'protected_count': len(baseline['protected']), 'protected_diff': protected,
        'original_phase1_protected_count': len(original['protected_paths']),
        'original_phase1_protected_diff': original_protected_diff,
        'preexisting_migration_diff': migrations,
        'prior_audit_evidence_diff': historical_evidence_diff,
        'governing_source_diff': source_diff,
        'original_progress_bytes_retained': hashlib.sha256(original_progress).hexdigest() == baseline['files'][progress],
        'section8': {'identical': sections[0] == sections[1], 'bytes': len(sections[0]),
                     'sha256': hashlib.sha256(sections[0]).hexdigest()},
        'changed_preexisting_files': changed, 'logs': logs}
    destination.mkdir(exist_ok=True)
    (destination / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('protected_count', 'protected_diff', 'preexisting_migration_diff', 'section8', 'logs')}, indent=2))
    if protected or original_protected_diff or migrations or historical_evidence_diff or source_diff or not result['original_progress_bytes_retained'] or sections[0] != sections[1]:
        raise SystemExit('Preservation verification failed.')


if __name__ == '__main__':
    main()
