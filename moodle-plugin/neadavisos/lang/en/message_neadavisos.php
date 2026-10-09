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
 * English strings.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

$string['bottoken'] = 'Bot token';
$string['bottoken_desc'] = 'Token given by @BotFather. Keep it secret: anyone with it can send messages as the bot.';
$string['botusername'] = 'Bot username';
$string['botusername_desc'] = 'The bot username created with @BotFather (for example: nead_avisos_bot).';
$string['buttonopen'] = 'Open in Moodle';
$string['buttonreply'] = 'Reply in Moodle';
$string['linkbutton'] = 'Connect to Telegram';
$string['linked'] = 'Your account is connected to Telegram. The notifications you enable in this column arrive there.';
$string['linkexpires'] = 'The connection code is single-use and expires in 15 minutes. Then reload this page.';
$string['linkinstructions'] = 'Press the button, then START in Telegram. Your account is connected within a minute.';
$string['newmessagefrom'] = 'New message from {$a}';
$string['notconfigured'] = 'The Telegram bot has not been configured by the site administrator yet.';
$string['pluginname'] = 'Telegram (NEAD Avisos)';
$string['privacy:metadata:preference:chatid'] = 'The Telegram chat ID that receives your notifications.';
$string['privacy:metadata:preference:code'] = 'A single-use code (valid for 15 minutes) used to connect your Telegram.';
$string['privacy:metadata:telegram'] = 'Notifications you choose to receive on Telegram are sent to the Telegram service.';
$string['privacy:metadata:telegram:chatid'] = 'Your Telegram chat ID, to deliver the notification.';
$string['privacy:metadata:telegram:message'] = 'The notification text (private message content only if the administrator allows it).';
$string['readinmoodle'] = 'For privacy, the content stays in Moodle. Use the button to read it.';
$string['settingsintro'] = 'Sends the Moodle notifications that each user chooses to their own Telegram. Users connect their account in Preferences > Notification preferences, with a single-use code. Only the chat ID is stored.';
$string['showmessagecontent'] = 'Show private message content';
$string['showmessagecontent_desc'] = 'If disabled (recommended), Telegram only shows "New message from ..." and the text stays in Moodle.';
$string['someone'] = 'someone';
$string['tasklinkchats'] = 'Connect and disconnect Telegram accounts';
$string['telegramhowto'] = 'To connect, open Moodle > Preferences > Notification preferences and press "Connect to Telegram".';
$string['telegramlinked'] = '✅ Connected to {$a}! You will receive here the notifications you enable. To stop: /parar';
$string['telegramunlinked'] = 'Disconnected. You will no longer receive Moodle notifications here.';
$string['unlink'] = 'Disconnect Telegram';
