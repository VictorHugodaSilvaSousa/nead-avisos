# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Bugs corrigidos em 09/10/2026."""

from datetime import datetime, timedelta, timezone

from nead_avisos import cli
from nead_avisos.collect import Notice
from nead_avisos.state import State
from nead_avisos.telegram import LIMIT, Telegram, render
from test_avisos_v3 import TEACHER, disc, run, started
from test_collect import NOW

ME = 7


def test_my_own_forum_posts_are_not_notified(tmp_path):
    m, st = started(tmp_path)
    m.discussions[51] = [disc(80, ME, name="Minha dúvida"), disc(81, TEACHER, name="Plantão")]
    keys = [n.key for n in run(m, st, NOW + timedelta(minutes=15))]
    assert "topic:81" in keys and "topic:80" not in keys
    later = NOW + timedelta(minutes=20)
    m.discussions[51][1] = dict(disc(81, TEACHER, n=1, tm=later, name="Plantão"), created=NOW.timestamp())
    m.replies[81] = [{"id": 900, "parentid": 1, "timecreated": later.timestamp(), "message": "eu respondi",
                      "author": {"id": ME, "fullname": "Eu"}}]
    assert not [n for n in run(m, st, NOW + timedelta(minutes=30)) if n.key.startswith("reply:")]


def test_long_message_is_cut_safely():
    body = "\n".join(f"• <b>Aluno {i}</b> — <i>texto {'x' * 80}</i>" for i in range(80))
    text = render(Notice("bulk:1", "me", "📝", "Muitos itens", body=body))
    assert len(text) <= LIMIT and text.count("<b>") == text.count("</b>") and text.count("<i>") == text.count("</i>")


def test_rejected_formatting_is_resent_as_plain_text(monkeypatch):
    calls = []

    def api(self, method, payload):
        calls.append(dict(payload))
        if payload.get("parse_mode"):
            return {"ok": False, "description": "Bad Request: can't parse entities: unsupported start tag"}
        return {"ok": True}
    monkeypatch.setattr(Telegram, "_api", api)
    monkeypatch.setattr("time.sleep", lambda x: None)
    assert Telegram("t").send(1, Notice("x:1", "me", "📝", "Título", body="<b>quebrado"))
    assert "parse_mode" not in calls[-1] and "<b>" not in calls[-1]["text"]


def test_error_alerts_at_most_every_6_hours(tmp_path):
    st = State(tmp_path / "s.json")
    assert cli._alert_due(st, "auth", hours=6) is True
    assert cli._alert_due(st, "auth", hours=6) is False
    st.data["alerted"]["auth"] = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    assert cli._alert_due(st, "auth", hours=6) is True
