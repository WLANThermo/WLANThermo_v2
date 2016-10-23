<?php
//-----------------------------------------------------------------------------------
// Config einlesen ##################################################################
//-----------------------------------------------------------------------------------

function getConfig ($filename, $commentchar) {
	$readConfig = '';	//Variablen deklarieren
	$config = '';	//Variablen deklarieren
	$section = '';	//Variablen deklarieren
	
	$readConfig = file($filename);
	foreach ($readConfig as $filedata) {
		$dataline = trim($filedata);
		$firstchar = substr($dataline, 0, 1);
		if ($firstchar!=$commentchar && $dataline!='') {
		//It's an entry (not a comment and not a blank line)
			if ($firstchar == '[' && substr($dataline, -1, 1) == ']') {
			//It's a section
			$section = substr($dataline, 1, -1);
			}else{
			//It's a key...
			$delimiter = strpos($dataline, '=');
				if ($delimiter > 0) {
					//...with a value
					$key = trim(substr($dataline, 0, $delimiter));
					$value = trim(substr($dataline, $delimiter + 1));
					if (substr($value, 1, 1) == '"' && substr($value, -1, 1) == '"') { 
						$value = substr($value, 1, -1); 
					}
					$config[$section][$key] = stripcslashes($value);
				}else{
				//...without a value
					$config[$section][trim($dataline)]='';
				}
			}
		}else{
			//It's a comment or blank line.  Ignore.
		}
   }
   return $config;
}

//-----------------------------------------------------------------------------------
// Config Pfad ######################################################################
//-----------------------------------------------------------------------------------

function getConfigPath(){
	return "./conf/WLANThermo.conf";
}

//-----------------------------------------------------------------------------------
// Temperatur Pfad ##################################################################
//-----------------------------------------------------------------------------------

function getCurrentTempPath(){
	$configPath = getConfigPath();
	if (file_exists($configPath)) {
		if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0);
		$config = getConfig($configPath , ";");
		return $config['filepath']['current_temp'];
	}else{
		return "False";
	}
}

//-----------------------------------------------------------------------------------
// Aktueller Name des Logfiles ######################################################
//-----------------------------------------------------------------------------------

function getCurrentLogFileName(){
	$currentTempPath = getCurrentTempPath();
	if ($currentTempPath != "False"){
		$currenttemp = file_get_contents($currentTempPath);
		while (preg_match("/TEMPLOG/i", $currenttemp) != "1"){
			$currenttemp = file_get_contents($currentTempPath);
		}
		$temp = explode(";",$currenttemp);
		$currentlogfilename = "".$temp[18].".csv";
		return $currentlogfilename;
	}else{
		return "False";
	}
}

//----------------------------------------------------------------------------------- 
// Logfile Verzeichnis auslesen #####################################################
//-----------------------------------------------------------------------------------

function getLogfiles() {
	$directory_log = './thermolog/';
	$directory_plot = './thermoplot/';
	$currentlogfilename = getCurrentLogFileName();
	$readFiles = array();
	$iterator = new DirectoryIterator($directory_log);
	foreach ($iterator as $fileinfo) {
		if ($fileinfo->isFile()) {
			$readFiles[$fileinfo->getMTime()] = $fileinfo->getFilename();
		}
	}
	krsort($readFiles);
	foreach($readFiles as $key => $file_name) {
		if (preg_match("/.csv/i", $file_name) == "1"){
			$file = "".$directory_log."".$file_name."";
			$filesize = filesize($file);
			if ($filesize > "1048576") {
				$filesize = "".round( $filesize /1024/1024 ,2 )."MB";
			}else{
				$filesize = "".ceil( $filesize /1024 )."KB";
			}
			if((iconv("UTF-8", "ISO-8859-1", $file_name) == iconv("UTF-8", "ISO-8859-1", $currentlogfilename)) or (iconv("UTF-8", "ISO-8859-1", $file_name) == "TEMPLOG.csv")){
				$editable = "False";
			}else{
				$editable = "True";
			}
			$file_plot = "".$directory_plot."".substr($file_name, 0, -4).".png";
			if (!file_exists($file_plot)) {
				$file_plot = "";
			}
			$file_csv = "".$directory_log."".substr($file_name, 0, -4).".csv";
			if (!file_exists($file_csv)) {
				$file_csv = "";
			}
			$readFiles[$key] = array("name" => $file_name , "filesize" => $filesize , "editable" => $editable, "plot" => $file_plot, "logfile" => $file_csv );
		}else{
			unset($readFiles[$key]);
		}
	}
	return $readFiles;
}
//----------------------------------------------------------------------------------- 
// Funktion um Temperaturen.csv zu erstellen ########################################
//-----------------------------------------------------------------------------------

function writeTmpMinMaxFile($tmp_min_max_value, $tmpFile) {

	$fp = @fopen($tmpFile . '_phptmp', "w+");
	if(!$fp) die("Temperaturen.csv konnte nicht erstellt werden!");
	fwrite($fp, $tmp_min_max_value);
	fflush($fp);
	fclose ($fp);
	rename($tmpFile . '_phptmp', $tmpFile);
}
//----------------------------------------------------------------------------------- 
// Funktion um SESSION Variablen neu zu laden #######################################
//----------------------------------------------------------------------------------- 

function session($configfile) {
	if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
	$ini = getConfig("".$configfile."", ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.	
	for ($i = 0; $i <= 7; $i++){
		$_SESSION["color_ch".$i] = $ini['plotter']['color_ch'.$i];
		$_SESSION["temp_min".$i] = $ini['temp_min']['temp_min'.$i];  
		$_SESSION["temp_max".$i] = $ini['temp_max']['temp_max'.$i];
		$_SESSION["ch_name".$i] = $ini['ch_name']['ch_name'.$i];
		$_SESSION["alert".$i] = $ini['web_alert']['ch'.$i];
		$_SESSION["ch_show".$i] = $ini['ch_show']['ch'.$i];
	}
	$_SESSION["locale"] = $ini['locale']['locale'];
	$_SESSION["temp_unit"] = $ini['locale']['temp_unit'];
	$_SESSION["color_pit"] = $ini['plotter']['color_pit'];
	$_SESSION["color_pitsoll"] = $ini['plotter']['color_pitsoll'];
	$_SESSION["plot_start"] = $ini['ToDo']['plot_start'];
	$_SESSION["plotname"] = $ini['plotter']['plotname'];
	$_SESSION["plotsize"] = $ini['plotter']['plotsize'];
	$_SESSION["plot_pit"] = $ini['plotter']['plot_pit'];
	$_SESSION["plotbereich_min"] = $ini['plotter']['plotbereich_min'];
	$_SESSION["plotbereich_max"] = $ini['plotter']['plotbereich_max'];
	$_SESSION["keybox"] = $ini['plotter']['keybox'];
	$_SESSION["keyboxframe"] = $ini['plotter']['keyboxframe'];
	$_SESSION["pit_on"] = $ini['ToDo']['pit_on'];
	$_SESSION["pit_ch"] = $ini['Pitmaster']['pit_ch'];
	$_SESSION["webcam_start"] = $ini['webcam']['webcam_start'];
	$_SESSION["webcam_name"] = $ini['webcam']['webcam_name'];
	$_SESSION["webcam_size"] = $ini['webcam']['webcam_size'];
	$_SESSION["raspicam_start"] = $ini['webcam']['raspicam_start'];
	$_SESSION["raspicam_name"] = $ini['webcam']['raspicam_name'];
	$_SESSION["raspicam_size"] = $ini['webcam']['raspicam_size'];
	$_SESSION["raspicam_exposure"] = $ini['webcam']['raspicam_exposure'];
	$_SESSION["current_temp"] = $ini['filepath']['current_temp'];
	$_SESSION["pitmaster"] = $ini['filepath']['pitmaster'];
	$_SESSION["showcpulast"] = $ini['Hardware']['showcpulast'];
	$_SESSION["checkUpdate"] = $ini['update']['checkupdate'];
	$_SESSION["check_update_url"] = $ini['update']['check_update_url'];
	if (isset($_SESSION["webGUIversion"])){
		if ($_SESSION["checkUpdate"] == "True"){
			$check_update = updateCheck("".$_SESSION["webGUIversion"]."");
			$_SESSION["updateAvailable"] = $check_update;
		}else{
			$_SESSION["updateAvailable"] = "False";
		}
	}else{
		$_SESSION["updateAvailable"] = "";
	}
	if(!isset($_SESSION["websoundalert"])){ $_SESSION["websoundalert"] = "True";}	
}
//-----------------------------------------------------------------------------------
// Überprüfen ob SessionVariablen existieren ########################################
//-----------------------------------------------------------------------------------

function checkSession(){

	for ($i = 0; $i <= 7; $i++){
		if (!isset($_SESSION["color_ch".$i]) or !isset($_SESSION["temp_min".$i]) or !isset($_SESSION["temp_max".$i]) or !isset($_SESSION["ch_name".$i]) or !isset($_SESSION["ch_show".$i]) or !isset($_SESSION["alert".$i])){
			session("./conf/WLANThermo.conf");
		}
	}
	if (!isset($_SESSION["plotsize"]) OR !isset($_SESSION["plotname"]) OR !isset($_SESSION["keybox"]) OR !isset($_SESSION["plotbereich_min"]) OR !isset($_SESSION["plotbereich_max"]) OR !isset($_SESSION["plot_start"])) {
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}
	if (!isset($_SESSION["current_temp"])) {
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}
	if (!isset($_SESSION["webcam_start"]) OR !isset($_SESSION["webcam_name"]) OR !isset($_SESSION["webcam_size"]) OR !isset($_SESSION["raspicam_start"]) OR !isset($_SESSION["raspicam_name"]) OR !isset($_SESSION["raspicam_exposure"]) OR !isset($_SESSION["raspicam_size"])) {
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}
	if (!isset($_SESSION["showcpulast"])){
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}	
	if (!isset($_SESSION["updateAvailable"])){
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}		
	if (!isset($_SESSION["checkUpdate"])){
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}
	if (!isset($_SESSION["locale"]) OR !isset($_SESSION["temp_unit"])) {
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}	
}
//-----------------------------------------------------------------------------------
// Restore Config ###################################################################
//-----------------------------------------------------------------------------------

function restoreConfig($newconfig,$oldconfig) {
	if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
	$newconfigfile = getConfig("".$newconfig."", ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.	
	$oldconfigfile = getConfig("".$oldconfig."", ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.

	foreach($newconfigfile as $key => $value) {
		foreach($value as $key1 => $value1) {
			if (isset($oldconfigfile[$key][$key1])){
				$newconfigfile[$key][$key1] = $oldconfigfile[$key][$key1];
			}
		}
	} 
	write_ini($newconfig, $newconfigfile);
}

function getPlotConfig($plot,$temp_unit){
	if($_SESSION["keyboxframe"] == "True"){ 
		$keyboxframe_value = "box lw 2";
	}
	if($_SESSION["keyboxframe"] == "False"){ 
		$keyboxframe_value = "";
	}
	if ($temp_unit == 'celsius') {
		$temp_unit = "[°C]";
	} elseif ($temp_unit == 'fahrenheit') {
		$temp_unit = "[°F]";
	}
	$plotsize = explode("x", $_SESSION["plotsize"]);
	$plotsize = "".$plotsize[0].",".$plotsize[1]."";	
	$plot_setting = "reset;";
	$plot_setting .= "set encoding locale;";
	$plot_setting .= "set terminal png size ".$plotsize." transparent;";
	$plot_setting .= "set title \\\"".$_SESSION["plotname"]."\\\";";
	$plot_setting .= "set datafile separator ',';";
	$plot_setting .= "set output \\\"/var/www/tmp/temperaturkurve_view.png\\\";";
	$plot_setting .= "set key ".$_SESSION["keybox"]." ".$keyboxframe_value.";";
	$plot_setting .= "unset grid;";
	$plot_setting .= "set xdata time;";
	$plot_setting .= "set timefmt \\\"%d.%m.%y %H:%M:%S\\\";";
	$plot_setting .= "set format x \\\"%H:%M\\\";";
	$plot_setting .= "set xlabel \\\"Uhrzeit\\\";";
	$plot_setting .= "set y2label \\\"Temperatur ".$temp_unit."\\\";";
	$plot_setting .= "set y2range [".$_SESSION["plotbereich_min"].":".$_SESSION["plotbereich_max"]."];";
	$plot_setting .= "set xtics nomirror;";
	$plot_setting .= "set y2tics nomirror;";
	if ($_SESSION["plot_pit"] == "True") {
		$plot_setting .= "set ylabel \\\"Pitmaster %\\\";";
		$plot_setting .= 'set yrange ["0":"105"];';
		$plot_setting .= "set ytics nomirror;";	
		$plot .= ", '/var/log/WLAN_Thermo/TEMPLOG.csv' every ::1 using 1:11 with lines lw 2 lc rgbcolor '".$_SESSION["color_pitsoll"]."' t 'Pitmaster Sollwert'  axes x1y2";
		$plot .= ", '/var/log/WLAN_Thermo/TEMPLOG.csv' every ::1 using 1:10 with lines lw 2 lc rgbcolor '".$_SESSION["color_pit"]."' t 'Pitmaster %' axes x1y1";
	}else{
		$plot_setting .= "set ylabel \\\"Temperatur [°C]\\\";";
		$plot_setting .= "set yrange [".$_SESSION["plotbereich_min"].":".$_SESSION["plotbereich_max"]."];";
		$plot_setting .= "set ytics nomirror;";		
	}	
	$plot_setting = "".$plot_setting."".$plot."";
	return $plot_setting;
}
//------------------------------------------------------------------------------------------------------------------------------------- 
// Funktion zum Download einer URL-Datei ##############################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

function download($url) {
	$ch = curl_init($url);
	curl_setopt ($ch, CURLOPT_URL, $url);
	curl_setopt ($ch, CURLOPT_HEADER, 0);
	curl_setopt ($ch, CURLOPT_RETURNTRANSFER, 1);
	$result = curl_exec ($ch);
	curl_close ($ch);
	return $result;
} 

//------------------------------------------------------------------------------------------------------------------------------------- 
// Funktion UpdateCheck ###############################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

function updateCheck($version) {
	$check_update_url = $_SESSION["check_update_url"]; //Update Server
	$file_headers = @get_headers($check_update_url);
	if($file_headers[0] == 'HTTP/1.1 404 Not Found') {
		//echo "Server nicht erreichbar";
	}else{
		//echo "File existiert";
		$check_update_string = download("".$check_update_url."");
		$check_update_array = parse_ini_string($check_update_string);
		if (isset($check_update_array['version'])) {
			$webGUIversion = $check_update_array['version'];
			if (version_compare("".$webGUIversion."", "".$version."", ">")) {
				//echo "Update Vorhanden";
				$update = "True";
				$_SESSION["newversion"] = $webGUIversion;
			}else{
				//echo "Sie sind am Aktuellsten stand";
				$update = "False";
			}
		}else{
			$update = "False";
		}
		//print_r($check_update_array);
		//echo $webGUIversion;
	}
	return $update;
} 

//------------------------------------------------------------------------------------------------------------------------------------- 
// Funktion zum schreiben der ini Datei ###############################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

function write_ini($inipath, $ini) {
	$new_ini = fopen($inipath . '_phptmp', 'w');
	foreach($ini AS $section_name => $section_values){
		fwrite($new_ini, "[$section_name]\n");
		foreach($section_values AS $key => $value){
			fwrite($new_ini, "$key = $value\n");
		}
		fwrite($new_ini, "\n");
	}
	fflush($new_ini);
	fclose($new_ini);
	rename($inipath . '_phptmp', $inipath);
}

//------------------------------------------------------------------------------------------------------------------------------------- 
// Funktion für wifi.php ##############################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------

function ConvertToChannel($freq) {
	$base = 2412;
	$channel = 1;
	for($x = 0; $x < 13; $x++) {
		if($freq != $base) {
			$base = $base + 5;
			$channel++;
		} else {
			return $channel;
		}
	}
	return "Invalid Channel";
}

function ConvertToSecurity($security) {
	switch($security) {
		case "[WPA2-PSK-CCMP][ESS]":
			return "WPA2-PSK (AES)";
		break;
		case "[WPA2-PSK-TKIP][ESS]":
			return "WPA2-PSK (TKIP)";
		break;
		case "[WPA-PSK-TKIP+CCMP][WPS][ESS]":
			return "WPA-PSK (TKIP/AES) with WPS";
		break;
		case "[WPA-PSK-TKIP+CCMP][WPA2-PSK-TKIP+CCMP][ESS]":
			return "WPA/WPA2-PSK (TKIP/AES)";
		break;
		case "[WPA-PSK-TKIP][ESS]":
			return "WPA-PSK (TKIP)";
		break;
		case "[WEP][ESS]":
			return "WEP";
		break;
	}
}

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
		if ($_SESSION['temp_unit'] == 'celsius') {
			$cpu_temp = floatval($output[0]);
		} elseif ($_SESSION['temp_unit'] == 'fahrenheit') {
			$cpu_temp = floatval($output[0]) * 1.8 + 32;
		}
		return $cpu_temp;
	}else{
		return "n/a";
	}
}

?>
