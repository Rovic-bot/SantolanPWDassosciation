"""Profile the existing verified 100-applicant regression without changing its rules."""
import cProfile
import json
import os
from pathlib import Path
import pstats
from ewaf.test_operational_volume import OperationalVolumeTests as _Volume


class OperationalProfile(_Volume):
    def calculate(self, *args, **kwargs):
        profile = cProfile.Profile()
        try:
            return profile.runcall(super().calculate, *args, **kwargs)
        finally:
            stats = pstats.Stats(profile)
            root = Path.cwd()
            rows = []
            for (file, line, name), (primitive, total, internal, cumulative, callers) in stats.stats.items():
                try: file = str(Path(file).relative_to(root))
                except ValueError: file = Path(file).name
                rows.append({'file':file,'line':line,'function':name,'calls':total,
                    'internal_seconds':internal,'cumulative_seconds':cumulative})
            rows.sort(key=lambda x:x['cumulative_seconds'],reverse=True)
            Path(os.environ['G12_ARTIFACT_DIR'],'operational-profile.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
