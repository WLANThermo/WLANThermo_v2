<?php
session_start(); //Session starten

//-------------------------------------------------------------------------------------------------------------------------------------
// Files einbinden ####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	include("../header.php");
	require_once("../function.php");
	$inipath = '../conf/WLANThermo.conf';
	
	
if(isset($_POST["shutdown"])) {		
	// --------------------------------------------------------------------------------------------------------------------------------
	// Schreiben der WLANThermo.conf ##################################################################################################
	// --------------------------------------------------------------------------------------------------------------------------------
	if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
	$ini = getConfig("../conf/WLANThermo.conf", ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.
	$ini['ToDo']['raspi_shutdown'] = "True";
	write_ini($inipath, $ini);
	echo "<div class=\"infofield\">";
		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='about:blank'\"> </head> <body> <h2>".gettext("RaspberryPi is shutting down")."...</h2></body>";	
	echo "</div>";

}elseif(isset($_POST["back"])) {
	//---------------------------------------------------------------------------------------------------------------------------------
	// Zurück Button auswerten ########################################################################################################
	//---------------------------------------------------------------------------------------------------------------------------------	
	echo "<div class=\"infofield\">";
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>".gettext("Cancelled shutdown")."...</h2></body>";
	echo "</div>";
}else{
	//---------------------------------------------------------------------------------------------------------------------------------
	// Formular ausgeben ##############################################################################################################
	//---------------------------------------------------------------------------------------------------------------------------------
?>

<div id="shutdown">
	<h1><?php echo gettext("RASPBERRY PI SHUTDOWN");?></h1>
	<form action="shutdown.php" method="post" >
		<br><p><b><?php echo gettext("Do you want to shutdown the RaspberryPi?");?></b></p>								
			<table align="center" width="80%">
				<tr>
					<td width="20%"></td>
					<td align="center"> <input type="submit" class=button_yes name="shutdown"  value=""><input type="submit" class=button_back name="back"  value=""> </td>
					<td width="20%"></td>
				</tr>
			</table>
	</form>
</div>
<?php
}
include("../footer.php");
?>
