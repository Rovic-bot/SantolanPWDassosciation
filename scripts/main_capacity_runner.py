"""Use the existing isolated harness with packet capacity for full 2,000-row snapshots."""
from pathlib import Path

path = Path(__file__).with_name('g12_test_runner.py')
source = path.read_text(encoding='utf-8')
needle = "character-set-server=utf8mb4\\ncollation-server=utf8mb4_0900_ai_ci\\n"
assert source.count(needle) == 1
source = source.replace(needle, needle + 'max_allowed_packet=512M\\nnet_read_timeout=180\\nnet_write_timeout=180\\n')
exec(compile(source, str(path), 'exec'), {'__file__': str(path), '__name__': '__main__'})
