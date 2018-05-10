<?php
	session_start();
	require_once("function.php");
	session("./conf/WLANThermo.conf");
	$log_dateformat = 'd.m.y H:i:s';
	
	$output = array();
	$output['temp_unit'] = $_SESSION["temp_unit"];
	$output['pit'] = array();
	if (isset($_SESSION["pit_on"]) && $_SESSION["pit_on"] == "True") {
		$output['pit']['enabled'] = true;
		$pit_file = $_SESSION["pitmaster"].'';
		if (file_exists($pit_file)) {
			$currentpit = file_get_contents($_SESSION["pitmaster"]);
			$pits = explode(";",$currentpit);
			$output['pit']['timestamp'] = DateTime::createFromFormat($log_dateformat, $pits[0])->format(DateTime::ATOM);
			$output['pit']['setpoint'] = floatval($pits[1]);
			$output['pit']['current'] = floatval($pits[2]);
			$output['pit']['control_out'] = floatval($pits[3]);
			$output['pit']['ch'] = $_SESSION['pit_ch'];
			$output['pit']['type'] = $_SESSION['pit_type'];
			$output['pit']['open_lid'] = $_SESSION['pit_lid'];
		}
	} else {
		$output['pit']['enabled'] = false;
	}
        
	$output['pit2'] = array();
	if (isset($_SESSION["pit2_on"]) && $_SESSION["pit2_on"] == "True") {
		$output['pit2']['enabled'] = true;
		$pit_file = $_SESSION["pitmaster2"].'';
		if (file_exists($pit_file)) {
			$currentpit = file_get_contents($_SESSION["pitmaster2"]);
			$pits = explode(";",$currentpit);
			$output['pit2']['timestamp'] = DateTime::createFromFormat($log_dateformat, $pits[0])->format(DateTime::ATOM);
			$output['pit2']['setpoint'] = floatval($pits[1]);
			$output['pit2']['current'] = floatval($pits[2]);
			$output['pit2']['control_out'] = floatval($pits[3]);
			$output['pit2']['ch'] = $_SESSION['pit2_ch'];
			$output['pit2']['type'] = $_SESSION['pit2_type'];
			$output['pit2']['open_lid'] = $_SESSION['pit2_lid'];	
		}
	} else {
		$output['pit2']['enabled'] = false;
	}
        
	$cpuload = new CPULoad();
	$cpuload->get_load();
	$output['cpu_load'] = $cpuload->load["cpu"];
	$output['cpu_temp'] = get_cputemp();

	$output['channel'] = array();
	$currenttemp = file_get_contents($_SESSION["current_temp"]);
	while (preg_match("/TEMPLOG/i", $currenttemp) != "1"){
		$currenttemp = file_get_contents($_SESSION["current_temp"]);
	}
	$temp = explode(";",$currenttemp);
	$output['timestamp'] = DateTime::createFromFormat($log_dateformat, $temp[0])->format(DateTime::ATOM);
	for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
		$output['channel'][strval($i)] = array();
		$output['channel'][strval($i)]['temp'] = floatval($temp[$i + 1]);
		$output['channel'][strval($i)]['color'] = $_SESSION["color_ch".$i];
		$output['channel'][strval($i)]['state'] = $temp[$i + 1 + $_SESSION["channel_count"]];
		$output['channel'][strval($i)]['temp_min'] = floatval($_SESSION["temp_min".$i]);
		$output['channel'][strval($i)]['temp_max'] = floatval($_SESSION["temp_max".$i]);
		$output['channel'][strval($i)]['name'] = $_SESSION["ch_name".$i];
		$output['channel'][strval($i)]['alert'] = $_SESSION["alert".$i] == 'True' ? true : false;
		$output['channel'][strval($i)]['show'] = $_SESSION["ch_show".$i] == 'True' ? true : false;
	}
	
	echo(json_encode($output, JSON_FORCE_OBJECT))
?>	
