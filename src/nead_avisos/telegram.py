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

    def send(self, chat_id: int, notice: Notice) -> bool:
        payload = {"chat_id": chat_id, "text": render(notice), "parse_mode": "HTML",
                   "disable_web_page_preview": True}
        if notice.url:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": "Abrir no Moodle", "url": notice.url}]]}
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
