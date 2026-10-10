"""Grupo da turma em ritmo de resumo: em vez de uma mensagem por novidade, o grupo recebe um resumo organizado
por disciplina em horários fixos (padrão 8h, 13h e 19h). Só o urgente chega na hora no grupo:
prazo que vence HOJE, prazo alterado pelo professor e evento de hoje.

O seu chat pessoal continua recebendo tudo na hora (este módulo só trata o que vai para o GRUPO).
"""

from __future__ import annotations

import html
from datetime import datetime

from .collect import Notice, fmt

LIMIT = 3800                                   # folga sob o limite de 4.000 caracteres do Telegram
URGENT_KINDS = {"duechange", "eventday", "eventchange"}
HEAD = "📬 <b>Novidades da turma</b>"


def h(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def is_urgent_for_group(n: Notice) -> bool:
    """O que não pode esperar o próximo resumo."""
    kind = n.key.split(":", 1)[0]
    return kind in URGENT_KINDS or (kind == "due" and bool(n.extra.get("urgent")))      # prazo vence HOJE


def entry(n: Notice, safe_link) -> dict:
    """Item da fila do resumo (só o necessário para montar a mensagem)."""
    kind = n.key.split(":", 1)[0]
    return {"key": n.key, "kind": kind, "icon": n.icon, "title": n.title, "course": n.course,
            "url": n.url if n.url and safe_link(n.url) else None,
            # Resumos que já vêm prontos (prazos da semana, vários itens de uma vez) levam o texto junto.
            "body": n.body if kind in ("digest", "bulk") else ""}


def current_slot(now: datetime, slots: list[int]) -> str | None:
    """Horário de resumo em vigor agora (ex.: '2026-10-10 13'), ou None antes do primeiro horário do dia."""
    past = [s for s in sorted(slots) if s <= now.hour]
    return f"{now:%Y-%m-%d} {past[-1]:02d}" if past else None


def render(entries: list[dict], now: datetime) -> list[str]:
    """Mensagens do resumo, divididas LINHA a LINHA se passarem do limite do Telegram (o nome da disciplina
    se repete na continuação, para cada mensagem fazer sentido sozinha)."""
    news = [e for e in entries if e["kind"] != "digest"]
    digests = [e for e in entries if e["kind"] == "digest"]
    sections: list[tuple[str, list[str]]] = []
    by_course: dict[str, list[dict]] = {}
    for e in news:
        by_course.setdefault(e["course"] or "Geral", []).append(e)
    for course, items in by_course.items():
        lines = []
        for e in items:
            title = f'<a href="{h(e["url"])}">{h(e["title"])}</a>' if e["url"] else h(e["title"])
            lines.append(f"• {e['icon']} {title}")
            lines += [f"   {line}" for line in e["body"].splitlines() if line.strip()]
        sections.append((f"📚 <b>{h(course)}</b>", lines))
    for d in digests[-1:]:                       # só o resumo de prazos mais recente
        sections.append((f"🗓 <b>{h(d['title'])}</b>", [ln for ln in d["body"].splitlines() if ln.strip()]))

    out: list[str] = []
    current = f"{HEAD} — {h(fmt(now))}"
    for header, lines in sections:
        current += "\n\n" + header
        for line in lines:
            if len(line) > LIMIT // 2:           # linha gigante (texto colado): corta, sem quebrar a mensagem
                line = h(line[:LIMIT // 2]) + "…" if "<" not in line else line[:LIMIT // 2].rsplit("<", 1)[0] + "…"
            if len(current) + len(line) + 1 > LIMIT:
                out.append(current)
                current = f"{HEAD} (continuação)\n\n{header} (cont.)"
            current += "\n" + line
    out.append(current)
    return out
