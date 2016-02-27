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
	include("function.php");
	$esound = "0"; // Variable für Soundalarmierung;
	$esound_ = "0";
	$message = "\n";
	$timestamp = "";
	$pit_time_stamp = "";
	$pit_val = "";
	$pit_set = "";

//	$pit_file = '.'.$_SESSION["pitmaster"].'';
//	if (file_exists($pit_file)) {
//		include('.'.$_SESSION["pitmaster"].'');
//	}

//-------------------------------------------------------------------------------------------------------------------------------------
// SESSION-Variablen überprüfen #######################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

	checkSession();
	
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
		echo '<div id="info_site"><p><b>WLANThermo update:</b> '.$last_line.'</p></div>';
	}else{
		echo '<div id="info_site"><b>Das Update wird gerade Installiert...</b></div>';
	}
	$_SESSION["to_update"] = 'True';
	echo '<script>$(function() { showLoading();});</script>';
	exit;
} 
if (file_exists(dirname(__FILE__).'/tmp/reboot')) { 
	$message .= "Reboot - Raspberry wird neu gestartet\n";
	echo '<div id="info_site"><b>Raspberry Pi wird gerade neu gestartet...</b></div>';
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
		echo '<div id="info_site"><p><b>NEXTION Display update:</b> '.$last_line.'</p></div>';
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
		if (file_exists(dirname(__FILE__).'/conf/WLANThermo.conf') AND file_exists(dirname(__FILE__).'/conf/WLANThermo.conf.old')) {
			restoreConfig("./conf/WLANThermo.conf","./conf/WLANThermo.conf.old");
		}
		session("./conf/WLANThermo.conf");
		echo '<script>$(function() { hideUpdate();});</script>';
		echo '<script>$(function() { hideLoading();});</script>';
		$_SESSION["updateAvailable"] == "False";
		$_SESSION["webGUIversion"] = $_SESSION["newversion"];
		unset($_SESSION["to_update"]);
	}
}
	echo '<script>$(function() { hideLoading();});</script>';

	//-------------------------------------------------------------------------------------------------------------------------------------
	// CPU Auslastung #####################################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

	define("TEMP_PATH","/tmp/");

	class CPULoad {
	
		function check_load() {
			$fd = fopen("/proc/stat","r");
			if ($fd) {
				$statinfo = explode("\n",fgets($fd, 1024));
				fclose($fd);
				foreach($statinfo as $line) {
					$info = explode(" ",$line);
					//echo "<pre>"; var_dump($info); echo "</pre>";
					if($info[0]=="cpu") {
						array_shift($info);  // pop off "cpu"
						if(!$info[0]) array_shift($info); // pop off blank space (if any)
						$this->user = $info[0];
						$this->nice = $info[1];
						$this->system = $info[2];
						$this->idle = $info[3];
						// $this->print_current();
						return;
					}
				}
			}
		}
		function load_load() {
			$fp = @fopen(TEMP_PATH."cpuinfo.tmp","r");
			if ($fp) {
				$lines = explode("\n",fread($fp,1024));
				$this->lasttime = $lines[0];
				list($this->last_user,$this->last_nice,$this->last_system,$this->last_idle) = explode(" ",$lines[1]);
				list($this->load["user"],$this->load["nice"],$this->load["system"],$this->load["idle"],$this->load["cpu"]) = explode(" ",$lines[2]);
				fclose($fp);
			}else{
				$this->lasttime = time() - 60;
				$this->last_user = $this->last_nice = $this->last_system = $this->last_idle = 0;
				$this->user = $this->nice = $this->system = $this->idle = 0;
			}
		}
		function calculate_load() {
			//$this->print_current();
			$d_user = $this->user - $this->last_user;
			$d_nice = $this->nice - $this->last_nice;
			$d_system = $this->system - $this->last_system;
			$d_idle = $this->idle - $this->last_idle;
			//printf("Delta - User: %f  Nice: %f  System: %f  Idle: %f<br/>",$d_user,$d_nice,$d_system,$d_idle);
			$total=$d_user+$d_nice+$d_system+$d_idle;
			if ($total<1) $total=1;
			$scale = 100.0/$total;
			$cpu_load = ($d_user+$d_nice+$d_system)*$scale;
			$this->load["user"] = $d_user*$scale;
			$this->load["nice"] = $d_nice*$scale;
			$this->load["system"] = $d_system*$scale;
			$this->load["idle"] = $d_idle*$scale;
			$this->load["cpu"] = ($d_user+$d_nice+$d_system)*$scale;
		}

		function get_load($fastest_sample=4) {
			$this->load_load();
			$this->cached = (time()-$this->lasttime);
			if ($this->cached>=$fastest_sample) {
				$this->check_load(); 
				$this->calculate_load();
			}
		}
	}	
	function get_cputemp(){
		exec("sudo /opt/vc/bin/vcgencmd measure_temp | tr -d \"temp=\" | tr -d \"'C\"",$output, $return);
		if((!$return) AND (isset($output[0]))){
			return $output[0];
		}else{
			return "n/a";
		}
	} 
	//-------------------------------------------------------------------------------------------------------------------------------------
	// Temperaturwerte einlesen ###########################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

		$currenttemp = file_get_contents($_SESSION["current_temp"]);
		while (preg_match("/TEMPLOG/i", $currenttemp) != "1"){
			$currenttemp = file_get_contents($_SESSION["current_temp"]);
		}
		$temp = explode(";",$currenttemp);
		$time_stamp = $temp[0];
		$temp_0 = $temp[1];
		$temp_1 = $temp[2];
		$temp_2 = $temp[3];
		$temp_3 = $temp[4];
		$temp_4 = $temp[5];
		$temp_5 = $temp[6];
		$temp_6 = $temp[7];
		$temp_7 = $temp[8];
		$_SESSION["currentlogfilename"] = $temp[18];
		
		$pit_file = $_SESSION["pitmaster"].'';
		if (file_exists($pit_file)) {
			$currentpit = file_get_contents($_SESSION["pitmaster"]);
			$pits = explode(";",$currentpit);
			$pit_time_stamp = $pits[0];
			$pit_set = $pits[1];
			$pit_val = $pits[3];
		}

	//-------------------------------------------------------------------------------------------------------------------------------------
	// Anzeige Letzte Messung #############################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

	if ($_SESSION["pit_on"] == "True"){?>
		<div class="last_regulation_view">Letzte Regelung am <b><?php echo $pit_time_stamp; ?></b> Uhr</div><?php
	}?>
	<div class="last_measure_view">Letzte Messung am <b><?php echo $time_stamp; ?></b> Uhr
	<?php if($_SESSION["showcpulast"] == "True"){
	echo "<br>";
	$cpuload = new CPULoad();
	$cpuload->get_load();
	$CPULOAD = round($cpuload->load["cpu"],1);
	echo "CPU Auslastung: <b>".$CPULOAD."% / ".get_cputemp()."&#176;C</b>";
	}
	?>
	</div>						 
	<br>
	<div class="clear"></div>

	<!-- ----------------------------------------------------------------------------------------------------------------------------------
	// Session in Array Speichern (sensoren)(plotter farben) etc. #########################################################################
	//--------------------------------------------------------------------------------------------------------------------------------- -->

	<?php
	for ($i = 0; $i <= 7; $i++){
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
	for ($i = 0; $i <= 7; $i++){
		$a = $i + 2 ;
		$chp[$i] = "'/var/log/WLAN_Thermo/TEMPLOG.csv' every ::1 using 1:$a with lines lw 2 lc rgb \\\"$color_ch[$i]\\\" t '$channel_name[$i]'  axes x1y2";
	}	
			
	//-------------------------------------------------------------------------------------------------------------------------------------
	// Ausgabe der Temperaturen ###########################################################################################################
	//-------------------------------------------------------------------------------------------------------------------------------------

		for ($i = 0; $i <= 7; $i++){
			
			if((${"temp_$i"} != "999.9") AND ($ch_show[$i] == "True")){
				if((${"temp_$i"} < $temp_min[$i]) AND (${"temp_$i"} > "-20" && ${"temp_$i"} < "280")){
					$temperature_indicator_color = "temperature_indicator_blue";
					if($alert[$i] == "True") { 
						$esound = "1"; 
						$esound_ = "1";
					}
				}elseif((${"temp_$i"} > $temp_max[$i]) AND (${"temp_$i"} > "-20" && ${"temp_$i"} < "280")){
					$temperature_indicator_color = "temperature_indicator_red";
					if($alert[$i] == "True") { 
						$esound = "1"; 
						$esound_ = "1";
					}
				}else{
					$temperature_indicator_color = "temperature_indicator"; 
					$esound_ = "0";
				}
				if	($plot !== "plot "){
					$plot .= ", ";}
					$plot .= "$chp[$i]";
				?>
					<div class="channel_view">
						<div class="channel_name"><?php echo htmlentities($channel_name[$i], ENT_QUOTES, "iso-8859-1"); ?></div>
						<div class="<?php echo $temperature_indicator_color;?>"><?php echo ${"temp_$i"};?>&#176;C</div>
						<div class="tempmm">Temp min <b><?php echo $temp_min[$i];?>&#176;C</b> / max <b><?php echo $temp_max[$i];?>&#176;C</b></div>
						<div class="headicon"><font color="<?php echo $color_ch[$i];?>">#<?php echo $i;?></font></div>
						<div class="webalert"><?php 
							if ($_SESSION["websoundalert"] == "True" && $esound_ == "1"){ 
								echo "<td><a href=\"#\" id=\"webalert_false\" class=\"webalert_false\" ><img src=\"../images/icons32x32/speaker.png\" border=\"0\" alt=\"Alarm\" title=\"Alarm\"></a></td>\n"; 
							}elseif($_SESSION["websoundalert"] == "False" && $esound_ == "1"){ 
								echo "<td><a href=\"#\" id=\"webalert_true\" class=\"webalert_true\" ><img src=\"../images/icons32x32/speaker_mute.png\" border=\"0\" alt=\"Alarm\" title=\"Alarm\"></a></td>\n"; 
							}?>
						</div>
						<?php
						if (($_SESSION["pit_ch"] == "$i") && ($_SESSION["pit_on"] == "True")){
						?>
							<div class="headicon_left"><img src="../images/icons16x16/pitmaster.png" alt=""></div>
							<div class="pitmaster_left"> <?php echo $pit_val; ?> / <?php echo $pit_set; ?>&#176;C</div>
						<?php 
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
		$plot_setting = getPlotConfig($plot);
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