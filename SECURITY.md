# Segurança e privacidade do NEAD Avisos

## Encontrou um problema de segurança?

**Não abra uma Issue pública.** Use a aba **Security → Report a vulnerability** deste repositório
(relato privado). Responderemos o quanto antes e corrigiremos antes de qualquer divulgação.

## O que o programa faz (e o que nunca faz)

- **Somente leitura no Moodle.** O cliente só aceita uma lista fechada de funções de consulta
  (`READ_ONLY_FUNCTIONS` em `src/nead_avisos/moodle.py`); qualquer outra é recusada antes de sair do
  computador. Ele nunca envia tarefas, posta em fóruns, manda mensagens ou altera nada.
- **Sua senha não é guardada.** Ela é usada uma única vez para gerar a chave do app oficial do Moodle.
- **Cada pessoa usa o próprio login e o próprio robô do Telegram.** Ninguém precisa passar senha para ninguém.

## Onde ficam os dados

| Dado | No PC | Na nuvem (GitHub) |
|---|---|---|
| Chave do Moodle, token do robô | Gerenciador de Credenciais do Windows | Secrets do repositório (cifrados pelo GitHub) |
| Números do chat/grupo | `.env` (não vai para o GitHub) | Secrets |
| Estado (o que já foi avisado) | `data/state.json` **criptografado** | cache do Actions **criptografado** |
| Chave do estado | Gerenciador de Credenciais | Secret `NEAD_AVISOS_CHAVE_ESTADO` |

O estado guarda o **mínimo**: identificadores, datas e *hashes* (impressões digitais) dos textos para saber se
algo mudou. Comentários de professores, enunciados e mensagens **não** ficam guardados; só passam pelo Telegram.

## Sigilo das informações de alunos e professores

- **Grupo da turma recebe só o que é igual para todos** (atividades, avisos do professor, eventos, prazos).
  Mensagens, notas, comentários, pendências pessoais e notificações do Moodle **nunca** vão para o grupo — há
  uma trava no envio, coberta por teste, que impede isso mesmo se surgir um erro em outra parte do código.
- **Registros públicos sem dado pessoal.** Em repositório público, os registros do Actions podem ser lidos por
  qualquer pessoa. O programa só escreve neles contagens e tipos de aviso — nunca nomes, títulos ou textos —
  e os números do Telegram ficam em Secrets (ocultos nos registros).
- **Botões só para o Moodle.** Um link estranho numa notificação nunca vira botão (só `https` do servidor do Moodle).

## Proteções da cópia na nuvem

- Ações do GitHub fixadas por SHA e dependências Python com versões exatas (`constraints.txt`); o Dependabot
  avisa quando sair correção de segurança.
- O token automático de cada execução só lê o código e mexe no próprio Actions; o checkout não guarda credencial.
- O `.exe` é gerado pelo GitHub a partir do código público; cada versão traz o arquivo `.sha256` para conferir.
  No PowerShell: `Get-FileHash .\NEAD-Avisos.exe -Algorithm SHA256`.

## Se uma chave vazar

1. **Chave do Moodle:** Moodle → seu perfil → Preferências → **Chaves de segurança** → Redefinir. Depois rode
   `nead-avisos setup` e atualize o Secret `NEAD_AVISOS_MOODLE_TOKEN`.
2. **Token do robô:** Telegram → @BotFather → /mybots → seu robô → **Revoke current token**. Depois
   `nead-avisos set-telegram` e atualize o Secret `NEAD_AVISOS_TELEGRAM_TOKEN`.
3. **Token do cron-job.org:** apague-o em https://github.com/settings/personal-access-tokens e crie outro.

## Parar e apagar tudo

`nead-avisos apagar-tudo` apaga deste PC o estado, o registro, as chaves e a tarefa agendada, e mostra como
revogar as chaves. Na nuvem: apague o repositório e o agendamento no cron-job.org.
