<?php
//setlocale(LC_ALL, 'de_DE.utf8');
//echo $_SESSION["language"];
if (isset($_SESSION["language"])){
	setlocale(LC_ALL, ''.$_SESSION["language"].'.utf8');		
}else{
	setlocale(LC_ALL, 'de_DE.utf8');
}

//setlocale(LC_ALL, 'fr_FR.utf8');
bindtextdomain("messages", "lang");
// Domain auswählen
textdomain("messages");
// Die Übersetzung wird nun in ./locale/de_DE/LC_MESSAGES/meinePHPApp.mo gesucht
// Ausgeben des Test-Textes
?>