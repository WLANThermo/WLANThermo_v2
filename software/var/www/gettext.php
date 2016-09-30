<?php
function get_available_languages() {
	$directory = "../lang";
	$dirHandle = dir($directory);
	$language = array();	
	exec("/usr/bin/locale -a",$output);	
	while (($f = $dirHandle->read()) != false) {
		if ($f != "." && $f != ".."){
			if (is_dir("".$directory."/".$f)){
				if (file_exists("".$directory."/".$f."/LC_MESSAGES/messages.mo")) {
					if (in_array("".$f.".utf8",$output)){
						$language[] = $f;
						echo $f;
					}				
				}
			}
		}
	}
	$dirHandle->close();
	//print_r ($language);
	return $language;
}

function set_locale($locale){
//setlocale(LC_ALL, 'de_DE.utf8');
//echo $_SESSION["locale"];
	if (isset($locale)){
		setlocale(LC_ALL, ''.$locale.'.utf8');		
	}else{
		setlocale(LC_ALL, 'de_DE.utf8');
	}
	//setlocale(LC_ALL, 'fr_FR.utf8');
	bindtextdomain("messages", "lang");
	// Domain auswählen
	textdomain("messages");
	// Die Übersetzung wird nun in ./locale/de_DE/LC_MESSAGES/meinePHPApp.mo gesucht
	// Ausgeben des Test-Textes
}
?>