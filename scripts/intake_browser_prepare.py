from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.main_testing import command
command(['shell', '-c', 'from program_intake.browser_fixture import prepare_main; prepare_main()'])
