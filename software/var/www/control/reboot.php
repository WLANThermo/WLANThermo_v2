<?php
session_start(); //Session starten

//-------------------------------------------------------------------------------------------------------------------------------------
// Files einbinden ####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	include("../header.php");
	include("../function.php");
	$inipath = '../conf/WLANThermo.conf';
	
//-------------------------------------------------------------------------------------------------------------------------------------
// String in Array Speichern (raspi_shutdown) #########################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

if(isset($_POST["reboot"])) { 		
	
	// ----------------------------------------------------------------------------------------------------------------------------
	// Schreiben der WLANThermo.conf ##############################################################################################
	// ----------------------------------------------------------------------------------------------------------------------------
	if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
	$ini = getConfig("../conf/WLANThermo.conf", ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.
	$ini['ToDo']['raspi_reboot'] = "True";
	write_ini($inipath, $ini);
	exec("/usr/bin/touch /var/www/tmp/reboot",$output);
	
	echo "<div class=\"infofield\">";	
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>".gettext("Restarting RaspberryPi")."...</h2></body>";	
	echo "</div>";

}elseif(isset($_POST["back"])) {
	echo "<div class=\"infofield\">";
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>".gettext("Cancelling reboot")."...</h2></body>";
	echo "</div>";
}else{
?>
<div id="shutdown">
	<h1><?php echo gettext("RASPBERRY PI REBOOT");?></h1>
	<form action="reboot.php" method="post" >
		<br><p><b><?php echo gettext("Do you want to reboot the RaspberryPi?");?></b></p>								
			<table align="center" width="80%">
				<tr>
					<td width="20%"></td>
					<td align="center"> <input type="submit" class=button_yes name="reboot"  value=""><input type="submit" class=button_back name="back"  value=""> </td>
					<td width="20%"></td>
				</tr>
			</table>
	</form>
</div>
<?php
}
include("../footer.php");
?>