# Guia do representante de turma

Como representante, você liga o **grupo da sua turma no Telegram** ao NEAD Avisos. A turma inteira passa a receber
os avisos gerais do Moodle **sem instalar nada e sem passar senha**: basta entrar no grupo.

## O que o grupo recebe (e o que nunca recebe)

| Recebe | Nunca recebe |
|---|---|
| Atividades e materiais novos | Suas notas e os comentários dos professores |
| Atividades alteradas pelo professor (nome, enunciado, arquivos) | Suas mensagens do Moodle |
| Avisos dos professores e respostas deles nos fóruns | As suas pendências e prazos perdidos |
| Prazos da semana, prazo alterado e prazo que vence hoje | Notificações pessoais do Moodle |
| Eventos da sala (aula síncrona etc.) | Postagens de colegas nos fóruns |

**Ritmo:** para o grupo não virar barulho, as novidades chegam em **resumos às 8h, 13h e 19h**, organizados por
disciplina. Só o urgente chega na hora: prazo que vence hoje, prazo alterado e evento de hoje.

## Como ligar (uns 10 minutos)

1. **Instale** colando no PowerShell:
   ```
   irm https://raw.githubusercontent.com/VictorHugodaSilvaSousa/nead-avisos/main/instalar.ps1 | iex
   ```
2. O assistente pede o **seu login do Moodle**. A senha não é guardada. Depois ele pede **o seu robô do Telegram**,
   criado no @BotFather: o assistente explica como criar.
3. Quando ele perguntar **"Você é representante e quer ligar o grupo da turma?"**, responda `s`:
   - adicione o seu robô ao grupo da turma;
   - envie no grupo a mensagem que aparece na tela, por exemplo `/vincular 3f9a12c4`.

   O código é de uso único, então ninguém mais consegue ligar outro grupo.
4. Escolha **onde rodar**:
   - **no PC:** só funciona com o PC ligado;
   - **na nuvem:** funciona com o PC desligado. Siga a seção "Rodar na nuvem" do README, incluindo o cron-job.org,
     para o grupo receber a cada 15 minutos.

**Uma pessoa por turma.** Se dois representantes ligarem o mesmo grupo, os avisos chegam em dobro.

## Boas práticas para o grupo

- Deixe **só administradores** podendo postar e use o grupo apenas para os avisos. Assim ninguém perde nada no meio
  de conversas.
- Fixe uma mensagem explicando o que é o grupo e o link para entrar.
- Os resumos são horários fixos. Se a turma preferir outros, ajuste `NEAD_AVISOS_GRUPO_HORARIOS`, por exemplo `9,18`.

## Mensagem pronta para convidar a turma

> 📢 Pessoal, criei um grupo no Telegram que avisa sozinho quando sai atividade nova, aviso de professor ou prazo
> chegando no Moodle, inclusive quando o professor muda uma data. Os avisos chegam em resumos às 8h, 13h e 19h, e o
> urgente na hora. Não precisa instalar nada nem passar senha, é só entrar: [link do grupo].
> Lá só vai o que é igual para todos; nada pessoal de ninguém.
