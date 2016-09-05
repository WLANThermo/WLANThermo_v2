<?php
	session_start();
//-------------------------------------------------------------------------------------------------------------------------------------
// Files einbinden ####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	include("header.php");
	include("function.php");
		
//-------------------------------------------------------------------------------------------------------------------------------------
// Verzeichnis mit den Logfiles #######################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

$directory_csv = './thermolog/';
$directory_png = './thermoplot/';

//-------------------------------------------------------------------------------------------------------------------------------------
// Kontrollieren ob Symlink existiert, ansonst erstellen ##############################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

if (!is_link("./thermolog")) {	//Überprüfen ob Symlink existiert
	$output = shell_exec('ln -s /var/log/WLAN_Thermo /var/www/thermolog'); 	//Symlink erstellen
	echo "<pre>$output</pre>";												//Symlink erstellen	
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../thermolog.php'\"> </head> <body> <h2>Symlink wird erstellt...</h2></body>";
} 

//-------------------------------------------------------------------------------------------------------------------------------------
// Auswertung des Löschen Buttons #####################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
if(isset($_POST['submit'])) { 

	if (isset($_POST) && count($_POST) > 0 ) {	// Alle $_POST Variablen in einer schleife Überprüfen
		echo "<ul>";
		foreach($_POST as $key => $value) {

			$csv_file = "".$directory_csv."".$key.".csv";
			$png_file = "".$directory_png."".$key.".png";
										
			if (file_exists($csv_file)) {	//Überprüfen ob csv Datei vorhanden ist
				unlink($csv_file);			//Löschen der csv Datei
				//echo "löschen csv";
			}
			if (file_exists($png_file)) {	//Überprüfen ob png Datei vorhanden ist
				unlink($png_file);			//Löschen der png Datei
				//echo "löschen png";
			}					
		}
	}  
	echo "</div>";
	echo "<div class=\"infofield\">";
	echo "<head> <meta http-equiv=\"refresh\" content=\"1;URL='../thermolog.php'\"> </head> <body> <h2>Files werden gel&ouml;scht...</h2></body>";
	echo "</div>";
	
}else{
?>
	<form action="thermolog.php" method="post"><!-- Sich selbst aufrufen beim löschen -->
	<div id="thermolog">
<?php

//------------------------------------------------------------------------------------------------------------------------------------- 
// Ausgabe der Tabellen (in einer Schleife): ##########################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
	
	echo '<h1>Thermolog Ordner</h1>';
	
//-------------------------------------------------------------------------------------------------------------------------------------
// Tabellenkopf und fuß ###############################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
?>
	<br /> 
	<table>
		<thead>
			<tr>
				<th>Dateiname</th>
				<th>D/L</th>
				<th>Plot</th>
				<th>Dateigr&ouml;&szlig;e</th>
				<th>letzte &Auml;nderung</th>
				<th>L&ouml;schen</th>
			</tr>
		</thead>
		<tfoot>
			<tr>
				<th></th>
				<th></th>
				<th></th>
				<th></th>
				<th></th>
				<th><input type="submit" class=button_delete name="submit"  value=""></th>
			</tr>
		</tfoot>
		<tbody>
<?php
//------------------------------------------------------------------------------------------------------------------------------------- 
// Verzeichnis auslesen und Dateien ausgeben ##########################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
		$readFiles = getLogfiles();
		//echo nl2br(print_r($readFiles,true));
		foreach($readFiles as $key => $file_name) {
		?>
			<tr>		
				<td><div class="<?php if ($readFiles[$key]["editable"] == "False"){ echo "no_edit";}else{ echo "edit";}?>" id="<?php echo $readFiles[$key]["name"]; ?>"><?php echo "".substr($readFiles[$key]["name"], 0, -4)."";?></div></td>
				<td><a href="<?php echo $readFiles[$key]["logfile"]; ?>"><img src="../images/icons16x16/download.png" alt="Download" title="Download"></a></td>
				<td><?php if(!empty($readFiles[$key]["plot"])){ echo '<a class="fancybox" href="'.$readFiles[$key]["plot"].'" data-fancybox-type="image"><img src="../images/icons16x16/chart.png" alt="Plot ansehen" title="Plot ansehen"></a> '; } ?></td>
				<td><?php echo $readFiles[$key]["filesize"]; ?></td>
				<td><?php echo ''.date( 'd.m.Y H:i:s', $key ).''; ?></td>
				<td><?php if ($readFiles[$key]["editable"] == "True"){ echo '<input type="checkbox" name="'.substr($readFiles[$key]["name"], 0, -4).'" value="True" >'; } ?> </td>
			</tr>
			
		<?php
		} ?>
		</tbody>
	</table>
	</div>
	</form>
<?php
}
// ------------------------------------------------------------------------------------------------------------------------------------
include("footer.php");
?>