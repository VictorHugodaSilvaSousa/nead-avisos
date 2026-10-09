"""Segurança e sigilo: estado cifrado, mínimo de dados guardados, registros sem dado pessoal, links seguros."""

import json
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

from nead_avisos.collect import Collector, Notice, as_digest, digest
from nead_avisos.config import Settings
from nead_avisos.state import MAGIC, State, StateKeyError
from nead_avisos.telegram import Telegram
from test_collect import NOW, FakeMoodle

KEY = Fernet.generate_key()


def test_state_on_disk_is_encrypted_and_unreadable_without_the_key(tmp_path):
    path = tmp_path / "state.json"
    st = State(path, key=KEY)
    st.data = {"seen": {"msg:1": "x"}, "courses": {"1": "[TDS_M3] Banco de Dados II 2026/2"}}
    st.save()
    raw = path.read_bytes()
    assert raw.startswith(MAGIC) and b"Banco de Dados" not in raw and b"msg:1" not in raw
    assert State(path, key=KEY).data["courses"]["1"].startswith("[TDS_M3]")
    with pytest.raises(StateKeyError):
        State(path)                                         # sem chave: recusa (não inventa estado vazio)
    other = State(path, key=Fernet.generate_key())          # chave errada: recomeça do zero, sem quebrar
    assert other.data == {} and other.reset_reason


def test_old_plain_state_is_converted_to_encrypted(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"seen": {"mod:1": "x"}}), encoding="utf-8")
    st = State(path, key=KEY)
    assert st.was_plain and st.data["seen"] == {"mod:1": "x"}
    st.save()
    assert path.read_bytes().startswith(MAGIC)


def test_state_keeps_only_fingerprints_of_texts(tmp_path):
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    m.modules[1][0]["description"] = "<p>Enunciado com dados da turma</p>"
    m.grades[1] = [{"id": 5, "itemtype": "mod", "itemname": "Tarefa", "gradeformatted": "9,00", "cmid": 11,
                    "feedback": "<p>Muito bom, Ana!</p>"}]
    Collector(Settings(), m, st, NOW).run()
    dump = json.dumps(st.data, ensure_ascii=False)
    assert "Enunciado com dados" not in dump and "Muito bom, Ana" not in dump
    assert st.data["fp"]["11"]["desc"] == digest("Enunciado com dados da turma")


def test_old_state_with_texts_does_not_cause_false_changes(tmp_path):
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    m.modules[1][0]["description"] = "<p>Leia o capítulo 3</p>"
    Collector(Settings(), m, st, NOW).run()
    st.data["fp"]["11"]["desc"] = "Leia o capítulo 3"            # como a versão anterior guardava
    out = Collector(Settings(), m, st, NOW + timedelta(minutes=15)).run()
    assert not [n for n in out if n.key.startswith(("edit:", "duechange:"))]
    assert as_digest("Leia o capítulo 3") == digest("Leia o capítulo 3") and as_digest("") == ""


def test_buttons_only_point_to_the_moodle_over_https():
    tg = Telegram("t", link_host="nead.ifb.edu.br")
    assert tg.safe_link("https://nead.ifb.edu.br/mod/assign/view.php?id=1")
    assert not tg.safe_link("https://nead.ifb.edu.br.golpe.com/login")
    assert not tg.safe_link("http://nead.ifb.edu.br/mod/assign/view.php?id=1")
    assert not tg.safe_link("javascript:alert(1)")


def test_logs_never_show_titles(monkeypatch, capsys):
    monkeypatch.setattr(Telegram, "_api", lambda self, m, p: {"ok": False, "description": "Forbidden"})
    monkeypatch.setattr("time.sleep", lambda x: None)
    Telegram("t").send(1, Notice("msg:9", "me", "✉️", "Mensagem de Fulano da Silva", body="texto"))
    err = capsys.readouterr().err
    assert "Fulano" not in err and "'msg'" in err


def test_personal_notices_never_reach_the_class_group(tmp_path, monkeypatch):
    from nead_avisos import cli
    sent = []
    monkeypatch.setattr(Telegram, "_api", lambda self, m, p: {"ok": True, "result": []} if m == "getUpdates"
                        else sent.append(p.get("chat_id")) or {"ok": True})
    monkeypatch.setattr("time.sleep", lambda x: None)
    monkeypatch.setattr(cli, "_moodle", lambda s: type("M", (), {"calls": 0})())
    import nead_avisos.config as cfg
    real = cfg.get_secret
    monkeypatch.setattr(cli, "get_secret", lambda n: "1:a" if n == "telegram_token" else real(n))
    bad = [Notice(f"{kind}:1", "group", "x", "pessoal") for kind in sorted(cli.PERSONAL_KINDS)]

    class FakeCollector:
        def __init__(self, s, m, state):
            self.first_run, self.m, self.state = False, m, state

        def run(self):
            return list(bad)
    monkeypatch.setattr(cli, "Collector", FakeCollector)
    s = Settings()
    s.data_dir, s.telegram_chat_id, s.telegram_group_id = tmp_path, 111, -999
    cli._run(s, dry_run=False)
    assert sent and -999 not in sent and set(sent) == {111}


def test_pairing_accepts_only_the_chat_that_sent_the_one_time_code():
    tg = Telegram("t")
    updates = [{"message": {"chat": {"id": 666, "type": "private"}, "text": "/start"}},          # intruso
               {"message": {"chat": {"id": 777, "type": "private"}, "text": "/start abc123"}},  # código errado
               {"message": {"chat": {"id": -5, "type": "group"}, "text": "/start c0ffee12"}},  # grupo
               {"message": {"chat": {"id": 111, "type": "private"}, "text": "/start c0ffee12"}}]
    assert tg.pairing_chat("c0ffee12", updates)["id"] == 111
    assert tg.pairing_chat("c0ffee12", updates[:3]) is None
    assert tg.pairing_chat("c0ffee12", [{"message": {"chat": {"id": 9, "type": "private"}, "text": "c0ffee12"}}])["id"] == 9


def test_moodle_username_cpf_is_never_kept_in_env(tmp_path, monkeypatch):
    from nead_avisos import assistente
    monkeypatch.setattr(assistente, "PROJECT_ROOT", tmp_path)
    env = tmp_path / ".env"
    env.write_text("NEAD_AVISOS_USERNAME=12345678900\nNEAD_AVISOS_TELEGRAM_CHAT_ID=111\n", encoding="utf-8")
    assistente.forget_username()
    assert env.read_text(encoding="utf-8") == "NEAD_AVISOS_TELEGRAM_CHAT_ID=111\n"
