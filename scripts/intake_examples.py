from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.main_testing import command

command(['shell', '-c', 'from program_intake.demo import add_examples; add_examples()'])
