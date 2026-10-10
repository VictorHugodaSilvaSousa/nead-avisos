# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""Avisos mais claros: notificações do Moodle traduzidas, tempo restante, sem cópia dupla, botão certo, silêncio."""

from datetime import timedelta

from nead_avisos import cli
from nead_avisos.collect import Collector, Notice, left
from nead_avisos.config import Settings
from nead_avisos.state import State
from nead_avisos.telegram import Telegram, button_label
from test_collect import NOW, FakeMoodle


def collector(tmp_path):
    c = Collector(Settings(), FakeMoodle(), State(tmp_path / "s.json"), NOW)
    c.short_names = {"BDII_2026/2": "Banco de Dados II"}
    return c


def test_moodle_notifications_in_plain_language(tmp_path):
    c = collector(tmp_path)
    hz = lambda **n: c._humanize(n)  # noqa: E731
    icon, title, course, body = hz(
        component="moodle", eventtype="coursecontentupdated",
        subject="Conteúdo alterado em [TDS_M3] Empreendedorismo 2026/2",
        smallmessage="Tarefa TRABALHO EM GRUPO (NOVO PRAZO 16 de OUTUBRO) foi alterado no curso [TDS_M3] "
                     "Empreendedorismo 2026/2.Altere suas preferências de notificação")
    assert (icon, title, course) == ("✏️", "Alterado pelo professor: Tarefa TRABALHO EM GRUPO (NOVO PRAZO 16 de OUTUBRO)",
                                     "Empreendedorismo")
    assert "prazo" in body and "preferências" not in body
    assert hz(component="moodle", eventtype="coursecontentupdated", subject="Novo conteúdo em X",
              smallmessage="URL Material extra é novo no curso [TDS_M3] Sistemas Operacionais 2026/2.")[:2] == \
        ("🆕", "Novo na sala: URL Material extra")
    assert hz(component="mod_assign", eventtype="assign_notification",
              subject="Você enviou sua tarefa para Atividade 3", smallmessage="Você enviou sua tarefa para Atividade 3") \
        == ("✅", "Envio confirmado: Atividade 3", "", "")
    icon, title, _, body = hz(component="mod_assign", eventtype="assign_notification",
                              subject="ALEXANDRE LAVAL retornou feedback para a tarefa ENTREGA: Ideias", smallmessage="")
    assert (icon, title) == ("📝", "Feedback do professor: ENTREGA: Ideias") and "ALEXANDRE LAVAL" in body
    icon, title, course, body = hz(
        component="mod_forum", eventtype="posts", subject="[TDS_M3] BDII_2026/2: [18/09] Avaliação: Projeto de BD",
        smallmessage="JOSANE BORGES enviou mensagem em [TDS_M3] BDII_2026/2: Avisos: [18/09] Avaliação")
    assert (icon, title, course) == ("📢", "[18/09] Avaliação: Projeto de BD", "Banco de Dados II")
    assert "JOSANE BORGES</i> publicou em Avisos" in body


def test_time_left():
    assert left(NOW + timedelta(hours=22), NOW) == "faltam 22 h"
    assert left(NOW + timedelta(days=1, hours=3), NOW) == "faltam 1 dia e 3 h"
    assert left(NOW + timedelta(days=3, hours=1), NOW) == "faltam 3 dias"
    assert left(NOW + timedelta(minutes=30), NOW) == "faltam 30 min"
    assert left(NOW - timedelta(days=2, hours=1), NOW) == "venceu há 2 dias"


def test_class_reminder_not_repeated_in_private_chat_when_personal_exists(tmp_path):
    c = collector(tmp_path)
    c.notices = [Notice("due:5:1", "group", "⏰", "Prazo amanhã: X", extra={"event": 5}),
                 Notice("mine:5:1d", "me", "🔴", "Você ainda não entregou (amanhã): X", extra={"event": 5}),
                 Notice("due:6:1", "group", "⏰", "Prazo amanhã: Y", extra={"event": 6})]
    c._no_double_reminders()
    assert c.notices[0].extra.get("skip_me") and not c.notices[2].extra.get("skip_me")


def test_button_labels():
    assert button_label(Notice("msg:1", "me", "✉️", "t", url="u")) == "💬 Responder no Moodle"
    assert button_label(Notice("mine:1:1d", "me", "🔴", "t", url="u")) == "📝 Abrir e entregar"
    assert button_label(Notice("notif:9", "me", "📢", "t", url="u")) == "📢 Abrir aviso"
    assert button_label(Notice("grade:1:2", "me", "📊", "t", url="u")) == "📊 Ver nota"


def test_quiet_hours_send_without_sound_except_urgent(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(Telegram, "_api", lambda self, m, p: {"ok": True, "result": []} if m == "getUpdates" else
                        sent.append((p.get("chat_id"), p.get("text", "")[:40], p.get("disable_notification")))
                        or {"ok": True})
    monkeypatch.setattr(cli, "get_secret", lambda name: "1:a")
    monkeypatch.setattr(cli, "_moodle", lambda s: type("M", (), {"calls": 0})())
    monkeypatch.setattr("time.sleep", lambda x: None)
    notices = [Notice("mod:1", "me", "📝", "Nova atividade"),
               Notice("mine:2:6h", "me", "🔴", "Você ainda não entregou", extra={"urgent": True}),
               Notice("notif:3", "me", "✅", "Envio confirmado", extra={"quiet": True})]

    class FakeCollector:
        def __init__(self, s, m, state):
            self.first_run, self.m, self.state = False, m, state

        def run(self):
            return list(notices)
    monkeypatch.setattr(cli, "Collector", FakeCollector)

    class Night:
        @staticmethod
        def now(tz=None):
            from datetime import datetime
            return datetime(2026, 10, 7, 23, 30, tzinfo=tz)
    s = Settings()
    s.data_dir, s.telegram_chat_id = tmp_path, 111
    monkeypatch.setattr(cli, "datetime", type("D", (), {"now": Night.now, "fromisoformat":
                                                        __import__("datetime").datetime.fromisoformat}))
    cli._run(s, dry_run=False)
    silent = {t.split("<b>", 1)[1].split("</b>")[0]: q for _, t, q in sent}
    assert silent == {"Nova atividade": True, "Você ainda não entregou": False, "Envio confirmado": True}


def test_sent_time_is_never_confused_with_today():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from nead_avisos.collect import sent_label
    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime(2026, 10, 8, 9, 0, tzinfo=tz)
    assert sent_label(datetime(2026, 10, 8, 8, 15, tzinfo=tz), now) == "hoje às 08:15"
    assert sent_label(datetime(2026, 10, 7, 21, 10, tzinfo=tz), now) == "ontem (07/10, qua) às 21:10"
    assert sent_label(datetime(2026, 10, 5, 21, 10, tzinfo=tz), now) == "em 05/10 (seg) às 21:10"
