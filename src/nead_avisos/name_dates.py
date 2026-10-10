# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Prazo escrito no NOME da atividade, quando o professor não cadastra a data no Moodle.

Exemplos reais do NEAD: "Atividade Alinhamento (31/07/2026)", "ENTREGA: Identificação de ideias (NOVO PRAZO: ATÉ
25 DE SETEMBRO - SEXTA-FEIRA)", "Atividade: Conceito Empreendedorismo (Até 07 de AGOSTO)".
O horário não vem no nome: o aviso diz "até o fim do dia" em vez de inventar uma hora.
"""

from __future__ import annotations

import re
from datetime import date, datetime

MONTHS = {m: i for i, m in enumerate(["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                                      "setembro", "outubro", "novembro", "dezembro"], 1)}
MONTHS["marco"] = 3
_NUMERIC = re.compile(r"(?<![\d/.])(\d{1,2})/(\d{1,2})(?:/(\d{4}|\d{2}))?(?![\d/])")
_WRITTEN = re.compile(r"(?<!\d)(\d{1,2})\s*(?:º\s*)?de\s+(" + "|".join(MONTHS) + r")(?:\s+de\s+(\d{4}))?",
                      re.IGNORECASE)


def term_start(term: str | None) -> date | None:
    """'2026/2' -> 01/07/2026; '2026/1' -> 01/01/2026."""
    m = re.fullmatch(r"(20\d{2})/([12])", term or "")
    return date(int(m.group(1)), 1 if m.group(2) == "1" else 7, 1) if m else None


def deadline_from_name(name: str, term: str | None, tz) -> datetime | None:
    """Último prazo escrito no nome (23:59 daquele dia), só se cair dentro do semestre da sala."""
    start = term_start(term)
    if start is None:
        return None
    found: list[date] = []
    for d, mth, y in _NUMERIC.findall(name or ""):
        year = (int(y) + (2000 if len(y) == 2 else 0)) if y else start.year
        try:
            found.append(date(year, int(mth), int(d)))
        except ValueError:
            pass
    for d, mth, y in _WRITTEN.findall(name or ""):
        try:
            found.append(date(int(y) if y else start.year, MONTHS[mth.lower()], int(d)))
        except ValueError:
            pass
    end = date(start.year + (1 if start.month == 7 else 0), 1 if start.month == 7 else 7, 31)
    valid = [d for d in found if start <= d <= end]
    if not valid:
        return None
    last = valid[-1]
    return datetime(last.year, last.month, last.day, 23, 59, tzinfo=tz)
