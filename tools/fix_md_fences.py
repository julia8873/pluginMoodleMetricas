import io
from pathlib import Path

root = Path(__file__).parents[1]
files = list(root.glob('docs/**/*.md'))

for p in files:
    text = p.read_text(encoding='utf-8')
    orig = text
    # Normalize CRLF
    text = text.replace('\r\n', '\n')
    # Fix double open fences
    text = text.replace('```python\n```python', '```python')
    text = text.replace('```python ```python', '```python')
    # Fix cases where an extra close/open pair exists
    text = text.replace('\n# \n```\n```', '\n```\n')
    text = text.replace('\n# \n```\r\n```', '\n```\n')
    # Remove stray lone closing fence followed by opening fence
    text = text.replace('```\n```', '```\n')
    
    if text != orig:
        backup = p.with_suffix(p.suffix + '.bak')
        backup.write_text(orig, encoding='utf-8')
        p.write_text(text, encoding='utf-8')
        print(f'Fixed: {p}')
    else:
        print(f'No changes: {p}')
