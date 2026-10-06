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
from .config import Settings, get_secret, set_secret
from .moodle import AuthError, Moodle, MoodleError, get_token
from .state import State
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
    set_secret("moodle_token", token)
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


def cmd_show_token() -> int:
    """Mostra a chave do Moodle para colar no Secret do GitHub. É pessoal: não envie a ninguém."""
    token = get_secret("moodle_token")
    if not token:
        print("Moodle não configurado. Rode: nead-avisos setup", file=sys.stderr)
        return 2
    print("ATENÇÃO: esta chave dá acesso de LEITURA à sua conta do Moodle. Cole-a só no Secret "
          "NEAD_AVISOS_MOODLE_TOKEN do seu repositório e não a envie a ninguém.\n")
    print(token)
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
    state = State(s.data_dir / "state.json")
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


def _run(s: Settings, dry_run: bool) -> int:
    import time
    t0 = time.monotonic()
    state = State(s.data_dir / "state.json")
    try:
        col = Collector(s, _moodle(s), state)
        notices = col.run()
    except AuthError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        _alert(s, f"⚠️ <b>NEAD Avisos</b>: {e(exc)}")
        return 1
    except MoodleError as exc:
        print(f"Moodle indisponível agora (tento de novo na próxima): {exc}", file=sys.stderr)
        return 0          # instabilidade do site não é erro do programa; nada foi marcado como visto
    now = datetime.now(s.tz)
    if dry_run:
        print(f"{len(notices)} aviso(s) seriam enviados (primeira execução: {col.first_run}):")
        for n in notices:
            print(f"  [{n.audience}] {n.icon} {n.title} | {n.course}")
        return 0
    tg_token = get_secret("telegram_token")
    sent = failed = 0
    if notices and (not tg_token or not s.telegram_chat_id):
        print("Telegram não configurado: os avisos NÃO foram marcados como enviados.", file=sys.stderr)
        return 2
    tg = Telegram(tg_token) if tg_token else None
    # Grupo que virou supergrupo numa execução anterior: usa o id novo guardado no estado.
    group_id = state.data.get("group_migrated", {}).get(str(s.telegram_group_id), s.telegram_group_id)
    partial = state.data.setdefault("partial", {})      # aviso -> chats que JÁ receberam (nunca repete)
    for n in sorted(notices, key=lambda n: (n.when or now)):
        dests = [s.telegram_chat_id] + ([group_id] if n.audience == "group" and group_id else [])
        info = partial.get(n.key, {"done": [], "since": now.isoformat()})
        for chat in dests:
            if chat not in info["done"] and tg.send(chat, n):
                info["done"].append(chat)
        if all(chat in info["done"] for chat in dests):
            sent += 1
            partial.pop(n.key, None)
            continue
        failed += 1
        if datetime.fromisoformat(info["since"]) < now - timedelta(days=1):
            print(f"Desistindo de '{n.title[:40]}' após 1 dia de falhas.", file=sys.stderr)
            partial.pop(n.key, None)                       # fica marcado como visto: não tenta mais
            continue
        partial[n.key] = info
        for key in n.extra.get("keys", [n.key]):          # tenta de novo na próxima, só onde faltou
            state.data.get("seen", {}).pop(key, None)
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


def _alert(s: Settings, text: str) -> None:
    token = get_secret("telegram_token")
    if token and s.telegram_chat_id:
        Telegram(token).send_text(s.telegram_chat_id, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nead-avisos", description="Avisos do Moodle do NEAD no Telegram")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("assistente", help="configuração passo a passo (abre ao dar dois cliques no .exe)")
    sub.add_parser("setup")
    sub.add_parser("set-telegram")
    sub.add_parser("chats")
    sub.add_parser("show-token")
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
    if args.cmd == "show-token":
        return cmd_show_token()
    if args.cmd in ("set-chat", "set-group"):
        return cmd_set_chat("group" if args.cmd == "set-group" else "me", args.chat_id)
    if args.cmd == "status":
        return cmd_status(s)
    return cmd_run(s, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
