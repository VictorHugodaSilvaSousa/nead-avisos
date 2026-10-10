# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Empacota o plugin do Moodle num .zip instalável (pasta 'neadavisos/' na raiz, barras normais) + .sha256.

Uso: python packaging/plugin_zip.py moodle-plugin/neadavisos dist/message_neadavisos.zip
"""

import hashlib
import sys
import zipfile
from pathlib import Path


def main(src: str, dest: str) -> None:
    root = Path(src)
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, (Path(root.name) / f.relative_to(root)).as_posix())
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    Path(f"{out}.sha256").write_text(f"{digest}  {out.name}\n", encoding="ascii")
    print(f"{out} ({out.stat().st_size} bytes) SHA-256 {digest}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
