<?php
	session_start();
	
$tmp_dir = '/var/www/tmp/display/current.temp';
if (!file_exists($tmp_dir)) {
	exit(0);
}
	
//-------------------------------------------------------------------------------------------------------------------------------------
// Files einbinden ####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	$beginn = microtime(true);
	require_once("function.php");
	require_once("gettext.php");
	$esound = "0"; // Variable für Soundalarmierung;
	$esound_ = "0";
	$message = "\n";
	$timestamp = "";
	$pit_time_stamp = "";
	$pit_val = "";
	$pit_set = "";
	$log_dateformat = 'd.m.y H:i:s';

//	$pit_file = '.'.$_SESSION["pitmaster"].'';
//	if (file_exists($pit_file)) {
//		include('.'.$_SESSION["pitmaster"].'');
//	}

//-------------------------------------------------------------------------------------------------------------------------------------
// SESSION-Variablen überprüfen #######################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	checkSession();
	
//-------------------------------------------------------------------------------------------------------------------------------------
// Sprache setzen #####################################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
	
if (isset($_SESSION["locale"])){	
	set_locale($_SESSION["locale"]);
}else{
	set_locale("de_DE.utf8");
}

//-------------------------------------------------------------------------------------------------------------------------------------
// Flag für Änderungen in der config ##################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

if (file_exists(dirname(__FILE__).'/tmp/flag')) {
	$message .= "Flag gesetzt - Config neu einlesen\n";
	session("./conf/WLANThermo.conf");
} else {
	$message .= "Flag nicht gesetzt \n";
}

if (file_exists(dirname(__FILE__).'/tmp/update')) {
	$message .= "Update - update läuft gerade\n";
	session("./conf/WLANThermo.conf");
	if (file_exists(dirname(__FILE__).'/tmp/update.log')) {
		$lines = file('tmp/update.log');
		$last_line = $lines[count($lines)-1];
		echo '<div id="info_site"><p><b>'.gettext('WLANThermo update').':</b> '.$last_line.'</p></div>';
	}else{
		echo '<div id="info_site"><b>'.gettext('The update is currently being installed').'...</b></div>';
	}
	$_SESSION["to_update"] = 'True';
	echo '<script>$(function() { showLoading();});</script>';
	exit;
} 
if (file_exists(dirname(__FILE__).'/tmp/reboot')) { 
	$message .= "Reboot - Raspberry wird neu gestartet\n";
	echo '<div id="info_site"><b>'.gettext('Restarting RaspberryPi').'...</b></div>';
	echo '<script>$(function() { showLoading();});</script>';
	exit;
}
if (file_exists(dirname(__FILE__).'/tmp/nextionupdate')) { 
	$message .= "Nextion - Update verfügbar\n";
	$nextionupdate = "NX3224T028.tft";
	$_SESSION["nextionupdate"] = $nextionupdate;
	echo '<script>$(function() { showUpdate();});</script>';
	if (file_exists(dirname(__FILE__).'/tmp/nextionupdatelog')) {
		$message .= "Nextion - Update wird gestartet\n";
		$lines = file('tmp/nextionupdatelog');
		$last_line = $lines[count($lines)-1];
		echo '<script>$(function() { showLoading();});</script>';
		echo '<div id="info_site"><p><b>'.gettext('NEXTION Display update').':</b> '.$last_line.'</p></div>';
		exit;
	}
}else{
	if (isset($_SESSION["nextionupdate"])){
		unset($_SESSION["nextionupdate"]);
		echo '<script>$(function() { hideUpdate();});</script>';
	}
}
if (isset($_SESSION["to_update"])){
	if ($_SESSION["to_update"] == "True"){
                /* Obsolete, now done by wlt_2_updateconfig.py
		if (file_exists(dirname(__FILE__).'/conf/WLANThermo.conf') AND file_exists(dirname(__FILE__).'/conf/WLANThermo.conf.old')) {
			restoreConfig("./conf/WLANThermo.conf","./conf/WLANThermo.conf.old");
		}
                */
		session("./conf/WLANThermo.conf");
		echo '<script>$(function() { hideUpdate();});</script>';
		echo '<script>$(function() { hideLoading();});</script>';
		$_SESSION["updateAvailable"] == "False";
		$_SESSION["webGUIversion"] = $_SESSION["newversion"];
		unset($_SESSION["to_update"]);
	}
}
	echo '<script>$(function() { hideLoading();});</script>';
	
	if ($_SESSION["temp_unit"] == 'celsius') {
		$temp_unit_short = '&#176;C';
	} elseif ($_SESSION["temp_unit"] == 'fahrenheit') {
		$temp_unit_short = '&#176;F';
	}
	
	//-------------------------------------------------------------------------------------------------------------------------------------
	// Temperaturwerte einlesen ###########################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

		$currenttemp = file_get_contents($_SESSION["current_temp"]);
		while (preg_match("/TEMPLOG/i", $currenttemp) != "1"){
			$currenttemp = file_get_contents($_SESSION["current_temp"]);
		}
		$temp = explode(";",$currenttemp);
		$time_stamp = DateTime::createFromFormat($log_dateformat, $temp[0]);
		for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
			${"temp_$i"} = floatval($temp[$i + 1]);
		}
		$_SESSION["currentlogfilename"] = $temp[2 * $_SESSION["channel_count"] + 2];
		for ($i = 0; $i < $_SESSION["pitmaster_count"]; $i++){
			$pitmaster_str = $i == 0 ? '' : strval($i +1);
			$pit_file = $_SESSION["pitmaster" . $pitmaster_str];
			if (file_exists($pit_file)) {
				$currentpit = file_get_contents($_SESSION["pitmaster" . $pitmaster_str]);
				$pits = explode(";",$currentpit);
				${'pit' . $pitmaster_str . '_time_stamp'} = DateTime::createFromFormat($log_dateformat, $pits[0]);
				${'pit' . $pitmaster_str . '_set'} = floatval($pits[1]);
				${'pit' . $pitmaster_str . '_val'} = floatval($pits[3]);
			}
		}

	//-------------------------------------------------------------------------------------------------------------------------------------
	// Anzeige Letzte Messung #############################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------
	$first = true;
	for ($pit = 0; $pit < $_SESSION["pitmaster_count"]; $pit++){
		$pitmaster_str = $pit == 0 ? '' : strval($pit +1);
		if ($_SESSION["pit" . $pitmaster_str . "_on"] == "True") {
			if ($first == true) {
				echo '<div class="last_regulation_view">';
				$first = false;
			}
			?>
			<img src="../images/icons16x16/pitmaster.png" alt=""> <img src="../images/icons16x16/number-<?php echo $pit + 1;?>.png" alt="">
			<?php
			if (${'pit' . $pitmaster_str . '_time_stamp'} instanceof DateTime) {
				echo gettext("Last regulation on");?> <b><?php echo IntlDateFormatter::formatObject(${'pit' . $pitmaster_str . '_time_stamp'}, array(IntlDateFormatter::SHORT, IntlDateFormatter::MEDIUM),$_SESSION["locale"]); ?></b><br />
			<?php
			}
		}
	}
	if ($first != true) {
		echo '</div>';
	} ?>
	<div class="last_measure_view"><?php echo gettext("Last measurement on");?> <b><?php echo IntlDateFormatter::formatObject($time_stamp, array(IntlDateFormatter::SHORT, IntlDateFormatter::MEDIUM),$_SESSION["locale"]); ?></b>
	<?php if($_SESSION["showcpulast"] == "True"){
	echo "<br>";
	$cpuload = new CPULoad();
	$cpuload->get_load();
	$CPULOAD = round($cpuload->load["cpu"],1);
	echo gettext("CPU utilization").": <b>".$CPULOAD."% / ".get_cputemp(). $temp_unit_short;"</b>";
	}
	?>
	</div>						 
	<br>
	<div class="clear"></div>

	<!-- ----------------------------------------------------------------------------------------------------------------------------------
	// Session in Array Speichern (sensoren)(plotter farben) etc. #########################################################################
	//--------------------------------------------------------------------------------------------------------------------------------- -->

	<?php
	for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
		$color_ch[] = $_SESSION["color_ch".$i];
		$temp_min[] = $_SESSION["temp_min".$i];  
		$temp_max[] = $_SESSION["temp_max".$i];
		$channel_name[] = $_SESSION["ch_name".$i];
		$alert[] = $_SESSION["alert".$i];
		$ch_show[] = $_SESSION["ch_show".$i];
	}
		
	//-------------------------------------------------------------------------------------------------------------------------------------
	// Variablen für den Plot #############################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------
	$plot = "plot ";
	for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
		$a = $i + 2 ;
		$chp[$i] = "'/var/log/WLAN_Thermo/TEMPLOG.csv' every ::1 using 1:$a with lines lw 2 lc rgb \\\"$color_ch[$i]\\\" t '$channel_name[$i]'  axes x1y2";
	}	
			
	//-------------------------------------------------------------------------------------------------------------------------------------
	// Ausgabe der Temperaturen ###########################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

		for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
			if((${"temp_$i"} != "") AND ($ch_show[$i] == "True")){
				if (${"temp_$i"} <= $temp_min[$i]) {
					$temperature_indicator_color = "temperature_indicator_blue";
					if($alert[$i] == "True") { 
						$esound = "1"; 
						$esound_ = "1";
					}
				} elseif(${"temp_$i"} >= $temp_max[$i]) {
					$temperature_indicator_color = "temperature_indicator_red";
					if($alert[$i] == "True") { 
						$esound = "1"; 
						$esound_ = "1";
					}
				} else {
					$temperature_indicator_color = "temperature_indicator"; 
					$esound_ = "0";
				}
				if	($plot !== "plot "){
					$plot .= ", ";}
					$plot .= "$chp[$i]";
				?>
					<div class="channel_view">
						<div class="channel_name"><?php echo htmlentities($channel_name[$i], ENT_QUOTES, "UTF-8"); ?></div>
						<div class="<?php echo $temperature_indicator_color;?>"><?php printf('%.1f%s', ${"temp_$i"}, $temp_unit_short);?></div>
						<div class="tempmm">Temp min <b><?php echo $temp_min[$i]; echo $temp_unit_short;?></b> / max <b><?php echo $temp_max[$i]; echo $temp_unit_short;?></b></div>
						<div class="headicon"><font color="<?php echo to_css_color($color_ch[$i]);?>">#<?php echo $i;?></font></div>
						<div class="webalert"><?php 
							if ($_SESSION["websoundalert"] == "True" && $esound_ == "1"){ 
								echo "<td><a href=\"#\" id=\"webalert_false\" class=\"webalert_false\" ><img src=\"../images/icons32x32/speaker.png\" border=\"0\" alt=\"Alarm\" title=\"Alarm\"></a></td>\n"; 
							}elseif($_SESSION["websoundalert"] == "False" && $esound_ == "1"){ 
								echo "<td><a href=\"#\" id=\"webalert_true\" class=\"webalert_true\" ><img src=\"../images/icons32x32/speaker_mute.png\" border=\"0\" alt=\"Alarm\" title=\"Alarm\"></a></td>\n"; 
							}?>
						</div>
						<?php
						for ($pit = 0; $pit < $_SESSION["pitmaster_count"]; $pit++){
							$pitmaster_str = $pit == 0 ? '' : strval($pit +1);
							if ($_SESSION["pit" . $pitmaster_str . "_ch"] == $i && $_SESSION["pit" . $pitmaster_str . "_on"] == "True") {
						?>
							<div class="headicon_left"><img src="../images/icons16x16/pitmaster.png" alt=""> <img src="../images/icons16x16/number-<?php echo $pit + 1;?>.png" alt=""></div>
							<div class="pitmaster_left"> <?php printf('%.1f%%',${'pit' . $pitmaster_str . '_val'}); ?> / <?php printf('%.1f%s',${'pit' . $pitmaster_str . '_set'}, $temp_unit_short); ?></div>
							<?php }
							}
						?>
					</div>
				<?php
			} 
		}

	//-------------------------------------------------------------------------------------------------------------------------------------
	// Plot erzeugen ######################################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------	
	
	if ($_SESSION["plot_start"] == "True"){
		$plot_setting = getPlotConfig($plot,$_SESSION['temp_unit']);
		if (is_dir("/var/www/tmp")){
			$message .= "Verzeichnis 'tmp' vorhanden! \n";
			$plotdateiname = '/var/www/tmp/temperaturkurve.png';
			if(file_exists("".$plotdateiname."")){
				$timestamp = filemtime($plotdateiname);
				$message .= "Aktueller Timestamp: \"".time()."\". \n";
				$message .= "Timestamp letzte Änderung der ".$plotdateiname.":\"".$timestamp."\". \n";
			}else{
				$timestamp = "0";
			}
			if (time()-$timestamp >= 9){
				if(file_exists("/var/www/tmp/temperaturkurve_view.png") AND (filesize("/var/www/tmp/temperaturkurve_view.png") > 0)){
					copy("/var/www/tmp/temperaturkurve_view.png","/var/www/tmp/temperaturkurve.png"); // Plotgrafik kopieren
					$message .= "temperaturkurve_view.jpg wird nach temperaturkurve.jpg kopiert. \n";
				}
				$cmd = "ps aux|grep gnuplot|grep -v grep| awk '{print $2}'";
				$message .="Cmd: ".$cmd." \n";
				exec($cmd, $plot_ret);
				if (isset($plot_ret[0])){
					$message .=" PID: ".$plot_ret[0]." \n";
				}
				if (empty($plot_ret)){
					exec("echo \"".$plot_setting."\" | /usr/bin/gnuplot > /var/www/tmp/error.txt &",$output);
					$message .= "Temperaturkurve.png wird erstellt. \n";
					//echo "".$plot_setting."".$plot."";
				}
			}	
		}	
	}

	//-------------------------------------------------------------------------------------------------------------------------------------
	// WebcamBild erzeugen ################################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------	
		
	if ($_SESSION["webcam_start"] == "True"){ // Überprüfen ob Webcam Aktiviert ist
		if (is_dir("/var/www/tmp")){ // Überprüfen ob das Verzeichnis "tmp" existiert
			$message .= "Verzeichnis 'tmp' vorhanden! \n";
			if(!file_exists("/var/www/tmp/webcam.jpg")){	
				copy("/var/www/images/webcam_fail.jpg","/var/www/tmp/webcam.jpg"); // Webcamgrafik kopieren
				$message .= "Keine webcam.jpg vorhanden! Kopiere dummy file. \n";
			}		
			$webcamdateiname = '/var/www/tmp/webcam.jpg';
			$timestamp = filemtime($webcamdateiname);
			$message .= "Aktueller Timestamp: \"".time()."\". \n";
			$message .= "Timestamp letzte Änderung der ".$webcamdateiname.":\"".$timestamp."\". \n";
			if (time()-$timestamp >= 9){
				if(file_exists("/var/www/tmp/webcam_view.jpg") AND (filesize("/var/www/tmp/webcam_view.jpg") > 0)){
					copy("/var/www/tmp/webcam_view.jpg","/var/www/tmp/webcam.jpg"); // Webcamgrafik kopieren
					$message .= "webcam_view.jpg wird nach webcam.jpg kopiert. \n";
				}
				$webcam_size = explode("x", $_SESSION["webcam_size"]);
				exec("sudo /usr/bin/raspi_webcam.sh W webcam_view.jpg ".$webcam_size[0]." ".$webcam_size[1]." '".$_SESSION["webcam_name"]."' > /dev/null &",$output);
				$message .= "webcam_view.jpg wird erstellt. \n";
			}
		}
	}

	//-------------------------------------------------------------------------------------------------------------------------------------
	// RaspicamBild erzeugen ##############################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------	
		
	if ($_SESSION["raspicam_start"] == "True"){ // Überprüfen ob Webcam Aktiviert ist
		if (is_dir("/var/www/tmp")){ // Überprüfen ob das Verzeichnis "tmp" existiert
			$message .= "Verzeichnis 'tmp' vorhanden! \n";
			if(!file_exists("/var/www/tmp/raspicam.jpg")){	
				copy("/var/www/images/webcam_fail.jpg","/var/www/tmp/raspicam.jpg"); // Webcamgrafik kopieren
				$message .= "Keine raspicam.jpg vorhanden! Kopiere dummy file. \n";
			}		
			$raspicamdateiname = '/var/www/tmp/raspicam.jpg';
			$timestamp = filemtime($raspicamdateiname);
			$message .= "Aktueller Timestamp: \"".time()."\". \n";
			$message .= "Timestamp letzte Änderung der ".$raspicamdateiname.":\"".$timestamp."\". \n";
			if (time()-$timestamp >= 9){
				if(file_exists("/var/www/tmp/raspicam_view.jpg") AND (filesize("/var/www/tmp/raspicam_view.jpg") > 0)){
					copy("/var/www/tmp/raspicam_view.jpg","/var/www/tmp/raspicam.jpg"); // Webcamgrafik kopieren
					$message .= "raspicam_view.jpg wird nach raspicam.jpg kopiert. \n";
				}
				$raspicam_size = explode("x", $_SESSION["raspicam_size"]);
				exec("sudo /usr/bin/raspi_webcam.sh R raspicam_view.jpg ".$raspicam_size[0]." ".$raspicam_size[1]." '".$_SESSION["raspicam_name"]."' ".$_SESSION["raspicam_exposure"]." > /dev/null &",$output);
				$message .= "raspicam_view.jpg wird erstellt. \n";
			}
		}
	}
		
	//-------------------------------------------------------------------------------------------------------------------------------------
	// Flag überprüfen ####################################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

	$flagdateiname = '/var/www/tmp/flag';
	if (file_exists($flagdateiname)) {
		$timestamp = filemtime($flagdateiname);
			$message .= "Aktueller Timestamp: \"".time()."\". \n";
			$message .= "Timestamp letzte Änderung der ".$flagdateiname.":\"".$timestamp."\". \n";
					
		if (time()-$timestamp >= 20){
			unlink(''.$flagdateiname.'');
			$message .= "Flag wird gelöscht. \n";
		}
	}

	//-------------------------------------------------------------------------------------------------------------------------------------
	// Alarmierung bei über/unterschreitung ###############################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

	if	($esound == "1")
		{
			if ($_SESSION["websoundalert"] == "True"){
				echo 	'<div id="sound">';
				echo    	'<audio autoplay>';
				echo			'<source src="buzzer.mp3" type="audio/mpeg" />';
				echo			'<source src="buzzer.ogg" type="audio/ogg" />';
				echo			'<source src="buzzer.m4a" type="audio/x-aac" />';
				echo		'</audio>';
				echo	'</div>';
			}
	}else{ $_SESSION["websoundalert"] = "True";}

//-------------------------------------------------------------------------------------------------------------------------------------
// Ausgabe diverser Variablen/SESSION - Nur für Debugzwecke ###########################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
	//echo nl2br(print_r($_SESSION,true));
	//echo nl2br(print_r($plot,true));
	//echo $_SESSION["plot_start"];
	//echo $_SESSION["keyboxframe"];
	
	//echo "".$keyboxframe_value."";
	//print_r($message);
	//echo "<pre>" . var_export($message,true) . "</pre>";  
	//echo "".$plot_setting."".$plot."";
	//$dauer = microtime(true) - $beginn; 
	//echo "Verarbeitung des Skripts: $dauer Sek.";

?>
