"""Configuração do NEAD Avisos.

Valores comuns: arquivo .env da pasta do projeto (ou variáveis de ambiente — é assim na nuvem).
Segredos (chave do Moodle, token do bot): Gerenciador de Credenciais do Windows no PC, ou variáveis de
ambiente NEAD_AVISOS_MOODLE_TOKEN / NEAD_AVISOS_TELEGRAM_TOKEN na nuvem. Nunca no .env nem no código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import sys as _sys

# Como .exe (PyInstaller), configuração e estado ficam em %LOCALAPPDATA%/NEAD-Avisos (pasta do usuário);
# rodando do código-fonte, na pasta do projeto.
if getattr(_sys, "frozen", False):
    PROJECT_ROOT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "NEAD-Avisos"
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
SERVICE = "nead-avisos"


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def _ints(text: str) -> list[int]:
    return [int(x) for x in text.replace(";", ",").split(",") if x.strip().lstrip("-").isdigit()]


@dataclass
class Settings:
    base_url: str = "https://nead.ifb.edu.br"
    username: str = ""
    timezone: str = "America/Sao_Paulo"
    telegram_chat_id: int | None = None          # seu chat privado: recebe TUDO
    telegram_group_id: int | None = None         # grupo da turma: só avisos gerais (sem dado pessoal)
    reminder_days: list[int] = field(default_factory=lambda: [3, 1, 0])
    digest_hour: int = 7                         # resumo diário de prazos a partir desta hora
    include_courses: list[int] = field(default_factory=list)   # força incluir (ids)
    exclude_courses: list[int] = field(default_factory=list)
    group_courses: list[int] = field(default_factory=list)     # vazio = mesmas salas acompanhadas
    data_dir: Path = PROJECT_ROOT / "data"
    silent_first_run: bool = False             # 1ª execução sem nenhum envio (ex.: ao migrar para a nuvem)
    quiet_hours: tuple[int, int] | None = (22, 7)  # avisos chegam SEM som nesse horário (urgentes tocam)
    group_slots: list[int] | None = field(default_factory=lambda: [8, 13, 19])  # resumo do grupo; None = na hora

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @classmethod
    def load(cls) -> "Settings":
        env = {**_load_env_file(PROJECT_ROOT / ".env"), **{k: v for k, v in os.environ.items()
                                                            if k.startswith("NEAD_AVISOS_")}}
        g = lambda k, d="": env.get(f"NEAD_AVISOS_{k}", d)  # noqa: E731
        s = cls()
        s.base_url = g("BASE_URL", s.base_url).rstrip("/")
        s.username = g("USERNAME")
        s.timezone = g("TIMEZONE", s.timezone)
        s.telegram_chat_id = int(g("TELEGRAM_CHAT_ID")) if g("TELEGRAM_CHAT_ID").lstrip("-").isdigit() else None
        s.telegram_group_id = int(g("TELEGRAM_GROUP_ID")) if g("TELEGRAM_GROUP_ID").lstrip("-").isdigit() else None
        if g("LEMBRETES_DIAS"):
            s.reminder_days = sorted(set(_ints(g("LEMBRETES_DIAS"))), reverse=True)
        if g("RESUMO_HORA").isdigit():
            s.digest_hour = int(g("RESUMO_HORA"))
        s.include_courses = _ints(g("INCLUIR_SALAS"))
        s.exclude_courses = _ints(g("EXCLUIR_SALAS"))
        s.group_courses = _ints(g("SALAS_DO_GRUPO"))
        s.silent_first_run = g("PRIMEIRA_EXECUCAO_SILENCIOSA", "").lower() in ("1", "true", "sim")
        quiet = g("SILENCIO", "22-7").replace(" ", "")
        if quiet in ("", "0", "nao", "não", "off"):
            s.quiet_hours = None
        elif "-" in quiet and all(x.isdigit() for x in quiet.split("-", 1)):
            a, b = (int(x) for x in quiet.split("-", 1))
            s.quiet_hours = (a % 24, b % 24)
        slots = g("GRUPO_HORARIOS", "8,13,19").replace(" ", "").lower()
        if slots in ("0", "imediato", "na-hora", "nahora"):
            s.group_slots = None
        elif slots:
            s.group_slots = sorted({int(x) % 24 for x in slots.split(",") if x.isdigit()}) or [8, 13, 19]
        if g("DATA_DIR"):
            s.data_dir = Path(g("DATA_DIR"))
        return s


def get_secret(name: str) -> str | None:
    """Ambiente (nuvem) tem precedência; depois, Gerenciador de Credenciais do Windows."""
    env = os.environ.get(f"NEAD_AVISOS_{name.upper()}")
    if env:
        return env
    try:
        import keyring
        return keyring.get_password(SERVICE, name) or None
    except Exception:  # noqa: BLE001 — sem keyring (ex.: Linux na nuvem)
        return None


def set_secret(name: str, value: str) -> None:
    import keyring
    keyring.set_password(SERVICE, name, value)
