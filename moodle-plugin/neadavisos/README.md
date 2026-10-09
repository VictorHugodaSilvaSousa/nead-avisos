# Telegram (NEAD Avisos) — plugin de notificação para o Moodle

Plugin do tipo **message output** (`message_neadavisos`). Ele acrescenta o Telegram como canal de notificação
do Moodle, ao lado de "E-mail" e "Notificações da web".

**Para quem é:** administradores do Moodle (por exemplo, a equipe de TI/NEAD do IFB).

## O que muda para os alunos

1. Em **Preferências → Preferências de notificação**, aparece a coluna **Telegram (NEAD Avisos)**.
2. O aluno clica em **Conectar ao Telegram**. O Telegram abre e ele aperta **INICIAR**. Em até 1 minuto a conta
   está ligada.
3. Daí em diante, **tudo o que o Moodle já notifica** (avisos do fórum, tarefas, notas e comentários, lembretes de
   prazo, mudanças de conteúdo, mensagens) chega no Telegram **na hora**. Cada pessoa escolhe o que quer receber.
4. Para parar, basta desligar em Preferências ou mandar `/parar` ao robô.

Ninguém precisa instalar nada nem informar senha, e não há atraso de horário.

## Instalação (administrador)

1. **Crie o robô** no Telegram com o **@BotFather** (`/newbot`). Anote o nome do robô (ex.: `nead_avisos_bot`) e o
   **token**.
2. **Instale o plugin** de uma destas formas:
   - *Administração do site → Plugins → Instalar plugins*, enviando o arquivo `message_neadavisos.zip`; ou
   - copiando a pasta `neadavisos` para `message/output/neadavisos` no servidor.

   Depois, acesse *Administração do site → Notificações* para concluir a instalação.
3. **Configure** em *Administração do site → Plugins → Saídas de mensagem → Telegram (NEAD Avisos)*:
   - token do robô e nome do robô;
   - "Mostrar o conteúdo das mensagens privadas": deixe **desligado** (recomendado).
4. Em *Administração do site → Mensagens → Configurações de notificação*, deixe o canal **habilitado** e, se quiser,
   defina para quais tipos de notificação ele vem ligado por padrão.
5. Confira se o **cron** do Moodle roda a cada minuto. A tarefa *Conectar e desconectar contas do Telegram* precisa
   dele.

Requisitos: Moodle 4.1 ou superior; o servidor precisa acessar `https://api.telegram.org` (porta 443).

## Segurança e privacidade (LGPD)

- **Guarda só o número do chat** do Telegram de quem se conectou, como preferência do usuário, e o código
  temporário de conexão. Não guarda nome, telefone ou mensagens do Telegram.
- **Conexão por código de uso único:** o código é aleatório, vale 15 minutos e é apagado ao ser usado. Só chats
  **privados** são aceitos, nunca grupos, e um chat fica ligado a uma única conta.
- **Mensagens privadas:** por padrão, o Telegram mostra só "Nova mensagem de Fulano" e o conteúdo fica no Moodle.
- **Botões** só levam ao próprio Moodle, por `https`. Links de outros sites nunca viram botão.
- **Sem endereço público novo:** o plugin consulta o Telegram (`getUpdates`); não abre webhook no Moodle.
- **Token do robô:** fica nas configurações do administrador, em campo de senha. Nunca vai para logs nem mensagens
  de erro.
- **Respeita as regras de rede do Moodle** (hosts e portas bloqueados pelo administrador).
- **Registro de privacidade completo** (*Política de privacidade e dados*): declara as preferências guardadas e o
  envio ao Telegram, e exporta os dados do usuário.
- **Contas suspensas ou excluídas** não recebem nada.

O texto das notificações escolhidas passa pelos servidores do Telegram. Isso fica informado no registro de
privacidade e na tela de preferências.

## Testes

- **PHPUnit, padrão do Moodle:** `vendor/bin/phpunit --testsuite message_neadavisos_testsuite`, ou
  `--filter message_neadavisos`.
- **Sem Moodle** (simulação, usada no GitHub a cada mudança): `php ../testes-sem-moodle/harness.php`.

## Licença

GNU GPL v3 ou posterior, como o Moodle.
