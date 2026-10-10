# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Tipos de aviso que a pessoa pode silenciar no PRÓPRIO chat (/silenciar, /ativar, /silenciados).

O grupo da turma não é afetado. O que está silenciado continua sendo marcado como visto: ao reativar, não chega
uma enxurrada de coisas antigas.
"""

from __future__ import annotations

import unicodedata

from .collect import Notice

# categoria -> (descrição, prefixos de chave dos avisos)
CATEGORIES: dict[str, tuple[str, tuple[str, ...]]] = {
    "confirmacoes": ("confirmações de envio (\"Envio confirmado\")", ()),
    "notificacoes": ("notificações do Moodle (🔔, ✏️, 🆕, 📢 do próprio Moodle)", ("notif",)),
    "atividades": ("atividades novas e alteradas", ("mod", "bulk", "edit", "cfg")),
    "prazos": ("lembretes de prazo e prazo alterado", ("due", "mine", "duechange")),
    "perdidos": ("prazos perdidos", ("late",)),
    "avisos": ("avisos dos professores (fórum de Avisos)", ("post", "postedit")),
    "foruns": ("tópicos e respostas nos fóruns", ("topic", "reply")),
    "notas": ("notas e comentários dos professores", ("grade", "feedback")),
    "mensagens": ("mensagens recebidas", ("msg", "msgbacklog")),
    "eventos": ("eventos e aulas", ("event", "eventday", "eventchange")),
    "resumos": ("resumos diários (pendências, prazos da semana, verificação do dia)", ("mydigest", "digest", "check")),
}
ALIASES = {"confirmacao": "confirmacoes", "notificacao": "notificacoes", "atividade": "atividades",
           "prazo": "prazos", "lembretes": "prazos", "perdido": "perdidos", "aviso": "avisos", "forum": "foruns",
           "nota": "notas", "mensagem": "mensagens", "evento": "eventos", "resumo": "resumos"}


def normalize(word: str) -> str | None:
    """'Notificações' -> 'notificacoes'; palavra desconhecida -> None."""
    w = unicodedata.normalize("NFKD", (word or "").strip().lower())
    w = "".join(ch for ch in w if not unicodedata.combining(ch))
    w = ALIASES.get(w, w)
    return w if w in CATEGORIES else None


def category(n: Notice) -> str | None:
    kind = n.key.split(":", 1)[0]
    if kind == "notif" and n.icon == "✅":
        return "confirmacoes"
    if kind == "cmd":
        return None                                  # respostas aos seus comandos nunca são silenciadas
    for name, (_, prefixes) in CATEGORIES.items():
        if kind in prefixes:
            return name
    return None


def is_muted(n: Notice, muted: list[str]) -> bool:
    return bool(muted) and category(n) in muted


def help_text() -> str:
    lines = ["Você pode silenciar, no SEU chat, estes tipos de aviso (o grupo da turma não muda):"]
    lines += [f"• <b>{name}</b> — {desc}" for name, (desc, _) in CATEGORIES.items()]
    lines += ["", "Exemplos: /silenciar confirmacoes · /ativar confirmacoes · /silenciados"]
    return "\n".join(lines)
