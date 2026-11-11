"""Read-only source inventory and preservation checks for the added-targets audit.

Writes evidence only under docs/added-targets-phase1-2026-10-23. Never imports
Django settings, opens a database, reads .env, or changes a tracked source file.
"""
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/added-targets-phase1-2026-10-23'
BASELINE = OUT / 'baseline.json'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def section_eight():
    raw = (ROOT / 'OVERALL_SYSTEM_SPECIFICATION.md').read_bytes()
    match = re.search(rb'^## 8\. .*?(?=^## 9\. )', raw, re.M | re.S)
    if not match:
        raise RuntimeError('Baseline Section 8 boundaries not found.')
    return match.group()


def source_files():
    return [name for name in git('ls-files', '-z').decode().split('\0') if name]


def capture():
    OUT.mkdir(parents=True, exist_ok=True)
    names = source_files()
    records = []
    for name in names:
        path = ROOT / name
        if not path.is_file():
            raise RuntimeError(f'Tracked source missing: {name}')
        records.append({'path': name, 'sha256': sha(path.read_bytes()),
                        'bytes': path.stat().st_size})
    protected = [item['path'] for item in records if (
        item['path'].startswith(('ewaf/', 'templates/ewaf/')) or
        '/migrations/' in item['path'] or
        item['path'] in {'assistance/services.py', 'announcements/results.py',
            'announcements/public_results.py', 'programs/workflow.py',
            'programs/services.py', 'programs/terms.py',
            'core/management/commands/runlocal.py', 'config/settings.py'})]
    external = ['CURRENT_SYSTEM_SPECIFICATION.md', 'Guide for Development.md',
        '00 - Project Overview/System Master Specification.md',
        '00 - Project Overview/Decisions.md', '00 - Project Overview/Open Decisions.md',
        '00 - Project Overview/Workflow References/2026-10-10/Confirmed_Membership_and_PDAO_Requirements_2026-10-10.md',
        '00 - Project Overview/Workflow References/2026-10-10/Workflow Source Register.md',
        '00 - Project Overview/Workflow References/2026-10-10/Workbook Formula and Cache Evidence.md',
        '00 - Project Overview/Computation - final.xlsx',
        '05 - Development/October 10 Implementation Impact.md']
    doc_hashes = {'../' + name: sha((ROOT.parent / name).read_bytes()) for name in external}
    doc_hashes['OVERALL_SYSTEM_SPECIFICATION.md'] = sha((ROOT / 'OVERALL_SYSTEM_SPECIFICATION.md').read_bytes())
    data = {'captured_utc': datetime.now(timezone.utc).isoformat(),
        'branch': git('branch', '--show-current').decode().strip(),
        'head': git('rev-parse', 'HEAD').decode().strip(),
        'status': git('status', '--porcelain=v1').decode(),
        'worktrees': git('worktree', 'list').decode(),
        'index_diff_sha256': sha(git('diff', '--cached', '--binary')),
        'worktree_diff_sha256': sha(git('diff', '--binary')),
        'files': records, 'protected_paths': protected, 'source_documents': doc_hashes,
        'section8_raw_sha256': sha(section_eight()),
        'section8_lf_sha256': sha(section_eight().replace(b'\r\n', b'\n')),
        'integrated_section8_comparison': 'BLOCKED: required integrated source unavailable'}
    with BASELINE.open('x', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2)
        handle.write('\n')
    tests = []
    for name in names:
        path = ROOT / name
        if path.suffix != '.py' or not (path.name.startswith('test') or '/tests/' in name):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name.startswith('test_'):
                        tests.append({'path': name, 'class': node.name, 'test': method.name,
                                      'line': method.lineno})
    (OUT / 'test-inventory.json').write_text(json.dumps(tests, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'tracked_files': len(records), 'protected_files': len(protected),
                      'test_methods': len(tests), 'section8_raw_sha256': data['section8_raw_sha256']}))


def verify():
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    changed = [item['path'] for item in baseline['files'] if
               not (ROOT / item['path']).is_file() or
               sha((ROOT / item['path']).read_bytes()) != item['sha256']]
    changed_docs = [name for name, digest in baseline['source_documents'].items()
                    if not (ROOT / name).is_file() or sha((ROOT / name).read_bytes()) != digest]
    result = {'verified_utc': datetime.now(timezone.utc).isoformat(),
        'head_unchanged': git('rev-parse', 'HEAD').decode().strip() == baseline['head'],
        'branch_unchanged': git('branch', '--show-current').decode().strip() == baseline['branch'],
        'index_diff_unchanged': sha(git('diff', '--cached', '--binary')) == baseline['index_diff_sha256'],
        'changed_tracked_files': changed, 'changed_source_documents': changed_docs,
        'changed_protected_files': sorted(set(changed) & set(baseline['protected_paths'])),
        'section8_unchanged': sha(section_eight()) == baseline['section8_raw_sha256'],
        'status': git('status', '--porcelain=v1').decode()}
    supplement = OUT / 'source-supplement.json'
    if supplement.is_file():
        source = json.loads(supplement.read_text(encoding='utf-8'))
        result['supplied_pdf_unchanged'] = sha((ROOT / source['path']).read_bytes()) == source['sha256']
    result['pass'] = (not changed and not changed_docs and all(result[key] for key in (
        'head_unchanged', 'branch_unchanged', 'index_diff_unchanged', 'section8_unchanged'))
        and result.get('supplied_pdf_unchanged', True))
    (OUT / 'preservation-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['capture']:
        capture()
    elif sys.argv[1:] == ['verify']:
        sys.exit(verify())
    else:
        raise SystemExit('Use capture (once) or verify.')
