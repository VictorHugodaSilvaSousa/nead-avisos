<?php
// This file is part of Moodle - https://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <https://www.gnu.org/licenses/>.

/**
 * Textos em português do Brasil.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$string['bottoken'] = 'Token do robô';
$string['bottoken_desc'] = 'Token entregue pelo @BotFather. Mantenha em segredo: quem tiver o token pode mandar mensagens como o robô.';
$string['botusername'] = 'Nome do robô';
$string['botusername_desc'] = 'Nome do robô criado no @BotFather (por exemplo: nead_avisos_bot).';
$string['buttonopen'] = 'Abrir no Moodle';
$string['buttonreply'] = 'Responder no Moodle';
$string['linkbutton'] = 'Conectar ao Telegram';
$string['linked'] = 'Sua conta está conectada ao Telegram. As notificações que você ligar nesta coluna chegam lá.';
$string['linkexpires'] = 'O código de conexão é de uso único e vale 15 minutos. Depois disso, recarregue esta página.';
$string['linkinstructions'] = 'Aperte o botão e depois INICIAR no Telegram. Em até 1 minuto sua conta fica conectada.';
$string['newmessagefrom'] = 'Nova mensagem de {$a}';
$string['notconfigured'] = 'O robô do Telegram ainda não foi configurado pela administração do Moodle.';
$string['pluginname'] = 'Telegram (NEAD Avisos)';
$string['privacy:metadata:preference:chatid'] = 'O número do chat do Telegram que recebe as suas notificações.';
$string['privacy:metadata:preference:code'] = 'Código de uso único (válido por 15 minutos) usado para conectar o seu Telegram.';
$string['privacy:metadata:telegram'] = 'As notificações que você escolhe receber no Telegram são enviadas ao serviço do Telegram.';
$string['privacy:metadata:telegram:chatid'] = 'O número do seu chat do Telegram, para entregar a notificação.';
$string['privacy:metadata:telegram:message'] = 'O texto da notificação (conteúdo de mensagens privadas só se a administração permitir).';
$string['readinmoodle'] = 'Por privacidade, o conteúdo fica no Moodle. Use o botão para ler.';
$string['settingsintro'] = 'Envia ao Telegram de cada pessoa as notificações do Moodle que ela escolher. Cada um conecta a própria conta em Preferências > Preferências de notificação, com um código de uso único. Só o número do chat é guardado.';
$string['showmessagecontent'] = 'Mostrar o conteúdo das mensagens privadas';
$string['showmessagecontent_desc'] = 'Desligado (recomendado): o Telegram mostra só "Nova mensagem de ..." e o texto fica no Moodle.';
$string['someone'] = 'alguém';
$string['tasklinkchats'] = 'Conectar e desconectar contas do Telegram';
$string['telegramhowto'] = 'Para conectar, abra o Moodle > Preferências > Preferências de notificação e aperte "Conectar ao Telegram".';
$string['telegramlinked'] = '✅ Conectado ao {$a}! Você vai receber aqui as notificações que ligar. Para parar: /parar';
$string['telegramunlinked'] = 'Desconectado. Você não vai mais receber notificações do Moodle aqui.';
$string['unlink'] = 'Desconectar o Telegram';
