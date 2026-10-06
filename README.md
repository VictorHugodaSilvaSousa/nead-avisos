# NEAD Avisos

Avisos do Moodle do NEAD/IFB no **Telegram**, que chegam no celular e no PC ao mesmo tempo:

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
- 🔔 notificações e ✉️ mensagens do Moodle (só no seu chat).

**Grupo da turma (opcional):** recebe só o que é igual para todos (atividades e alterações, avisos, respostas
do professor, eventos e prazos). Nunca recebe notas, notificações, mensagens ou entregas pessoais.

Quando uma versão nova traz tipos de aviso novos, a primeira execução só registra o estado atual. Assim não
chega uma enxurrada de "novidades" antigas.

**Segurança:**
- **Somente leitura:** o programa só consulta o Moodle e nunca envia, marca ou altera nada lá.
- Cada pessoa usa o **próprio login**. A senha é usada uma única vez, para gerar a chave de acesso do app oficial do Moodle, e **não é guardada**.
- A chave fica no Gerenciador de Credenciais do Windows ou, na nuvem, nos *Secrets* do GitHub.
- Ele acompanha só as salas em que você é **aluno** e que estão em andamento. Salas de mediação e de semestres encerrados ficam de fora.

## Para colegas: sem instalar nada

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
2. No repositório, abra **Settings → Secrets and variables → Actions**:
   - **Secrets:** `NEAD_AVISOS_MOODLE_TOKEN` e `NEAD_AVISOS_TELEGRAM_TOKEN`. Para ver a chave do Moodle,
     rode `nead-avisos show-token` no PC.
   - **Variables:** `NEAD_AVISOS_TELEGRAM_CHAT_ID` e, se quiser, `NEAD_AVISOS_TELEGRAM_GROUP_ID`.
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
| `NEAD_AVISOS_INCLUIR_SALAS` / `EXCLUIR_SALAS` | — | ids de salas para forçar a inclusão ou a exclusão |
| `NEAD_AVISOS_SALAS_DO_GRUPO` | turma atual + Coordenação | quais salas vão para o grupo da turma |

Comandos: `setup`, `set-telegram`, `chats`, `status` (salas acompanhadas e destino), `run [--dry-run]`.
