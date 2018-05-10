<?php
session_start(); //Session starten

//-------------------------------------------------------------------------------------------------------------------------------------
// Files einbinden ####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	$document_root = getenv('DOCUMENT_ROOT');
	include("".$document_root."/header.php");
	require_once("".$document_root."/function.php");
	$inipath = ''.$document_root.'/conf/WLANThermo.conf';
	$message = "";
	$currentlogfilename = getCurrentLogFileName();
	//echo $currentlogfilename;
//-------------------------------------------------------------------------------------------------------------------------------------
// WLANThermo.conf einlesen ###########################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

if(file_exists($inipath)){
	if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
	$ini = getConfig($inipath, ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.
}else{
	echo "<h2>".gettext("The configuration file")." (".$inipath.") ".gettext("does not exist")."!</h2>";
	die();
}
	
if(isset($_POST["yes"])) { 
	echo "<div class=\"infofield\">";
		if ($_SESSION["plot_start"] == "True"){ // Prüfen ob der Plotdienst eingeschaltet ist
			if(file_exists("".$document_root."/tmp/temperaturkurve.png")){ //Überprüfen ob eine Plotgrafik existiert
				copy("".$document_root."/tmp/temperaturkurve.png","".$document_root."/thermoplot/$currentlogfilename.png"); // Plotgrafik kopieren
				echo "<h2>".gettext("Saving current plot image")."...</h2>";
			}else{ 
				echo "<h2>".gettext("Plot image is unavilable")."...</h2>";
			}
		}
		
		$ini['ToDo']['create_new_log'] = "True"; // Parameter für neues Logfile setzen
		write_ini($inipath, $ini);	// Schreiben der WLANThermo.conf

		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>".gettext("New log file created")."...</h2></body>";	

//-------------------------------------------------------------------------------------------------------------------------------------
// Zurück Button auswerten ############################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------	

}elseif(isset($_POST["back"])) {
	echo "<div class=\"infofield\">";
	 echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <p><h2>".gettext("No new log file has been created")."!...</h2></p></body>";
	echo "</div>";
}else{

//-------------------------------------------------------------------------------------------------------------------------------------
// Formular ausgeben ##################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
	?>
<div id="new_log_file_site">
	<h1><?php echo gettext("Create New Log File");?></h1>
	<form action="new_log_file.php" method="post" >
		<br>
		<p><b><?php echo gettext("Are you sure you want to create a new log file?");?></b></p>			
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
