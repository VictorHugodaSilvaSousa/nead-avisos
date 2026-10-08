"""Envio pelo Telegram (chega no celular e no PC ao mesmo tempo). HTML com escape; nunca registra o token."""

from __future__ import annotations

import html
import json
import re
import ssl
import time
import urllib.error
import urllib.request

from .collect import Notice

LIMIT = 4000


def _ssl():
    import truststore
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def e(text) -> str:
    return html.escape("" if text is None else str(text), quote=False)


BUTTONS = [("msg", "💬 Responder no Moodle"), ("mine", "📝 Abrir e entregar"), ("late", "📝 Abrir a tarefa"),
           ("due", "📝 Abrir a tarefa"), ("grade", "📊 Ver nota"), ("feedback", "📝 Ver comentário"),
           ("post", "📢 Abrir aviso"), ("postedit", "📢 Abrir aviso"), ("reply", "💬 Abrir discussão"),
           ("topic", "💬 Abrir discussão"), ("event", "📆 Ver no calendário"), ("eventday", "📆 Ver no calendário"),
           ("eventchange", "📆 Ver no calendário"), ("edit", "✏️ Ver o que mudou"), ("duechange", "📅 Abrir a tarefa"),
           ("cfg", "⚙️ Abrir a atividade"), ("mod", "📖 Abrir no Moodle"), ("msgbacklog", "💬 Abrir mensagens")]


NOTIF_BUTTONS = {"📢": "📢 Abrir aviso", "📝": "📝 Ver comentário", "✏️": "✏️ Ver o que mudou", "🆕": "📖 Abrir",
                 "✅": "✅ Ver envio"}


def button_label(n: Notice) -> str:
    prefix = n.key.split(":", 1)[0]
    if prefix == "notif":
        return NOTIF_BUTTONS.get(n.icon, "Abrir no Moodle")
    return next((label for p, label in BUTTONS if p == prefix), "Abrir no Moodle")


def render(n: Notice) -> str:
    head = f"{n.icon} <b>{e(n.title)}</b>"
    if n.course:
        head += f"\n📚 {e(n.course)}"
    # body pode trazer <b>/<i> montados por nós; o resto do texto já vem escapado abaixo
    # Corpos montados com formatação já vêm escapados (collect.h); texto puro é escapado aqui.
    body = n.body if re.search(r"</?(b|i|s|a)[ >]", n.body) else e(n.body)
    return (head + (f"\n\n{body}" if body else ""))[:LIMIT]


class Telegram:
    def __init__(self, token: str) -> None:
        self.token = token
        self.migrated: dict[int, int] = {}     # grupo que virou supergrupo: id antigo -> id novo

    def _api(self, method: str, payload: dict) -> dict:
        req = urllib.request.Request(f"https://api.telegram.org/bot{self.token}/{method}",
                                     data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30, context=_ssl()) as r:
                    return json.load(r)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:                       # limite do Telegram: espera e tenta de novo
                    time.sleep(int(exc.headers.get("Retry-After", "3")) + 1)
                    continue
                try:
                    return json.load(exc)
                except ValueError:
                    return {"ok": False, "description": f"HTTP {exc.code}"}
            except (urllib.error.URLError, OSError) as exc:
                if attempt == 2:
                    return {"ok": False, "description": f"{type(exc).__name__}: {exc}"}
                time.sleep(2)
        return {"ok": False, "description": "limite de tentativas"}

    def send(self, chat_id: int, notice: Notice, silent: bool = False) -> bool:
        payload = {"chat_id": chat_id, "text": render(notice), "parse_mode": "HTML",
                   "disable_web_page_preview": True, "disable_notification": silent}
        if notice.url:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": button_label(notice), "url": notice.url}]]}
        result = self._api("sendMessage", payload)
        new_id = (result.get("parameters") or {}).get("migrate_to_chat_id")
        if not result.get("ok") and new_id:
            # O Telegram transformou o grupo em supergrupo (novo id): reenvia lá e guarda o id novo.
            self.migrated[chat_id] = new_id
            payload["chat_id"] = new_id
            result = self._api("sendMessage", payload)
        ok = bool(result.get("ok"))
        if not ok:
            import sys
            print(f"Telegram recusou '{notice.title[:40]}' para {chat_id}: {result.get('description')}", file=sys.stderr)
        time.sleep(1.1)        # grupos aceitam ~20 mensagens/minuto
        return ok

    def send_text(self, chat_id: int, text: str) -> bool:
        return bool(self._api("sendMessage", {"chat_id": chat_id, "text": text[:LIMIT], "parse_mode": "HTML",
                                              "disable_web_page_preview": True}).get("ok"))

    def updates(self) -> list[dict]:
        return self._api("getUpdates", {}).get("result", [])

    def me(self) -> dict:
        return self._api("getMe", {}).get("result", {})
