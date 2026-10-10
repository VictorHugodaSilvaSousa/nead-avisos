# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Caixa de entrada: toda mensagem recebida, notificações sem repetir assunto e verificação diária."""

from datetime import timedelta

from nead_avisos.collect import Collector
from nead_avisos.config import Settings
from nead_avisos.state import State
from test_collect import NOW, FakeMoodle

ME = 7


def run(m, st, now):
    return Collector(Settings(), m, st, now).run()


def conv(cid, msgs, ctype=1, name=None, members=((9, "Andreza"),)):
    return {"id": cid, "type": ctype, "name": name, "members": [{"id": i, "fullname": n} for i, n in members],
            "messages": sorted(msgs, key=lambda x: -x["timecreated"])}


def msg(mid, who, when, text="Oi"):
    return {"id": mid, "useridfrom": who, "timecreated": when.timestamp(), "text": f"<p>{text}</p>"}


def test_every_received_message_is_sent_one_by_one(tmp_path):
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    t1, t2 = NOW + timedelta(minutes=3), NOW + timedelta(minutes=8)
    m.convs = [conv(40, [msg(1, 9, t1, "Já entreguei"), msg(2, 9, t2, "Obrigada!"), msg(3, ME, t2, "De nada")]),
               conv(41, [msg(4, 12, t1, "Reunião às 19h")], ctype=2, name="Equipe 3", members=((12, "Prof. Ana"),))]
    out = [n for n in run(m, st, NOW + timedelta(minutes=15)) if n.key.startswith("msg:")]
    assert [(n.key, n.title) for n in out] == [("msg:1", "Mensagem de Andreza"), ("msg:2", "Mensagem de Andreza"),
                                              ("msg:4", "Mensagem de Prof. Ana em Equipe 3")]
    assert all(n.audience == "me" for n in out) and "Já entreguei" in out[0].body
    assert not [n for n in run(m, st, NOW + timedelta(minutes=30)) if n.key.startswith("msg:")]   # sem repetir
    m.convs[0]["messages"].insert(0, msg(5, 9, NOW + timedelta(minutes=35), "Mais uma"))
    assert [n.key for n in run(m, st, NOW + timedelta(minutes=45)) if n.key.startswith("msg:")] == ["msg:5"]


def test_existing_installation_gets_last_7_days_once_as_summary(tmp_path):
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    st.data = {"initialized": NOW.isoformat(), "seen": {}, "features": ["edits", "config", "forums", "grades",
                                                                         "events"]}
    m.convs = [conv(40, [msg(1, 9, NOW - timedelta(days=1), "Respondi"), msg(2, 9, NOW - timedelta(days=20))])]
    out = [n for n in run(m, st, NOW) if n.key.startswith(("msg", "msgbacklog"))]
    assert len(out) == 1 and out[0].title == "1 mensagem(ns) recebida(s) nos últimos 7 dias"
    assert "Andreza" in out[0].body and "Respondi" in out[0].body
    assert not [n for n in run(m, st, NOW + timedelta(minutes=15)) if n.key.startswith(("msg", "msgbacklog"))]


def test_moodle_notifications_without_repeating_what_was_already_sent(tmp_path):
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    t = (NOW + timedelta(minutes=5)).timestamp()
    m.notifs = [
        {"id": 1, "component": "mod_assign", "eventtype": "assign_due_soon", "subject": "Vencimento amanhã",
         "contexturl": "https://m/mod/assign/view.php?id=12", "timecreated": t},
        {"id": 2, "component": "mod_assign", "eventtype": "assign_notification",
         "subject": "Fulano retornou feedback para a tarefa X", "contexturl": "https://m/mod/assign/view.php?id=13",
         "timecreated": t},
        {"id": 3, "component": "mod_forum", "eventtype": "posts", "subject": "Re: Bem-vindos",
         "contexturl": "https://nead.ifb.edu.br/mod/forum/discuss.php?d=900#p5", "timecreated": t},
    ]
    st.data.setdefault("refs", {})["d:900"] = NOW.isoformat()            # o aviso do fórum já foi enviado
    out = run(m, st, NOW + timedelta(minutes=15))
    assert [n.key for n in out if n.key.startswith("notif:")] == ["notif:2"]
    check = next(n for n in out if n.key.startswith("check:"))
    assert "3 item(ns)" in check.body and "2 já coberto(s)" in check.body and "✅ 1 enviado" in check.body
    assert not [n for n in run(m, st, NOW + timedelta(minutes=30)) if n.key.startswith(("notif:", "check:"))]


def test_backlog_summary_fits_in_one_telegram_message(tmp_path):
    from nead_avisos.telegram import LIMIT, render
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    st.data = {"initialized": NOW.isoformat(), "seen": {}}
    m.convs = [conv(40 + i, [msg(i, 9, NOW - timedelta(hours=i + 1), "palavra " * 200)]) for i in range(30)]
    out = next(n for n in run(m, st, NOW) if n.key.startswith("msgbacklog"))
    assert len(render(out)) < LIMIT and out.title.startswith("30 mensagem(ns)")
