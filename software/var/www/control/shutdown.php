<?php
session_start(); //Session starten

//-------------------------------------------------------------------------------------------------------------------------------------
// Files einbinden ####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	include("../header.php");
	include("../function.php");
	$inipath = '../conf/WLANThermo.conf';
	
//-------------------------------------------------------------------------------------------------------------------------------------
// WLANThermo.conf einlesen ###########################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
	$ini = getConfig("../conf/WLANThermo.conf", ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.

//-------------------------------------------------------------------------------------------------------------------------------------
// String in Array Speichern (raspi_shutdown) #########################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

if(isset($_POST["shutdown"])) { 	
		$ini['ToDo']['raspi_shutdown'] = "True";
		// ----------------------------------------------------------------------------------------------------------------------------
		// Schreiben der WLANThermo.conf ##############################################################################################
		// ----------------------------------------------------------------------------------------------------------------------------

		write_ini($inipath, $ini);
	echo "<div class=\"infofield\">";
		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='about:blank'\"> </head> <body> <h2>RaspberryPi wird heruntergefahren...</h2></body>";	
	echo "</div>";
//-------------------------------------------------------------------------------------------------------------------------------------
// Zurück Button auswerten ############################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------	
}elseif(isset($_POST["reboot"])) {
			$ini['ToDo']['raspi_reboot'] = "True";
		// ----------------------------------------------------------------------------------------------------------------------------
		// Schreiben der WLANThermo.conf ##############################################################################################
		// ----------------------------------------------------------------------------------------------------------------------------

		write_ini($inipath, $ini);
		exec("/usr/bin/touch /var/www/tmp/reboot",$output);
	echo "<div class=\"infofield\">";
		
		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>RaspberryPi wird neu gestartet...</h2></body>";	
	echo "</div>";

}elseif(isset($_POST["back"])) {
	echo "<div class=\"infofield\">";
	 echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>Verlassen der Seite ohne neu start des RaspberryPi!...</h2></body>";
	echo "</div>";
}elseif($_GET["id"] == "shutdown"){

//-------------------------------------------------------------------------------------------------------------------------------------
// Formular ausgeben ##################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
	?>

<div id="shutdown">
	<h1>RASPBERRY&nbsp;PI&nbsp;&nbsp;HERUNTERFAHREN</h1>
	<form action="shutdown.php" method="post" >
		<br><p><b>M&ouml;chten Sie den RaspberryPi herunterfahren?</b></p>								
			<table align="center" width="80%"><tr><td width="20%"></td>
				<td align="center"> <input type="submit" class=button_yes name="shutdown"  value="">
					<input type="submit" class=button_back name="back"  value=""> </td>
				<td width="20%"></td></tr>
			</table>
	</form>
</div>
<?php
}elseif($_GET["id"] == "reboot"){
?>
<div id="shutdown">
	<h1>RASPBERRY&nbsp;PI&nbsp;&nbsp;NEU STARTEN</h1>
	<form action="shutdown.php" method="post" >
		<br><p><b>M&ouml;chten Sie den RaspberryPi neu starten?</b></p>								
			<table align="center" width="80%"><tr><td width="20%"></td>
				<td align="center"> <input type="submit" class=button_yes name="reboot"  value="">
					<input type="submit" class=button_back name="back"  value=""> </td>
				<td width="20%"></td></tr>
			</table>
	</form>
</div>
<?php
}
include("../footer.php");
?>