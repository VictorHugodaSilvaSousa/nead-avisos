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


def plain_text(text: str) -> str:
    """HTML do aviso -> texto simples (reserva quando o Telegram recusa a formatação)."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def render(n: Notice) -> str:
    head = f"{n.icon} <b>{e(n.title)}</b>"
    if n.course:
        head += f"\n📚 {e(n.course)}"
    # body pode trazer <b>/<i> montados por nós; o resto do texto já vem escapado abaixo
    # Corpos montados com formatação já vêm escapados (collect.h); texto puro é escapado aqui.
    body = n.body if re.search(r"</?(b|i|s|a)[ >]", n.body) else e(n.body)
    text = head + (f"\n\n{body}" if body else "")
    if len(text) <= LIMIT:
        return text
    cut = text[:LIMIT - 20].rsplit("\n", 1)[0]          # corta numa quebra de linha
    if cut.count("<") != cut.count(">") or len(re.findall(r"<(b|i|s|a)[ >]", cut)) != \
            len(re.findall(r"</(b|i|s|a)>", cut)):
        cut = e(plain_text(cut))                         # marcação incompleta: vai sem formatação
    return cut + "\n…"


class Telegram:
    def __init__(self, token: str, link_host: str | None = None) -> None:
        self.token = token
        self.link_host = link_host      # botões só levam a este endereço (o Moodle), nunca a links de terceiros
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
        if notice.url and self.safe_link(notice.url):
            payload["reply_markup"] = {"inline_keyboard": [[{"text": button_label(notice), "url": notice.url}]]}
        result = self._api("sendMessage", payload)
        new_id = (result.get("parameters") or {}).get("migrate_to_chat_id")
        if not result.get("ok") and new_id:
            # O Telegram transformou o grupo em supergrupo (novo id): reenvia lá e guarda o id novo.
            self.migrated[chat_id] = new_id
            payload["chat_id"] = new_id
            result = self._api("sendMessage", payload)
        if not result.get("ok") and re.search(r"can't parse entities|message is too long|text is too long",
                                              str(result.get("description")), re.I):
            # Formatação quebrada ou texto longo demais: reenvia como texto simples (nunca trava o aviso).
            payload["text"] = plain_text(render(notice))[:LIMIT]
            payload.pop("parse_mode", None)
            result = self._api("sendMessage", payload)
        ok = bool(result.get("ok"))
        if not ok:
            import sys
            # Nunca o título (pode ter nome de aluno/professor): os registros da nuvem são públicos.
            print(f"Telegram recusou um aviso do tipo '{notice.key.split(':', 1)[0]}': {result.get('description')}",
                  file=sys.stderr)
        time.sleep(1.1)        # grupos aceitam ~20 mensagens/minuto
        return ok

    def safe_link(self, url: str) -> bool:
        """Só https e só o servidor do Moodle: um link estranho numa notificação não vira botão."""
        from urllib.parse import urlparse
        u = urlparse(url)
        return u.scheme == "https" and (self.link_host is None or u.hostname == self.link_host)

    def send_text(self, chat_id: int, text: str, silent: bool = False) -> bool:
        payload = {"chat_id": chat_id, "text": text[:LIMIT], "parse_mode": "HTML", "disable_web_page_preview": True,
                   "disable_notification": silent}
        result = self._api("sendMessage", payload)
        new_id = (result.get("parameters") or {}).get("migrate_to_chat_id")
        if not result.get("ok") and new_id:
            self.migrated[chat_id] = new_id
            payload["chat_id"] = new_id
            result = self._api("sendMessage", payload)
        if not result.get("ok") and re.search(r"can't parse entities|too long", str(result.get("description")), re.I):
            payload["text"] = plain_text(text)[:LIMIT]
            payload.pop("parse_mode", None)
            result = self._api("sendMessage", payload)
        return bool(result.get("ok"))

    def updates(self, offset: int | None = None) -> list[dict]:
        params = {"offset": offset, "timeout": 0} if offset else {}
        return self._api("getUpdates", params).get("result", [])

    def owner_commands(self, owner_chat: int, offset: int | None) -> tuple[list[tuple[int, str]], int | None]:
        """Comandos ('/pendencias', '/prazos', '/ajuda') mandados pelo DONO no chat privado. Mensagens de qualquer
        outra pessoa ou de grupos são ignoradas. Devolve (comandos, próximo offset)."""
        cmds, nxt = [], offset
        for u in self.updates(offset):
            nxt = max(nxt or 0, u["update_id"] + 1)
            msg = u.get("message") or {}
            chat = msg.get("chat") or {}
            text = (msg.get("text") or "").strip().split("@")[0].split(" ")[0].lower()
            if chat.get("type") == "private" and chat.get("id") == owner_chat and text.startswith("/"):
                cmds.append((u["update_id"], text))
        return cmds, nxt

    def pairing_chat(self, code: str, updates: list[dict] | None = None) -> dict | None:
        """Chat privado que enviou '/start <code>' (link de pareamento). Ninguém mais é aceito."""
        for u in updates if updates is not None else self.updates():
            msg = u.get("message") or {}
            chat = msg.get("chat") or {}
            text = (msg.get("text") or "").strip()
            if chat.get("type") == "private" and text in (f"/start {code}", code):
                return chat
        return None

    def pairing_group(self, code: str, updates: list[dict] | None = None) -> dict | None:
        """Grupo em que alguém mandou '/vincular <code>' (o código só aparece na tela do representante)."""
        for u in updates if updates is not None else self.updates():
            msg = u.get("message") or {}
            chat = msg.get("chat") or {}
            words = (msg.get("text") or "").strip().split()
            if (chat.get("type") in ("group", "supergroup") and len(words) == 2
                    and words[0].split("@")[0].lower() == "/vincular" and words[1] == code):
                return chat
        return None

    def me(self) -> dict:
        return self._api("getMe", {}).get("result", {})
