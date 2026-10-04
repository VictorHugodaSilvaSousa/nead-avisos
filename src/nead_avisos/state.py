"""Estado local (o que já foi avisado), em JSON. Guarda só identificadores e datas, nenhum conteúdo."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

KEEP_DAYS = 120


class State:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.data: dict = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def prune(self, now: datetime) -> None:
        """Esquece avisos antigos (o arquivo não cresce para sempre). Atividades ('mod:') ficam sempre."""
        limit = (now - timedelta(days=KEEP_DAYS)).isoformat()
        seen = self.data.get("seen", {})
        self.data["seen"] = {k: v for k, v in seen.items() if k.startswith("mod:") or v >= limit}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=0), encoding="utf-8")
        os.replace(tmp, self.path)
