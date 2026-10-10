# NEAD Avisos

Avisos do Moodle do NEAD/IFB no **Telegram**, que chegam no celular e no PC ao mesmo tempo.

> Criado por **Victor Hugo da Silva Sousa**, estudante e representante da turma TDS (NEAD/IFB).

**Instalar (Windows), um comando no PowerShell:**
```
irm https://raw.githubusercontent.com/VictorHugodaSilvaSousa/nead-avisos/main/instalar.ps1 | iex
```
Ele baixa a versão mais recente, **confere o SHA-256**, instala só para o seu usuário (sem administrador), cria os
atalhos e abre o assistente. Para remover: `& "$env:LOCALAPPDATA\NEAD-Avisos\instalar.ps1" -Desinstalar`.

O que ele avisa:

- 📝 nova atividade ou material publicado pelo professor, com o link direto;
- ✏️ **atividade alterada pelo professor**, dizendo o que mudou: nome, enunciado, arquivo novo, atualizado ou
  removido, e disponibilidade;
- 📅 prazo alterado (antes → depois) e ⚙️ configuração alterada (forma de envio, nota, tentativas...);
- 📢 novo aviso no fórum de **Avisos** e aviso editado pelo professor;
- 💬 tópico novo e **resposta do professor** em qualquer fórum. Postagens de colegas vão só para o seu chat;
- 📆 novo evento da sala (aula síncrona, encontro...), evento alterado e lembrete no dia;
- ⏰ lembretes de prazo: 3 dias antes, 1 dia antes e no dia; 🗓 resumo diário com os prazos da semana;
- 📊 **nota lançada ou alterada** e 💬 comentário do professor (só no seu chat);
- 🔴 o que **você** ainda não entregou, ⚠️ prazo perdido e 📋 resumo diário das suas pendências (só no seu chat);
- ✉️ **toda mensagem recebida** no Moodle, uma por uma (conversas individuais e em grupo), e 🔔 as notificações
  do Moodle sem repetir o que já foi avisado (só no seu chat);
- 🔎 **verificação do dia**: confere tudo o que o Moodle registrou para você nas últimas 24 h contra o que
  chegou no Telegram, e o que faltar sai na hora (só no seu chat).

**Grupo da turma (opcional, ligado pelo representante: veja o [guia do representante](docs/representantes.md)):**
recebe só o que é igual para todos (atividades e alterações, avisos, respostas do professor, eventos e prazos).
Nunca recebe notas, notificações, mensagens ou entregas pessoais. Para não virar barulho, o grupo recebe **resumos por
disciplina às 8h, 13h e 19h**; só o urgente (prazo que vence hoje, prazo alterado, evento de hoje) chega na hora.
O seu chat pessoal recebe tudo na hora.

**Como chegam:** cada aviso diz quanto tempo falta para o prazo ("faltam 22 h") e tem um botão que leva direto
ao lugar certo ("📝 Abrir e entregar", "💬 Responder no Moodle", "📊 Ver nota"...). As notificações do Moodle chegam
traduzidas: "✏️ Alterado pelo professor", "🆕 Novo na sala", "📝 Feedback do professor", "✅ Envio confirmado"
(esta sempre sem som). O lembrete da turma não se repete no seu chat quando você já recebe o lembrete pessoal do
mesmo prazo.

Quando uma versão nova traz tipos de aviso novos, a primeira execução só registra o estado atual. Assim não
chega uma enxurrada de "novidades" antigas.

**Segurança e privacidade** (detalhes em [SECURITY.md](SECURITY.md)):
- **Somente leitura:** o programa só consulta o Moodle e nunca envia, marca ou altera nada lá.
- Cada pessoa usa o **próprio login**. A senha é usada uma única vez, para gerar a chave de acesso do app oficial
  do Moodle, e **não é guardada**. A chave fica no Gerenciador de Credenciais do Windows ou, na nuvem, nos
  *Secrets* do GitHub. Ela dá à conta o mesmo acesso do app oficial: **não a compartilhe com ninguém**.
- O que o programa guarda (o que já foi avisado) fica **criptografado**, e textos como comentários de professores
  e mensagens não ficam guardados: só passam pelo seu Telegram.
- **Informações de alunos e professores ficam no seu chat.** O grupo da turma nunca recebe mensagens, notas,
  comentários ou pendências pessoais, e os registros da nuvem não mostram nomes nem textos.
- Ele acompanha só as salas em que você é **aluno** e que estão em andamento. Salas de mediação e de semestres
  encerrados ficam de fora.
- Para parar e apagar tudo deste PC: `nead-avisos apagar-tudo`.

**Pergunte ao robô quando quiser** (só você, no chat privado; a resposta chega em até 15 minutos):
`/pendencias` (o que você ainda não entregou), `/prazos` (prazos da turma nos próximos 7 dias) e `/ajuda`.

**Menos avisos no seu chat:** `/silenciar TIPO` desliga um tipo só no seu chat (o grupo da turma não muda), `/ativar
TIPO` religa e `/silenciados` mostra o que está desligado. Tipos: `confirmacoes`, `notificacoes`, `atividades`,
`prazos`, `perdidos`, `avisos`, `foruns`, `notas`, `mensagens`, `eventos` e `resumos`. Por exemplo,
`/silenciar confirmacoes` para de mandar "Envio confirmado".

## Para o NEAD: plugin do Moodle (todos os alunos, sem instalar nada)

A pasta [`moodle-plugin/neadavisos`](moodle-plugin/neadavisos) é um **plugin de notificação para o Moodle**. Com ele
instalado pela administração, o Telegram vira um canal de notificação do próprio Moodle, ao lado do e-mail. Cada aluno
conecta a conta em *Preferências → Preferências de notificação* e recebe **na hora** o que escolher, sem robô próprio,
sem GitHub e sem senha. O `.zip` pronto para instalar está em cada versão (`message_neadavisos.zip`), e o guia para o
administrador, com os detalhes de segurança e LGPD, está no [README do plugin](moodle-plugin/neadavisos/README.md).

## Para colegas: sem instalar nada

O jeito mais fácil é o comando de instalação lá do começo. Se preferir baixar à mão:

1. Baixe o **NEAD-Avisos.exe** na página de versões:
   https://github.com/VictorHugodaSilvaSousa/nead-avisos/releases/latest
2. Dê **dois cliques** no arquivo. Se o Windows mostrar "O Windows protegeu o computador", clique em
   **Mais informações → Executar assim mesmo**. O aviso aparece porque o programa é novo e não é assinado.
3. Siga o assistente, que leva uns 5 minutos:
   - **seu login** do Moodle: a senha não é guardada;
   - **seu robô** do Telegram, criado no @BotFather: o assistente lê o token sozinho;
   - **onde rodar:** neste PC (a cada 15 min, sem janela) ou na nuvem pelo GitHub (funciona com o PC desligado).

Cada pessoa usa **o próprio login e o próprio robô**: ninguém precisa passar senha para ninguém.
O **grupo da turma** é alimentado só pelo representante. Se cada colega ligasse o grupo, os avisos sairiam repetidos.

## 1. Instalar a partir do código (Windows)

Um comando, na pasta do projeto: instala o Python 3.12 se faltar (winget), cria o `.venv` com as dependências nas
versões testadas e roda os testes:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\instalar-codigo.ps1
```
Ou, à mão:

```powershell
cd nead-avisos
python -m venv .venv
.venv\Scripts\pip install -e .
copy .env.example .env          # preencha NEAD_AVISOS_USERNAME (o mesmo usuário da tela de login do NEAD)
.venv\Scripts\nead-avisos setup # pede a senha uma vez (cole com o BOTÃO DIREITO do mouse)
```

## 2. Telegram

1. No Telegram, fale com o **@BotFather**, envie `/newbot`, escolha um nome (ex.: "NEAD Avisos") e copie o token.
2. Rode `.venv\Scripts\nead-avisos set-telegram` e cole o token com o **botão direito**.
3. Abra o seu bot e envie **/start**.
4. Grupo da turma (opcional): adicione o bot ao grupo e envie no grupo `/start@NOME_DO_SEU_BOT`.
5. Rode `.venv\Scripts\nead-avisos chats` e copie os IDs para o `.env`:
   - `NEAD_AVISOS_TELEGRAM_CHAT_ID` = o número marcado como PRIVADO;
   - `NEAD_AVISOS_TELEGRAM_GROUP_ID` = o número marcado como GRUPO (começa com `-`).
6. Teste:
   - `nead-avisos run --dry-run` mostra o que seria enviado, sem enviar nada;
   - `nead-avisos run` é a primeira execução de verdade: só registra o estado atual e avisa "NEAD Avisos ativado". Daí em diante, só chegam novidades.

## 3a. Rodar no PC (a cada 15 min, com o PC ligado)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows-schedule.ps1
```

O log fica em `data\avisos.log`. Para remover a tarefa: `scripts\uninstall-windows-schedule.ps1`.

## 3b. Rodar na nuvem (com o PC DESLIGADO): GitHub Actions, grátis

1. Crie uma conta em https://github.com e um repositório **público** com esta pasta. O código não tem
   segredos, e em repositório público as execuções são ilimitadas. Os arquivos `.env` e `data/` não sobem
   (estão no `.gitignore`).
2. No repositório, abra **Settings → Secrets and variables → Actions → Secrets** e cadastre, como **Secrets**
   (nunca como Variables: em repositório público, Variables aparecem nos registros):
   - `NEAD_AVISOS_MOODLE_TOKEN`: rode `nead-avisos show-token` no PC (o valor é copiado, não aparece na tela);
   - `NEAD_AVISOS_TELEGRAM_TOKEN`: o token do seu robô;
   - `NEAD_AVISOS_TELEGRAM_CHAT_ID` e, se for o representante, `NEAD_AVISOS_TELEGRAM_GROUP_ID`;
   - `NEAD_AVISOS_CHAVE_ESTADO`: rode `nead-avisos chave-nuvem` no PC. Ela criptografa o estado guardado no cache.
3. Na aba **Actions**, habilite os workflows e clique em **NEAD Avisos → Run workflow** para testar.
4. **A cada 15 minutos de verdade:** o agendamento grátis do GitHub atrasa muito e, na prática, roda só a cada
   3 a 7 horas. Para os avisos chegarem na hora, use o https://cron-job.org (grátis) para disparar o workflow:
   - crie um token em https://github.com/settings/personal-access-tokens/new com *Only select repositories*
     (este repositório) e **Actions: Read and write**, nada mais;
   - no cron-job.org, crie um cronjob *Every 15 minutes* com
     - URL `https://api.github.com/repos/SEU_USUARIO/SEU_REPOSITORIO/actions/workflows/avisos.yml/dispatches`;
     - método `POST`;
     - cabeçalhos `Authorization: Bearer SEU_TOKEN`, `Accept: application/vnd.github+json`,
       `X-GitHub-Api-Version: 2022-11-28` e `Content-Type: application/json`;
     - corpo `{"ref":"main"}`.

     O "Test run" deve responder **204**.
5. **Desative a tarefa do PC** (passo 3a). Com as duas ligadas, os avisos chegam em dobro.

## Configurações (`.env` ou Variables do GitHub)

| Variável | Padrão | Para quê |
|---|---|---|
| `NEAD_AVISOS_LEMBRETES_DIAS` | `3,1,0` | dias de antecedência dos lembretes de prazo |
| `NEAD_AVISOS_RESUMO_HORA` | `7` | hora do resumo diário dos prazos da semana |
| `NEAD_AVISOS_GRUPO_HORARIOS` | `8,13,19` | horários dos resumos do grupo da turma (`0` = cada novidade na hora) |
| `NEAD_AVISOS_SILENCIO` | `22-7` | avisos chegam **sem som** nesse horário; mensagens e prazos urgentes tocam (`0` desliga) |
| `NEAD_AVISOS_INCLUIR_SALAS` / `EXCLUIR_SALAS` | — | ids de salas para forçar a inclusão ou a exclusão |
| `NEAD_AVISOS_SALAS_DO_GRUPO` | turma atual + Coordenação | quais salas vão para o grupo da turma |

Comandos: `setup`, `set-telegram`, `chats`, `status` (salas acompanhadas e destino), `run [--dry-run]`.

## Autoria e licença

**NEAD Avisos** foi idealizado e desenvolvido por **Victor Hugo da Silva Sousa** (TDS — NEAD/IFB), 2026.

Copyright (C) 2026 Victor Hugo da Silva Sousa.

Este programa é software livre, sob a **GNU General Public License, versão 3 ou posterior** (GPL-3.0-or-later).
O texto completo está em [LICENSE](LICENSE). Na prática:
- qualquer pessoa ou instituição pode usar, estudar, copiar e modificar;
- quem distribuir o programa, modificado ou não, **deve manter o aviso de autoria** e distribuir o código sob a
  mesma licença;
- não há garantia de qualquer tipo.

O plugin do Moodle (`moodle-plugin/neadavisos`) segue a mesma licença, como o próprio Moodle.
