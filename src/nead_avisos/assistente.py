"""Assistente de configuração para quem não é da área técnica (abre ao dar dois cliques no NEAD-Avisos.exe).

Cada pessoa usa o PRÓPRIO login do Moodle e o PRÓPRIO bot do Telegram. Nada de ninguém passa por outra pessoa.
"""

from __future__ import annotations

import getpass
import subprocess
import sys
import time
import webbrowser

from .config import PROJECT_ROOT, Settings, get_secret, set_secret
from .moodle import AuthError, MoodleError, get_token
from .telegram import Telegram

TEMPLATE_REPO = "https://github.com/VictorHugodaSilvaSousa/nead-avisos"


def _title(text: str) -> None:
    print("\n" + "=" * 70 + f"\n  {text}\n" + "=" * 70)


def _wait(msg: str = "Quando terminar, aperte ENTER para continuar...") -> None:
    input(f"\n{msg}")


def _yes(question: str) -> bool:
    return input(f"{question} [s/n]: ").strip().lower().startswith("s")


def _clipboard() -> str:
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True,
                         timeout=15)
    return (out.stdout or "").strip()


def _to_clipboard(text: str) -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"], input=text, text=True,
                   timeout=15)


def _set_env(key: str, value: str) -> None:
    path = PROJECT_ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    name = f"NEAD_AVISOS_{key}"
    lines = [ln for ln in lines if not ln.lstrip("# ").startswith(f"{name}=")] + [f"{name}={value}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------- passos
def passo_moodle() -> bool:
    _title("Passo 1 de 4 — Seu login do Moodle do NEAD")
    print("Use o MESMO usuário e senha que você digita em nead.ifb.edu.br.\n"
          "A senha é usada uma única vez para gerar uma chave de acesso e NÃO é guardada.\n"
          "O programa só LÊ o Moodle: nunca envia, marca ou altera nada.")
    for _ in range(3):
        user = input("\nUsuário do Moodle: ").strip()
        print("Senha (não aparece enquanto digita; para colar use o BOTÃO DIREITO do mouse):")
        password = getpass.getpass("> ").strip()
        try:
            token = get_token("https://nead.ifb.edu.br", user, password)
        except AuthError:
            print("O Moodle recusou esse usuário/senha. Tente de novo.")
            continue
        except MoodleError as exc:
            print(f"Não consegui falar com o Moodle agora ({exc}). Verifique a internet.")
            return False
        set_secret("moodle_token", token)
        _set_env("USERNAME", user)
        print("✔ Login confirmado. Chave de acesso guardada com segurança no seu Windows.")
        return True
    return False


def passo_bot() -> Telegram | None:
    _title("Passo 2 de 4 — Seu robô do Telegram")
    print("Você vai criar um robô SÓ SEU (leva 1 minuto):\n"
          "  1. Vai abrir o @BotFather no Telegram. Envie: /newbot\n"
          "  2. Escolha um nome (ex.: Meus Avisos NEAD) e um usuário terminado em bot (ex.: avisos_fulano_bot)\n"
          "  3. O BotFather responde com um TOKEN (algo como 123456:AAH...). COPIE o token (Ctrl+C).\n"
          "  ⚠ Não cole o token em nenhum lugar: o assistente lê sozinho da área de transferência.")
    webbrowser.open("https://t.me/BotFather")
    for _ in range(5):
        _wait("Depois de COPIAR o token, aperte ENTER...")
        token = _clipboard()
        if ":" in token and len(token) >= 30 and " " not in token:
            bot = Telegram(token).me()
            if bot:
                set_secret("telegram_token", token)
                _to_clipboard("")                       # limpa o token da área de transferência
                print(f"✔ Robô @{bot['username']} configurado.")
                return Telegram(token)
            print("O Telegram não aceitou esse token. Copie de novo a linha inteira do token.")
        else:
            print("Não encontrei um token copiado. No BotFather, selecione o token e aperte Ctrl+C.")
    return None


def passo_chat(tg: Telegram) -> bool:
    _title("Passo 3 de 4 — Ligar o robô ao seu Telegram")
    import secrets
    bot = tg.me()
    # Código de uso único: só o chat que enviar ESTE código vira o seu chat. Se outra pessoa falar com o robô
    # ao mesmo tempo, ela é ignorada (não passa a receber os seus avisos).
    code = secrets.token_hex(4)
    print(f"Vai abrir o seu robô @{bot.get('username')}. Aperte INICIAR (o código {code} vai junto, sozinho).\n"
          f"Se o botão não aparecer, envie para o robô a mensagem:  {code}")
    webbrowser.open(f"https://t.me/{bot.get('username')}?start={code}")
    print("Aguardando sua mensagem para o robô", end="", flush=True)
    for _ in range(60):
        chat = tg.pairing_chat(code)
        if chat:
            _set_env("TELEGRAM_CHAT_ID", str(chat["id"]))
            tg.send_text(chat["id"], "✅ Robô ligado! Você vai receber aqui os avisos do Moodle do NEAD.")
            print(f"\n✔ Pronto, {chat.get('first_name', '')}! Confira a mensagem de teste no Telegram.")
            return True
        print(".", end="", flush=True)
        time.sleep(3)
    print(f"\nNão recebi o código. Abra o robô no Telegram, envie a mensagem {code} e rode o assistente de novo.")
    return False


def instalar_no_pc() -> None:
    """Tarefa agendada a cada 15 min, rodando SEM janela (lançador VBScript)."""
    vbs = PROJECT_ROOT / "rodar-sem-janela.vbs"
    if getattr(sys, "frozen", False):
        cmd = f'""{sys.executable}"" run'
    else:
        cmd = f'""{sys.executable}"" -m nead_avisos run'
    vbs.write_text(f'CreateObject("WScript.Shell").Run "{cmd}", 0, True\r\n', encoding="utf-8")
    ps = (f"$a = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '\"{vbs}\"';"
          "$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15);"
          "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew "
          "-ExecutionTimeLimit (New-TimeSpan -Minutes 20) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
          "Register-ScheduledTask -TaskName 'NEAD-Avisos' -Action $a -Trigger $t -Settings $s "
          "-Description 'NEAD Avisos: novidades do Moodle no Telegram' -Force | Out-Null")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], check=True, timeout=60)
    print("✔ Pronto: o NEAD Avisos vai conferir o Moodle a cada 15 minutos enquanto o PC estiver ligado.")


def instalar_na_nuvem() -> None:
    _title("Rodar na nuvem (funciona com o PC desligado) — GitHub, grátis")
    print("Você precisa de uma conta no GitHub (github.com). Vamos criar a SUA cópia do NEAD Avisos:\n"
          "  1. Vai abrir a página do modelo. Clique em 'Use this template' > 'Create a new repository'.\n"
          "  2. Dê um nome (ex.: nead-avisos), deixe PUBLIC e clique em 'Create repository'.")
    webbrowser.open(f"{TEMPLATE_REPO}/generate")
    repo = ""
    while "github.com/" not in repo:
        repo = input("\nCole aqui o endereço do SEU repositório (ex.: https://github.com/seu-usuario/nead-avisos): ")
        repo = repo.strip().removesuffix(".git").rstrip("/")
    s = Settings.load()
    from .state import state_key
    # Tudo como Secret: Secrets ficam ocultos nos registros (que são públicos em repositório público).
    items = [("secrets", "NEAD_AVISOS_MOODLE_TOKEN", get_secret("moodle_token")),
             ("secrets", "NEAD_AVISOS_TELEGRAM_TOKEN", get_secret("telegram_token")),
             ("secrets", "NEAD_AVISOS_TELEGRAM_CHAT_ID", str(s.telegram_chat_id)),
             ("secrets", "NEAD_AVISOS_CHAVE_ESTADO", state_key().decode())]
    print("\nAgora vamos cadastrar 4 itens SECRETOS. Para cada um, vai abrir a página certa e o VALOR já vai estar\n"
          "copiado (ele não aparece na tela):")
    for kind, name, value in items:
        _to_clipboard(value)
        webbrowser.open(f"{repo}/settings/{kind}/actions/new")
        print(f"\n  • Em 'Name' digite exatamente:  {name}\n"
              f"  • Em '{'Secret' if kind == 'secrets' else 'Value'}' clique e cole (Ctrl+V) e depois em "
              f"'{'Add secret' if kind == 'secrets' else 'Add variable'}'.")
        _wait()
    _to_clipboard("")
    webbrowser.open(f"{repo}/actions")
    print("\nPor fim, na aba Actions que abriu: clique em 'I understand my workflows, go ahead and enable them',\n"
          "depois em 'NEAD Avisos' > 'Run workflow' > 'Run workflow'. Em ~1 minuto chega no seu Telegram\n"
          "'NEAD Avisos ativado na nuvem'.\n\n"
          "IMPORTANTE: o agendamento grátis do GitHub atrasa horas. Para receber a cada 15 minutos, siga a seção\n"
          "'A cada 15 minutos de verdade' do README (cron-job.org, grátis, ~10 minutos de configuração).")


PRIVACY = """Antes de começar, o que o NEAD Avisos faz com os seus dados:
  • Usa o SEU login do Moodle só para LER: atividades, avisos, prazos, notas, mensagens e notificações.
    Ele nunca envia, posta, responde ou altera nada no Moodle.
  • Sua senha é usada uma vez para gerar a chave do app do Moodle e NÃO é guardada. A chave fica no
    Gerenciador de Credenciais do Windows (ou nos Secrets do SEU GitHub, se escolher a nuvem).
  • Os avisos vão só para o SEU robô do Telegram. Nada é enviado ao autor do programa nem a terceiros.
  • O que fica guardado (o que já foi avisado) é criptografado; mensagens e comentários não ficam guardados.
  • Para parar e apagar tudo: rode 'nead-avisos apagar-tudo'. Detalhes no arquivo SECURITY.md."""


def main() -> int:
    _title("NEAD Avisos — configuração")
    print("Avisos do Moodle do NEAD no seu Telegram (celular e PC): novas atividades, avisos dos professores,\n"
          "prazos chegando, prazos perdidos e suas pendências. Leva uns 5 minutos.\n")
    print(PRIVACY)
    if not _yes("\nEntendi e quero continuar?"):
        print("Tudo bem, nada foi configurado.")
        return 0
    if not passo_moodle():
        return 2
    tg = passo_bot()
    if not tg or not passo_chat(tg):
        return 2
    _title("Passo 4 de 4 — Onde ele vai rodar?")
    print("  1 = Neste PC (mais simples; só funciona com o PC ligado)\n"
          "  2 = Na nuvem pelo GitHub (funciona com o PC desligado; precisa de conta no GitHub)")
    choice = ""
    while choice not in ("1", "2"):
        choice = input("Escolha 1 ou 2: ").strip()
    if choice == "1":
        instalar_no_pc()
    else:
        instalar_na_nuvem()
    print("\nTudo pronto! Você pode fechar esta janela.")
    _wait("Aperte ENTER para sair...")
    return 0
