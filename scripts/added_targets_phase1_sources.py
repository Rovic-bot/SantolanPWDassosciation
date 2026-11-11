"""Read-only document comparison using the bundled artifact Python runtime.

Dependencies are supplied by that runtime, not added to application requirements.
PDF extraction is a text comparison, never proof of Markdown byte identity.
"""
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/added-targets-phase1-2026-10-23'


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def compact(text):
    return re.sub(r'\s+', '', text)


def main():
    pdf_path = ROOT / 'Santolan_Overall_Specification_Integrated.pdf'
    pages = [page.extract_text() or '' for page in PdfReader(pdf_path).pages]
    pdf_text = '\n'.join(pages[22:25])
    pdf_text = re.sub(r'^SANTOLAN PWD.*$', '', pdf_text, flags=re.M)
    pdf_text = re.sub(r'^ADDITIVE INTEGRATION.*$', '', pdf_text, flags=re.M)
    pdf_text = pdf_text.replace('•', '')
    md = (ROOT / 'OVERALL_SYSTEM_SPECIFICATION.md').read_text(encoding='utf-8')
    section = re.search(r'^## 8\. .*?(?=^## 9\. )', md, re.M | re.S).group()
    plain = re.sub(r'^\|[ |:\-]+\|\s*$', '', section, flags=re.M)
    plain = re.sub(r'^#+ ', '', plain, flags=re.M)
    plain = re.sub(r'^```.*$', '', plain, flags=re.M)
    plain = re.sub(r'^- ', '', plain, flags=re.M)
    plain = plain.replace('**', '').replace('`', '').replace('|', ' ')
    a, b = compact(plain), compact(pdf_text)
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(),
        'pdf_sha256': hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        'pages': [23, 24, 25], 'method': 'Remove PDF running headers/footer, Markdown heading/table/fence/emphasis/list syntax and whitespace; preserve wording, numbers, and operators.',
        'baseline_normalized_sha256': sha(a), 'integrated_pdf_normalized_sha256': sha(b),
        'normalized_equal': a == b,
        'integrated_markdown_byte_identity': 'NOT VERIFIED: integrated Markdown unavailable',
        'differences': [{'operation': op, 'baseline': a[i:j], 'pdf': b[k:l]}
            for op, i, j, k, l in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op != 'equal']}
    (OUT / 'section8-comparison.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    workbook = ROOT.parent / '00 - Project Overview/Computation - final.xlsx'
    formulas = load_workbook(workbook, data_only=False, read_only=True)
    caches = load_workbook(workbook, data_only=True, read_only=True)
    sheet, cache = formulas['Sheet1'], caches['Sheet1']
    rows = [{'cell': cell.coordinate, 'formula_or_literal': cell.value,
             'stored_value': cache[cell.coordinate].value, 'is_formula': cell.data_type == 'f'}
            for row in sheet for cell in row if cell.value is not None]
    formulas.close()
    caches.close()
    ledger = {'path': '../00 - Project Overview/Computation - final.xlsx',
        'sha256': hashlib.sha256(workbook.read_bytes()).hexdigest(),
        'recalculated': False, 'populated_cells': len(rows),
        'formula_cells': sum(row['is_formula'] for row in rows), 'cells': rows}
    (OUT / 'workbook-read-evidence.json').write_text(json.dumps(ledger, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    print(json.dumps({key: ledger[key] for key in ('recalculated', 'populated_cells', 'formula_cells')}))


if __name__ == '__main__':
    main()
