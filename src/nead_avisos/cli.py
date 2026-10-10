# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
"""NEAD Avisos — avisos do Moodle do NEAD/IFB no Telegram (celular e PC).

  nead-avisos setup              login no Moodle (uma vez) -> guarda só a chave de acesso
  nead-avisos set-telegram       guarda o token do SEU bot do Telegram (@BotFather)
  nead-avisos chats              mostra os chats/grupos que falaram com o bot (para achar os IDs)
  nead-avisos set-chat ID        define o seu chat privado      | nead-avisos set-group -ID   define o grupo
  nead-avisos run [--dry-run]    busca novidades e envia (dry-run: só mostra, não envia nem salva)
  nead-avisos status             o que está configurado e quais salas são acompanhadas
  nead-avisos show-token         mostra a chave do Moodle (para o Secret do GitHub, na versão na nuvem)

Somente leitura no Moodle: nada é enviado, marcado ou alterado lá.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timedelta

from .collect import Collector, short_course
from .config import SERVICE, Settings, get_secret, set_secret
from .moodle import AuthError, Moodle, MoodleError, get_token
from .state import State, StateKeyError, state_key
from .telegram import Telegram, e


def _ask_secret(prompt: str) -> str:
    print("Para colar: clique com o BOTÃO DIREITO do mouse (Ctrl+V não funciona neste campo).")
    value = getpass.getpass(prompt)
    if any(ord(c) < 32 for c in value):
        raise SystemExit("Caracteres invisíveis recebidos (Ctrl+V). Cole com o botão direito e tente de novo.")
    return value.strip()


def cmd_setup(s: Settings) -> int:
    user = s.username or input("Usuário do Moodle (o mesmo da tela de login): ").strip()
    password = _ask_secret("Senha do Moodle (não aparece na tela): ")
    try:
        token = get_token(s.base_url, user, password)
    except (AuthError, MoodleError) as exc:
        print(f"Não foi possível entrar: {exc}", file=sys.stderr)
        return 2
    finally:
        password = user = ""
    set_secret("moodle_token", token)
    from .assistente import forget_username
    forget_username()                    # o usuário (no NEAD, o CPF) não fica gravado no .env
    print("Pronto: a chave de acesso foi guardada no Gerenciador de Credenciais do Windows. A senha NÃO foi guardada.")
    return cmd_status(s)


def _clipboard() -> str:
    """Lê a área de transferência do Windows (o token não passa pelo terminal nem fica no histórico)."""
    import subprocess
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True,
                         text=True, timeout=15)
    return (out.stdout or "").strip()


def cmd_set_telegram() -> int:
    token = _clipboard()
    if ":" in token and len(token) >= 30 and " " not in token:
        print("Token lido da área de transferência (copiado do BotFather).")
        from .assistente import _to_clipboard
        _to_clipboard("")                     # o token não fica esquecido na área de transferência
    else:
        token = _ask_secret("Token do seu bot (do @BotFather): ")
    if ":" not in token or len(token) < 30:
        print("Isso não parece um token do BotFather (formato 123456789:AA...).", file=sys.stderr)
        return 2
    bot = Telegram(token).me()
    if not bot:
        print("O Telegram recusou esse token.", file=sys.stderr)
        return 2
    set_secret("telegram_token", token)
    print(f"Bot @{bot.get('username')} configurado. Agora mande /start para ele e rode: nead-avisos chats")
    return 0


def _set_env(key: str, value: str) -> None:
    """Grava/atualiza NEAD_AVISOS_<key>=value no .env do projeto (IDs não são segredos)."""
    from .config import PROJECT_ROOT
    path = PROJECT_ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    name = f"NEAD_AVISOS_{key}"
    lines = [ln for ln in lines if not ln.lstrip("# ").startswith(f"{name}=")]
    lines.append(f"{name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_set_chat(kind: str, chat_id: str) -> int:
    if not chat_id.lstrip("-").isdigit():
        print("Use o número mostrado por: nead-avisos chats", file=sys.stderr)
        return 2
    if kind == "group" and not chat_id.startswith("-"):
        print("ID de grupo começa com '-' (veja: nead-avisos chats).", file=sys.stderr)
        return 2
    _set_env("TELEGRAM_GROUP_ID" if kind == "group" else "TELEGRAM_CHAT_ID", chat_id)
    print(("Grupo da turma" if kind == "group" else "Seu chat") + f" configurado: {chat_id}")
    return 0


def _copy_secret(value: str, secret_name: str, warning: str) -> int:
    """Copia um segredo para a área de transferência (nunca na tela) e apaga depois do ENTER."""
    from .assistente import _to_clipboard
    print(warning)
    _to_clipboard(value)
    print(f"\nO valor foi COPIADO (não aparece na tela). Cole no Secret '{secret_name}' do seu repositório:\n"
          "Settings > Secrets and variables > Actions > New repository secret.")
    try:
        input("Depois de colar, aperte ENTER para apagar o valor da área de transferência...")
    finally:
        _to_clipboard("")
    print("Área de transferência limpa.")
    return 0


def cmd_show_token() -> int:
    """Copia a chave do Moodle para colar no Secret do GitHub. É pessoal: não envie a ninguém."""
    token = get_secret("moodle_token")
    if not token:
        print("Moodle não configurado. Rode: nead-avisos setup", file=sys.stderr)
        return 2
    return _copy_secret(token, "NEAD_AVISOS_MOODLE_TOKEN",
                        "ATENÇÃO: esta chave dá acesso à sua conta do Moodle como o app oficial (o NEAD Avisos só lê, "
                        "mas a chave em si permitiria mais). Cole-a SÓ no Secret do seu repositório e nunca a envie a "
                        "ninguém. Se vazar: Moodle > seu perfil > Preferências > Chaves de segurança > Redefinir.")


def cmd_cloud_key() -> int:
    """Copia a chave que criptografa o estado, para o Secret NEAD_AVISOS_CHAVE_ESTADO da nuvem."""
    from .state import state_key
    return _copy_secret(state_key().decode(), "NEAD_AVISOS_CHAVE_ESTADO",
                        "Esta chave criptografa o que o NEAD Avisos guarda (o que já foi avisado). Sem ela, o "
                        "cache da nuvem é ilegível para qualquer pessoa.")


def cmd_erase() -> int:
    """Apaga tudo o que o NEAD Avisos guardou neste PC e explica como revogar as chaves."""
    import shutil
    import subprocess
    s = Settings.load()
    print("Isto apaga deste PC: o estado (o que já foi avisado), o registro, as chaves guardadas no Gerenciador de\n"
          "Credenciais (Moodle, Telegram, criptografia) e a tarefa agendada. Os avisos param neste PC.")
    if input("Digite APAGAR para confirmar: ").strip().upper() != "APAGAR":
        print("Nada foi apagado.")
        return 0
    shutil.rmtree(s.data_dir, ignore_errors=True)
    for name in ("moodle_token", "telegram_token", "chave_estado"):
        try:
            import keyring
            keyring.delete_password(SERVICE, name)
        except Exception:  # noqa: BLE001 — já não existia
            pass
    subprocess.run(["schtasks", "/Delete", "/TN", "NEAD-Avisos", "/F"], capture_output=True)
    print("\nApagado deste PC. Para cortar o acesso de vez:\n"
          "  1. Moodle > seu perfil > Preferências > Chaves de segurança > Redefinir (invalida a chave do app).\n"
          "  2. Telegram > @BotFather > /mybots > seu robô > Delete Bot (ou Revoke current token).\n"
          "  3. Se usava a nuvem: apague o seu repositório no GitHub (Settings > Delete this repository)\n"
          "     e o agendamento no cron-job.org.")
    return 0


def cmd_chats() -> int:
    token = get_secret("telegram_token")
    if not token:
        print("Configure o bot antes: nead-avisos set-telegram", file=sys.stderr)
        return 2
    chats = {}
    for u in Telegram(token).updates():
        msg = u.get("message") or u.get("my_chat_member") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat:
            chats[chat["id"]] = (chat.get("type"), chat.get("title") or chat.get("first_name") or "")
    if not chats:
        print("Nenhuma conversa ainda. Mande /start para o bot (e, no grupo, adicione o bot e escreva /start@NOME_DO_BOT).")
    for cid, (kind, name) in chats.items():
        tipo = "PRIVADO (use em NEAD_AVISOS_TELEGRAM_CHAT_ID)" if kind == "private" else \
            "GRUPO (use em NEAD_AVISOS_TELEGRAM_GROUP_ID)"
        print(f"  {cid:>16}  {tipo}  {name}")
    return 0


def _moodle(s: Settings) -> Moodle:
    token = get_secret("moodle_token")
    if not token:
        raise SystemExit("Moodle não configurado. Rode: nead-avisos setup")
    return Moodle(s.base_url, token)


def cmd_status(s: Settings) -> int:
    m = _moodle(s)
    state = State(s.data_dir / "state.json", key=state_key())
    col = Collector(s, m, state)
    courses = col.courses()
    group = col.group_course_ids(courses)
    print(f"Salas acompanhadas ({len(courses)}), onde você é ALUNO e que estão em andamento:")
    for c in courses:
        where = "seu chat + GRUPO" if c["id"] in group else "só seu chat"
        print(f"  {c['id']:>6}  [{where:<16}] {short_course(c['fullname'])}")
    print("Telegram:", "configurado" if get_secret("telegram_token") else "FALTA (nead-avisos set-telegram)",
          "| seu chat:", s.telegram_chat_id or "FALTA", "| grupo da turma:", s.telegram_group_id or "não definido")
    state.save()
    return 0


def _acquire_lock(path) -> bool:
    """Evita duas execuções ao mesmo tempo (ex.: agendador + teste manual). Trava velha (>30 min) é ignorada."""
    import os
    import time
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists() and time.time() - path.stat().st_mtime > 1800:
            path.unlink()
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def cmd_run(s: Settings, dry_run: bool) -> int:
    lock = s.data_dir / "run.lock"
    if not dry_run and not _acquire_lock(lock):
        print("Outra execução do NEAD Avisos está em andamento; saindo.")
        return 0
    try:
        return _run(s, dry_run)
    finally:
        if not dry_run:
            lock.unlink(missing_ok=True)


# Avisos com dado pessoal (mensagens, notas, comentários, pendências, notificações do Moodle, resumos pessoais):
# só no chat da própria pessoa.
PERSONAL_KINDS = frozenset({"msg", "msgbacklog", "notif", "grade", "feedback", "mine", "late", "mydigest", "check"})


def _run(s: Settings, dry_run: bool) -> int:
    import time
    t0 = time.monotonic()
    try:
        state = State(s.data_dir / "state.json", key=state_key())
    except StateKeyError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        _alert(s, f"⚠️ <b>NEAD Avisos parou</b>: {e(exc)}. Configure o Secret NEAD_AVISOS_CHAVE_ESTADO.")
        return 1
    if state.reset_reason:
        print(f"Estado recomeçado do zero ({state.reset_reason}); esta execução só registra o estado atual.",
              file=sys.stderr)
    # Só o formato do estado (nenhum dado): confirma nos registros que ele está protegido.
    print("Estado: " + ("CRIPTOGRAFADO" if state.encrypted else "sem criptografia (falta a chave)")
          + (" — convertido agora do formato antigo" if state.was_plain and state.encrypted else "")
          + (" — novo" if not state.data and not state.reset_reason else ""))
    try:
        col = Collector(s, _moodle(s), state)
        tg_for_cmds = get_secret("telegram_token")
        if tg_for_cmds and s.telegram_chat_id and not dry_run:
            # Comandos que você mandou ao robô desde a última execução (só do seu chat privado).
            try:
                col.commands, nxt = Telegram(tg_for_cmds).owner_commands(s.telegram_chat_id,
                                                                         state.data.get("tg_offset"))
                if nxt:
                    state.data["tg_offset"] = nxt
            except Exception:  # noqa: BLE001 — comandos são opcionais; os avisos seguem
                col.commands = []
        notices = col.run()
    except AuthError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        if _alert_due(state, "auth", hours=6):
            _alert(s, f"⚠️ <b>NEAD Avisos parou</b>: {e(exc)}\nOs avisos voltam assim que a chave for renovada.")
        state.save()
        return 1
    except MoodleError as exc:
        print(f"Moodle indisponível agora (tento de novo na próxima): {exc}", file=sys.stderr)
        down = state.data.setdefault("down_since", datetime.now(s.tz).isoformat(timespec="seconds"))
        if (datetime.now(s.tz) - datetime.fromisoformat(down)).total_seconds() > 6 * 3600 and \
                _alert_due(state, "down", hours=12):
            _alert(s, "⚠️ <b>NEAD Avisos</b>: o Moodle do NEAD está fora do ar (ou inacessível) desde "
                      f"{datetime.fromisoformat(down):%d/%m %H:%M}. Os avisos voltam sozinhos quando ele normalizar.")
        state.save()
        return 0          # instabilidade do site não é erro do programa; nada foi marcado como visto
    if state.data.pop("down_since", None):
        state.data.pop("alerted", None)
    now = datetime.now(s.tz)
    if dry_run:
        print(f"{len(notices)} aviso(s) seriam enviados (primeira execução: {col.first_run}):")
        from .group_digest import is_urgent_for_group
        for n in notices:
            where = n.audience
            if n.audience == "group" and s.group_slots and not is_urgent_for_group(n):
                where = "group: resumo"
            print(f"  [{where}] {n.icon} {n.title} | {n.course}")
        return 0
    tg_token = get_secret("telegram_token")
    sent = failed = 0
    if notices and (not tg_token or not s.telegram_chat_id):
        print("Telegram não configurado: os avisos NÃO foram marcados como enviados.", file=sys.stderr)
        return 2
    from urllib.parse import urlparse
    tg = Telegram(tg_token, link_host=urlparse(s.base_url).hostname) if tg_token else None
    # Grupo que virou supergrupo numa execução anterior: usa o id novo guardado no estado.
    group_id = state.data.get("group_migrated", {}).get(str(s.telegram_group_id), s.telegram_group_id)
    partial = state.data.setdefault("partial", {})      # aviso -> chats que JÁ receberam (nunca repete)
    from .group_digest import current_slot, entry as digest_entry, is_urgent_for_group, render as render_digest
    group_queue = state.data.setdefault("group_queue", [])
    quiet = False
    if s.quiet_hours:
        a, b = s.quiet_hours
        quiet = (a <= now.hour or now.hour < b) if a > b else (a <= now.hour < b)
    for n in sorted(notices, key=lambda n: (n.when or now)):
        if n.audience == "group" and n.key.split(":", 1)[0] in PERSONAL_KINDS:
            n.audience = "me"                 # trava: dado pessoal NUNCA vai para o grupo, mesmo com bug acima
        dests = [s.telegram_chat_id] + ([group_id] if n.audience == "group" and group_id else [])
        if n.extra.get("skip_me") and group_id and n.audience == "group":
            dests = [group_id]               # você já recebe o lembrete pessoal do mesmo prazo
        if group_id in dests and s.group_slots and not is_urgent_for_group(n):
            # Grupo em ritmo de resumo: entra na fila do próximo horário (não toca o celular de todo mundo agora).
            if n.key not in {e["key"] for e in group_queue}:
                group_queue.append(digest_entry(n, tg.safe_link))
            dests = [d for d in dests if d != group_id]
        info = partial.get(n.key, {"done": [], "since": now.isoformat()})
        for chat in dests:
            if chat not in info["done"] and tg.send(chat, n, silent=n.extra.get("quiet") or (quiet and not n.extra.get("urgent"))):
                info["done"].append(chat)
        if all(chat in info["done"] for chat in dests):
            sent += 1
            partial.pop(n.key, None)
            continue
        failed += 1
        if datetime.fromisoformat(info["since"]) < now - timedelta(days=1):
            print(f"Desistindo de um aviso do tipo '{n.key.split(':', 1)[0]}' após 1 dia de falhas.", file=sys.stderr)
            partial.pop(n.key, None)                       # fica marcado como visto: não tenta mais
            continue
        partial[n.key] = info
        for key in n.extra.get("keys", [n.key]):          # tenta de novo na próxima, só onde faltou
            state.data.get("seen", {}).pop(key, None)
    slot = current_slot(now, s.group_slots) if s.group_slots else None
    if group_id and tg and group_queue and slot and state.data.get("group_last_slot") != slot:
        messages = render_digest(group_queue, now)
        if all(tg.send_text(group_id, text) for text in messages):
            print(f"Resumo do grupo enviado: {len(group_queue)} item(ns) em {len(messages)} mensagem(ns).")
            state.data["group_queue"] = []
            state.data["group_last_slot"] = slot
        else:
            failed += 1                       # a fila fica para a próxima execução
    elif slot and not group_queue:
        state.data["group_last_slot"] = slot
    if tg and tg.migrated:
        moves = state.data.setdefault("group_migrated", {})
        for old, new in tg.migrated.items():
            moves[str(old)] = new
            if s.telegram_group_id is not None:
                moves[str(s.telegram_group_id)] = new
        tg.send_text(s.telegram_chat_id, "ℹ️ <b>NEAD Avisos</b>: o grupo da turma virou supergrupo no Telegram e "
                                         f"ganhou um número novo ({new}). Já estou usando o número novo. Para "
                                         "deixar registrado, atualize NEAD_AVISOS_TELEGRAM_GROUP_ID para esse número.")
    if col.first_run and tg and s.telegram_chat_id:
        import os
        where = " na nuvem (funciona com o PC desligado)" if os.environ.get("GITHUB_ACTIONS") else ""
        tg.send_text(s.telegram_chat_id, f"✅ <b>NEAD Avisos ativado{where}</b>\nAcompanhando "
                                         f"{len(state.data.get('courses', {}))} sala(s). A partir de agora você recebe "
                                         "só as novidades.")
    state.prune(now)
    state.save()
    print(f"{now:%d/%m %H:%M} — {sent} aviso(s) enviado(s), {failed} falha(s), {col.m.calls} consulta(s) ao Moodle, "
          f"{time.monotonic() - t0:.0f}s.")
    return 0 if not failed else 3


def _alert_due(state: State, kind: str, hours: int) -> bool:
    """Evita repetir o mesmo alerta de erro a cada 15 min: no máximo 1 a cada `hours` horas."""
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    now = _dt.now(_tz.utc)
    alerted = state.data.setdefault("alerted", {})
    last = alerted.get(kind)
    if last and now - _dt.fromisoformat(last) < _td(hours=hours):
        return False
    alerted[kind] = now.isoformat(timespec="seconds")
    return True


def _alert(s: Settings, text: str) -> None:
    token = get_secret("telegram_token")
    if token and s.telegram_chat_id:
        Telegram(token).send_text(s.telegram_chat_id, text)


def main(argv: list[str] | None = None) -> int:
    # Saída redirecionada (tarefa agendada, .exe) pode usar cp1252: um emoji não pode derrubar o programa.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="nead-avisos", description="Avisos do Moodle do NEAD no Telegram")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("assistente", help="configuração passo a passo (abre ao dar dois cliques no .exe)")
    sub.add_parser("setup")
    sub.add_parser("set-telegram")
    sub.add_parser("chats")
    sub.add_parser("show-token", help="copia a chave do Moodle (para o Secret da nuvem), sem mostrar na tela")
    sub.add_parser("chave-nuvem", help="copia a chave de criptografia do estado (Secret NEAD_AVISOS_CHAVE_ESTADO)")
    sub.add_parser("apagar-tudo", help="apaga deste PC todos os dados e chaves do NEAD Avisos")
    p_chat = sub.add_parser("set-chat", help="define o seu chat privado (número de: nead-avisos chats)")
    p_chat.add_argument("chat_id")
    p_group = sub.add_parser("set-group", help="define o grupo da turma (número negativo de: nead-avisos chats)")
    p_group.add_argument("chat_id")
    sub.add_parser("status")
    p_run = sub.add_parser("run")
    p_run.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd in (None, "assistente"):           # dois cliques no .exe = assistente
        from .assistente import main as assistente
        return assistente()
    s = Settings.load()
    if args.cmd == "setup":
        return cmd_setup(s)
    if args.cmd == "set-telegram":
        return cmd_set_telegram()
    if args.cmd == "chats":
        return cmd_chats()
    if args.cmd == "chave-nuvem":
        return cmd_cloud_key()
    if args.cmd == "apagar-tudo":
        return cmd_erase()
    if args.cmd == "show-token":
        return cmd_show_token()
    if args.cmd in ("set-chat", "set-group"):
        return cmd_set_chat("group" if args.cmd == "set-group" else "me", args.chat_id)
    if args.cmd == "status":
        return cmd_status(s)
    return cmd_run(s, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
