# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Estado (o que já foi avisado), CRIPTOGRAFADO em disco.

O estado guarda o mínimo para não repetir avisos: identificadores, datas e "impressões digitais" (hashes) do
que mudou. Mesmo assim ele fica cifrado (Fernet: AES-128 + HMAC-SHA256), porque na nuvem ele vive no cache do
GitHub Actions de um repositório público. A chave:
  - no PC: Gerenciador de Credenciais do Windows (criada automaticamente na 1ª execução);
  - na nuvem: o Secret NEAD_AVISOS_CHAVE_ESTADO (nunca vai para o repositório nem para os registros).
Sem a chave, o arquivo é ilegível. Arquivo antigo (sem criptografia) é lido uma vez e regravado cifrado.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

KEEP_DAYS = 120
MAGIC = b"NEADAVISOS-ENC-1\n"


class StateKeyError(Exception):
    """Estado cifrado, mas a chave não foi informada."""


def state_key(create: bool = True) -> bytes | None:
    """Chave do estado: Secret da nuvem ou Gerenciador de Credenciais (gera uma no PC, se não houver)."""
    from .config import get_secret, set_secret
    key = get_secret("chave_estado")
    if not key and create and not os.environ.get("GITHUB_ACTIONS"):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        set_secret("chave_estado", key)
    return key.encode() if key else None


class State:
    def __init__(self, path: Path, key: bytes | None = None) -> None:
        self.path = path
        self.key = key
        self.was_plain = False          # arquivo antigo sem criptografia (será regravado cifrado)
        self.reset_reason: str | None = None
        self.data: dict = {}
        try:
            raw = path.read_bytes()
        except OSError:
            return
        if raw.startswith(MAGIC):
            if not key:
                raise StateKeyError("o estado está criptografado, mas a chave (NEAD_AVISOS_CHAVE_ESTADO) não foi "
                                    "encontrada")
            from cryptography.fernet import Fernet, InvalidToken
            try:
                self.data = json.loads(Fernet(key).decrypt(raw[len(MAGIC):]))
            except (InvalidToken, ValueError):
                # Chave trocada ou arquivo corrompido: recomeça do zero (a 1ª execução é silenciosa).
                self.reset_reason = "chave diferente ou arquivo corrompido"
            return
        try:
            self.data = json.loads(raw.decode("utf-8"))
            self.was_plain = True
        except (UnicodeDecodeError, ValueError):
            self.reset_reason = "arquivo ilegível"

    @property
    def encrypted(self) -> bool:
        return self.key is not None

    def prune(self, now: datetime) -> None:
        """Esquece avisos antigos (o arquivo não cresce para sempre). Atividades ('mod:') ficam sempre."""
        limit = (now - timedelta(days=KEEP_DAYS)).isoformat()
        seen = self.data.get("seen", {})
        self.data["seen"] = {k: v for k, v in seen.items() if k.startswith("mod:") or v >= limit}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(self.data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if self.key:
            from cryptography.fernet import Fernet
            body = MAGIC + Fernet(self.key).encrypt(body)
        elif os.environ.get("GITHUB_ACTIONS"):
            print("AVISO: estado salvo SEM criptografia (falta o Secret NEAD_AVISOS_CHAVE_ESTADO).", file=sys.stderr)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, self.path)
