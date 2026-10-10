# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Comandos ao robô (/pendencias, /prazos, /ajuda): só do dono, só no chat privado, resposta só para ele."""

from datetime import timedelta

from nead_avisos.collect import Collector
from nead_avisos.config import Settings
from nead_avisos.state import State
from nead_avisos.telegram import Telegram
from test_avisos_v2 import MyEventsMoodle, ev
from test_collect import NOW

OWNER = 111


def upd(uid, chat, text, kind="private"):
    return {"update_id": uid, "message": {"chat": {"id": chat, "type": kind}, "text": text}}


def test_only_owner_private_commands_are_accepted(monkeypatch):
    updates = [upd(1, 666, "/pendencias"), upd(2, -5, "/prazos@nead_bot", "supergroup"),
               upd(3, OWNER, "/prazos@nead_bot"), upd(4, OWNER, "oi"), upd(5, OWNER, "/PENDENCIAS")]
    monkeypatch.setattr(Telegram, "_api", lambda self, m, p: {"ok": True, "result": updates})
    cmds, nxt = Telegram("t").owner_commands(OWNER, None)
    assert cmds == [(3, "/prazos"), (5, "/pendencias")] and nxt == 6


def test_commands_answer_once_and_only_to_me(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    Collector(Settings(), m, st, NOW).run()
    m.my = [ev(1, NOW + timedelta(days=2), True, "Tarefa A")]
    col = Collector(Settings(), m, st, NOW + timedelta(minutes=15))
    col.commands = [(10, "/pendencias"), (11, "/prazos"), (12, "/ajuda")]
    out = {n.key: n for n in col.run()}
    assert out["cmd:10"].title.startswith("Suas pendências") and "Tarefa A" in out["cmd:10"].body
    assert out["cmd:11"].title.startswith("Prazos da semana")
    assert "/pendencias" in out["cmd:12"].body
    assert all(out[k].audience == "me" for k in ("cmd:10", "cmd:11", "cmd:12"))
    col = Collector(Settings(), m, st, NOW + timedelta(minutes=30))
    col.commands = [(10, "/pendencias")]
    assert not [n for n in col.run() if n.key.startswith("cmd:")]          # mesmo pedido não responde 2 vezes
