#!/usr/bin/env python3
"""Pre-build script: expande inclusiones custom `--8<-- "path:label"`.

Busca en los archivos under `docs/` las líneas con el patrón
--8<-- "relative/path:file_label" y sustituye cada bloque por un
bloque de código con el contenido entre los marcadores
`--8<-- [start:label]` / `--8<-- [end:label]` en el fichero fuente.

Usar antes de `mkdocs build` para garantizar que los snippets se
embarcan correctamente sin necesidad de plugins extras.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"

INCLUDE_PATTERN = re.compile(r'--8<--\s*"(?P<path>[^:]+):(?P<label>[^"]+)"')
START_PATTERN = lambda lbl: re.compile(r'--8<--\s*\[start:%s\]' % re.escape(lbl))
END_PATTERN = lambda lbl: re.compile(r'--8<--\s*\[end:%s\]' % re.escape(lbl))


def extract_fragment(src_path: Path, label: str) -> str | None:
    if not src_path.exists():
        return None
    text = src_path.read_text(encoding="utf-8")
    m1 = START_PATTERN(label).search(text)
    m2 = END_PATTERN(label).search(text)
    if not m1 or not m2:
        return None
    frag = text[m1.end(): m2.start()].strip("\n")
    return frag


def process_file(md_path: Path) -> bool:
    changed = False
    text = md_path.read_text(encoding="utf-8")
    def repl(m: re.Match) -> str:
        rel = m.group("path")
        label = m.group("label")
        src = ROOT / rel
        frag = extract_fragment(src, label)
        if frag is None:
            print(f"[WARN] No fragment {label} in {rel}", file=sys.stderr)
            return m.group(0)
        # normalize indentation
        lines = frag.splitlines()
        # Determine minimal indent (skip empty)
        indents = [len(re.match(r"^\s*", ln).group(0)) for ln in lines if ln.strip()]
        min_indent = min(indents) if indents else 0
        norm = "\n".join([ln[min_indent:] for ln in lines])
        return "```python\n" + norm + "\n```"

    new_text = INCLUDE_PATTERN.sub(repl, text)
    if new_text != text:
        backup = md_path.with_suffix(md_path.suffix + ".bak")
        if not backup.exists():
            md_path.rename(backup)
            backup.write_text(text, encoding="utf-8")
        md_path.write_text(new_text, encoding="utf-8")
        changed = True
    return changed


def main():
    md_files = list(DOCS_DIR.rglob("*.md"))
    any_changed = False
    for md in md_files:
        if process_file(md):
            print(f"Expanded includes in {md}")
            any_changed = True
    if not any_changed:
        print("No includes expanded.")


if __name__ == '__main__':
    main()
