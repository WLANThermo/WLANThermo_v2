<?php
session_start();

// ##################################################################################
// Files einbinden ------------------------------------------------------------------
// ##################################################################################
require_once("../function.php");
session("../conf/WLANThermo.conf");

if(isset($_GET["telegram_token"]) && isset($_GET["telegram_getid"]) && $_GET["telegram_getid"] == "true") {
    $updates = json_decode(file_get_contents('https://api.telegram.org/bot' . $_GET["telegram_token"] .'/getUpdates', 'r'), True);
    $chats = [];
    if (isset($updates['ok']) && $updates['ok'] == True &&
        isset($updates['result'])) {
        foreach ($updates['result'] as $result) {
            if (isset($result['message']['text']) && $result['message']['text'] == "/start") {
                $chats[] = [
                'id'   => $result['message']['chat']['id'],
                'name' => $result['message']['chat']['first_name'] . ' ' . $result['message']['chat']['last_name']];
            }
        }
        header("Content-type: text/json");
        echo(json_encode($chats));
    }
}
?>