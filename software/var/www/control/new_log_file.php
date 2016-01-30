<?php
session_start(); //Session starten

//-------------------------------------------------------------------------------------------------------------------------------------
// Files einbinden ####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	$document_root = getenv('DOCUMENT_ROOT');
	$home = getenv('HOME');
	include("".$document_root."/header.php");
	include("".$document_root."/function.php");
	$inipath = ''.$document_root.'/conf/WLANThermo.conf';
	$message = "";

	if (!isset($_SESSION["current_temp"])) {
	$message .= "Variable - Config neu einlesen\n";
	session("./conf/WLANThermo.conf");
	}	
	
	$currentlogfilename = file_get_contents($_SESSION["current_temp"]);
	while (preg_match("/TEMPLOG/i", $currentlogfilename) != "1"){
		$currentlogfilename = file_get_contents($_SESSION["current_temp"]);
	}
	$currentlogfilename = explode(";",$currentlogfilename);
	$currentlogfilename = $currentlogfilename[18];
	//echo $currentlogfilename;
	
//-------------------------------------------------------------------------------------------------------------------------------------
// WLANThermo.conf einlesen ###########################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

if(file_exists($inipath)){
	if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
	$ini = getConfig($inipath, ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.
}else{
	echo "<h2>Die Konfigurationsdatei (".$inipath.") existiert nicht!</h2>";
	die();
}
	
if(isset($_POST["yes"])) { 
	echo "<div class=\"infofield\">";
		if ($_SESSION["plot_start"] == "True"){ // Prüfen ob der Plotdienst eingeschaltet ist
			if(file_exists("".$document_root."/tmp/temperaturkurve.png")){ //Überprüfen ob eine Plotgrafik existiert
				copy("".$document_root."/tmp/temperaturkurve.png","".$document_root."/thermoplot/$currentlogfilename.png"); // Plotgrafik kopieren
				echo "<h2>Aktuelle Plotgrafik wird gesichert...</h2>";
			}else{ 
				echo "<h2>Plotgrafik nicht vorhanden...</h2>";
			}
		}
		
		$ini['ToDo']['create_new_log'] = "True"; // Parameter für neues Logfile setzen
		write_ini($inipath, $ini);	// Schreiben der WLANThermo.conf

		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>Neues Logfile wird angelegt...</h2></body>";	

//-------------------------------------------------------------------------------------------------------------------------------------
// Zurück Button auswerten ############################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------	

}elseif(isset($_POST["back"])) {
	echo "<div class=\"infofield\">";
	 echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <p><h2>Verlassen der Seite ohne ein neues Logfile anzulegen!...</h2></p></body>";
	echo "</div>";
}else{

//-------------------------------------------------------------------------------------------------------------------------------------
// Formular ausgeben ##################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
	?>
<div id="new_log_file_site">
	<h1>NEUES&nbsp;&nbsp;LOGFILE&nbsp;&nbsp;ERSTELLEN</h1>
	<form action="new_log_file.php" method="post" >
		<br>
		<p><b>M&ouml;chten Sie ein neues Logfile erstellen?</b></p>			
			<table align="center" width="80%"><tr><td width="20%"></td>
				<td align="center"> <input type="submit" class=button_yes name="yes"  value="">
					<input type="submit" class=button_back name="back"  value=""> </td>
				<td width="20%"></td></tr>
			</table>
	</form>
</div>
<?php
}
include("".$document_root."/footer.php");
?>