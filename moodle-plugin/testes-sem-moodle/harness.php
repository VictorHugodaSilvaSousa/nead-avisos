<?php
// Testes do plugin message_neadavisos SEM um Moodle instalado: simula só as funções do Moodle que o plugin usa
// (configuração, preferências, banco, strings, curl) e roda o código real do plugin.
// Uso: php harness.php      (sai com código 1 se algum teste falhar)

define('MOODLE_INTERNAL', true);
define('MATURITY_BETA', 100);
define('MESSAGE_PERMITTED', 0x0004);
define('DEBUG_DEVELOPER', 32767);
$CFG = (object) ['wwwroot' => 'https://nead.ifb.edu.br', 'dirroot' => __DIR__ . '/stub', 'libdir' => __DIR__ . '/stub'];

// ------------------------------------------------------------------ simulação do Moodle
$CONFIG = [];
$PREFS = [];          // [userid][name] = value
$SENT = [];           // mensagens que o "Telegram" recebeu
$UPDATES = [];        // o que getUpdates devolve
$DEBUG = [];

function get_config($plugin, $name = null) { global $CONFIG; return $CONFIG[$plugin][$name] ?? false; }
function set_config($name, $value, $plugin = null) { global $CONFIG; $CONFIG[$plugin][$name] = $value; }
function get_user_preferences($name, $default = null, $userid = null) {
    global $PREFS; return $PREFS[$userid][$name] ?? $default; }
function set_user_preference($name, $value, $userid) { global $PREFS; $PREFS[$userid][$name] = (string) $value; }
function unset_user_preference($name, $userid) { global $PREFS; unset($PREFS[$userid][$name]); }
function s($text) { return htmlspecialchars((string) $text, ENT_QUOTES | ENT_HTML5, 'UTF-8'); }
function format_string($t) { return $t; }
function get_site() { return (object) ['fullname' => 'Moodle do NEAD <IFB>']; }
function fullname($u) { return trim(($u->firstname ?? '') . ' ' . ($u->lastname ?? '')); }
function debugging($msg, $level = 0) { global $DEBUG; $DEBUG[] = $msg; }
function mtrace($m) {}
function get_string($id, $component, $a = null) {
    static $strings = null;
    if ($strings === null) { $string = []; require(__DIR__ . '/../neadavisos/lang/pt_br/message_neadavisos.php'); $strings = $string; }
    if (!isset($strings[$id])) { throw new Exception("string ausente: $id"); }
    return str_replace('{$a}', (string) $a, $strings[$id]);
}
class core_text {
    static function strlen($s) { return mb_strlen($s); }
    static function substr($s, $a, $l = null) { return mb_substr($s, $a, $l); }
    static function strrpos($s, $n) { return mb_strrpos($s, $n); }
}
class html_writer {
    static function div($c, $cls = '') { return "<div class=\"$cls\">$c</div>"; }
    static function link($url, $text, $attrs = []) { return '<a href="' . s($url) . '">' . s($text) . '</a>'; }
    static function checkbox($name, $v, $checked, $label) { return "<input type=\"checkbox\" name=\"$name\">" . s($label); }
}
class message_output {}
class fake_db {
    function sql_like($field, $param, $cs = true) { return "$field LIKE $param"; }
    function get_records_select($table, $where, $params) {
        global $PREFS; $out = [];
        foreach ($PREFS as $uid => $prefs) {
            $v = $prefs[$params['name']] ?? null;
            if ($v !== null && fnmatch(str_replace('%', '*', $params['value']), $v)) {
                $out[] = (object) ['userid' => $uid, 'name' => $params['name'], 'value' => $v];
            }
        }
        return $out;
    }
    function delete_records_select($table, $where, $params) {
        global $PREFS;
        foreach ($PREFS as $uid => $prefs) {
            if ($uid != $params['userid'] && ($prefs[$params['name']] ?? null) === $params['value']) {
                unset($PREFS[$uid][$params['name']]);
            }
        }
    }
    function get_fieldset_select($table, $field, $where, $params) {
        global $PREFS; $out = [];
        foreach ($PREFS as $uid => $prefs) { if (($prefs[$params['name']] ?? null) === $params['value']) { $out[] = $uid; } }
        return $out;
    }
}
$DB = new fake_db();
// "curl" do Moodle: registra o que seria enviado ao Telegram, sem rede.
class curl {
    function setHeader($h) {}
    function get_errno() { return 0; }
    function post($url, $body, $opts = []) {
        global $SENT, $UPDATES;
        if (!preg_match('#^https://api\.telegram\.org/bot\d+:[A-Za-z0-9_-]+/(\w+)$#', $url, $m)) {
            throw new Exception("URL inesperada");
        }
        $params = json_decode($body, true);
        if ($m[1] === 'getUpdates') { return json_encode(['ok' => true, 'result' => $UPDATES]); }
        if ($m[1] === 'sendMessage') {
            if (($params['parse_mode'] ?? '') === 'HTML' && strpos($params['text'], '<quebrado>') !== false) {
                return json_encode(['ok' => false, 'description' => "Bad Request: can't parse entities"]);
            }
            $SENT[] = $params; return json_encode(['ok' => true]);
        }
        return json_encode(['ok' => false]);
    }
}
@mkdir(__DIR__ . '/stub/message/output', 0777, true);
file_put_contents(__DIR__ . '/stub/message/output/lib.php', '<?php');
file_put_contents(__DIR__ . '/stub/filelib.php', '<?php');

$base = __DIR__ . '/../neadavisos';
require($base . '/classes/telegram.php');
require($base . '/classes/linker.php');
require($base . '/classes/formatter.php');
require($base . '/message_output_neadavisos.php');

use message_neadavisos\formatter;
use message_neadavisos\linker;
use message_neadavisos\telegram;

// ------------------------------------------------------------------ testes
$fails = 0;
function check($name, $cond) { global $fails; echo ($cond ? "  OK    " : "  FALHA ") . $name . "\n"; if (!$cond) { $fails++; } }
function msg($chat, $text, $type = 'private') { static $id = 1; return ['update_id' => $id++, 'message' => ['chat' => ['id' => $chat, 'type' => $type], 'text' => $text]]; }

set_config('bottoken', '1234567:' . str_repeat('A', 35), 'message_neadavisos');
set_config('botusername', '@nead_avisos_bot', 'message_neadavisos');
$out = new message_output_neadavisos();
$USER = (object) ['id' => 9];         // no Moodle, $USER é sempre o usuário logado

echo "Configuração\n";
check('sistema configurado com token e nome do robô', $out->is_system_configured());
check('token em formato inválido é recusado', !telegram::valid_token('abc') && !telegram::valid_token('123:curto'));

echo "Ligar a conta (código de uso único)\n";
$url = linker::link_url(7);
check('link do robô leva o código', (bool) preg_match('#^https://t\.me/nead_avisos_bot\?start=([a-f0-9]{16})$#', $url, $m));
$code = $m[1];
check('mesmo código reaproveitado enquanto vale', linker::code_for(7) === $code);
$UPDATES = [msg(666, '/start'), msg(666, '/start 0000000000000000'), msg(-100, "/start $code", 'group'),
            msg(111, "/start $code")];
$SENT = [];
$changed = linker::process_updates();
check('só o chat com o código certo é ligado', $changed === 1 && linker::chat_of(7) === '111');
check('grupo com o código certo é ignorado', linker::chat_of(7) !== '-100');
check('código é apagado depois de usado', get_user_preferences(linker::PREF_CODE, null, 7) === null);
check('quem só mandou /start recebe instruções (não é ligado)', count(array_filter($SENT, fn($s) => $s['chat_id'] == 666)) >= 1);
check('mensagem de conexão escapa o nome do site', (bool) array_filter($SENT, fn($s) => strpos($s['text'], '&lt;IFB&gt;') !== false));
check('offset avança (mensagens não são relidas)', (int) get_config('message_neadavisos', 'updateoffset') > 0);

echo "Código vencido e reuso\n";
set_user_preference(linker::PREF_CODE, 'abcdefabcdefabcd|' . (time() - 10), 8);
check('código vencido é recusado', linker::user_for_code('abcdefabcdefabcd') === null);
check('código mal formado é recusado', linker::user_for_code("x' OR 1=1 --") === null);
$code9 = linker::code_for(9);
$UPDATES = [msg(111, $code9)];
linker::process_updates();
check('um chat fica ligado a uma única conta', linker::chat_of(9) === '111' && linker::chat_of(7) === null);

echo "Envio de notificações\n";
$SENT = [];
$user = (object) ['id' => 9, 'firstname' => 'Ana', 'lastname' => 'Souza', 'deleted' => 0, 'suspended' => 0];
$from = (object) ['id' => 5, 'firstname' => 'Prof.', 'lastname' => 'Josane'];
$out->send_message((object) ['userto' => $user, 'userfrom' => $from, 'notification' => 1,
    'subject' => 'Nota <script>x</script> 4 < 5 & "média"', 'smallmessage' => 'Sua nota: 9,0
---------------------------------------
Altere suas preferências de notificação', 'contexturl' => 'https://nead.ifb.edu.br/mod/assign/view.php?id=3']);
check('notificação chega ao chat ligado', count($SENT) === 1 && $SENT[0]['chat_id'] == '111');
check('HTML do assunto é removido e caracteres especiais escapados',
    strpos($SENT[0]['text'], '<script>') === false && strpos($SENT[0]['text'], '4 &lt; 5 &amp; &quot;média&quot;') !== false);
check('rodapé de preferências é removido', strpos($SENT[0]['text'], 'preferências') === false);
check('botão leva ao Moodle', ($SENT[0]['reply_markup']['inline_keyboard'][0][0]['url'] ?? '') === 'https://nead.ifb.edu.br/mod/assign/view.php?id=3');

$SENT = [];
$out->send_message((object) ['userto' => $user, 'userfrom' => $from, 'notification' => 1, 'subject' => 'Aviso',
    'smallmessage' => 'x', 'contexturl' => 'https://nead.ifb.edu.br.golpe.com/login']);
check('link de outro site não vira botão', count($SENT) === 1 && !isset($SENT[0]['reply_markup']));

$SENT = [];
$out->send_message((object) ['userto' => $user, 'userfrom' => $from, 'notification' => 0,
    'component' => 'moodle', 'name' => 'instantmessage', 'subject' => 'Mensagem', 'smallmessage' => 'Minha nota caiu, CPF 123']);
check('mensagem privada: por padrão o CONTEÚDO não vai ao Telegram', strpos($SENT[0]['text'], 'CPF') === false &&
    strpos($SENT[0]['text'], 'Nova mensagem de Prof. Josane') !== false);
set_config('showmessagecontent', 1, 'message_neadavisos');
$SENT = [];
$out->send_message((object) ['userto' => $user, 'userfrom' => $from, 'notification' => 0, 'subject' => 'M',
    'smallmessage' => 'Texto liberado pelo admin']);
check('com a opção do administrador, o conteúdo vai', strpos($SENT[0]['text'], 'Texto liberado') !== false);

$SENT = [];
$out->send_message((object) ['userto' => (object) ['id' => 77, 'deleted' => 0], 'notification' => 1, 'subject' => 'x']);
check('conta não ligada: nada é enviado (e a fila não trava)', count($SENT) === 0);
$out->send_message((object) ['userto' => (object) ['id' => 9, 'suspended' => 1], 'notification' => 1, 'subject' => 'x']);
check('conta suspensa: nada é enviado', count($SENT) === 0);

echo "Robustez\n";
$SENT = [];
(new telegram())->send('111', 'texto <quebrado>');
check('formatação recusada é reenviada como texto simples', count($SENT) === 1 && !isset($SENT[0]['parse_mode']));
$long = str_repeat("• <b>Item</b> <i>" . str_repeat('x', 90) . "</i>\n", 80);
$cut = telegram::cut($long);
check('texto longo é cortado sem deixar marcação aberta', mb_strlen($cut) <= telegram::LIMIT &&
    substr_count($cut, '<b>') === substr_count($cut, '</b>') && substr_count($cut, '<i>') === substr_count($cut, '</i>'));

echo "Desligar\n";
$UPDATES = [msg(111, '/parar')];
linker::process_updates();
check('/parar desliga a conta', linker::chat_of(9) === null);
$form = $out->config_form((object) ['neadavisos_chatid' => null]);
check('formulário mostra o botão de conexão', strpos($form, 't.me/nead_avisos_bot?start=') !== false);
$prefs = (object) [];
$out->load_data($prefs, 9);
check('load_data informa conta desligada', $prefs->neadavisos_chatid === null);

echo "\n" . ($fails ? "$fails FALHA(S)\n" : "TODOS OS TESTES PASSARAM\n");
exit($fails ? 1 : 0);
