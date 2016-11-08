<?php
	session_start();
	include("function.php");
	session("./conf/WLANThermo.conf");
	$log_dateformat = 'd.m.y H:i:s';
	
	$output = array();
	
	$output['pit'] = array();
	if ($_SESSION["pit_on"] == "True") {
		$output['pit']['enabled'] = true;
		$pit_file = $_SESSION["pitmaster"].'';
		if (file_exists($pit_file)) {
			$currentpit = file_get_contents($_SESSION["pitmaster"]);
			$pits = explode(";",$currentpit);
			$output['pit']['timestamp'] = DateTime::createFromFormat($log_dateformat, $pits[0])->format(DateTime::ATOM);
			$output['pit']['setpoint'] = floatval($pits[1]);
			$output['pit']['current'] = floatval($pits[2]);
			$output['pit']['control_out'] = floatval($pits[3]);
		}
	} else {
		$output['pit']['enabled'] = false;
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
	for ($i = 0; $i <= 7; $i++){
		$output['channel'][strval($i)] = array();
		$output['channel'][strval($i)]['temp'] = floatval($temp[$i + 1]);
		$output['channel'][strval($i)]['color'] = $_SESSION["color_ch".$i];
		$output['channel'][strval($i)]['state'] = $temp[$i + 9];
		$output['channel'][strval($i)]['temp_min'] = floatval($_SESSION["temp_min".$i]);
		$output['channel'][strval($i)]['temp_max'] = floatval($_SESSION["temp_max".$i]);
		$output['channel'][strval($i)]['name'] = $_SESSION["ch_name".$i];
		$output['channel'][strval($i)]['alert'] = $_SESSION["alert".$i] == 'True' ? true : false;
		$output['channel'][strval($i)]['show'] = $_SESSION["ch_show".$i] == 'True' ? true : false;
	}
	
	echo(json_encode($output, JSON_FORCE_OBJECT))
?>	