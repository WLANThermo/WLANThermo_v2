<?php
 /*************************************************** 
    Copyright (C) 2018  Stephan Martin
    ***************************
		@author Stephan Martin
		@version 0.1, 24/03/18
	***************************
	This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    
    HISTORY: Please refer Github History
****************************************************/
session_start();
include("function.php");
//-----------------------------------------------------------------------------
// WLANThermo config path
$thermoConfigFile = './conf/WLANThermo.conf'; 
session($thermoConfigFile);
//-----------------------------------------------------------------------------
//Time test:
/*
$before = microtime(true); //designer2k2 hack!
for ($i=0 ; $i<100 ; $i++) {
	getData();
}	
$after = microtime(true);
echo ($after-$before)/$i . " sec/perRun\n";

/*
0.12s full
0.07s without RSSI
0.07s without Pitmaster
0.01s without RSSI / Pitmaster

0.06s is for this lines: $thermoConfig = getConfig($thermoConfigFile, ";"; The other is for the "exec iwconfig"

*/
//-----------------------------------------------------------------------------

header('Content-type:application/json;charset=utf-8');	
echo json_encode(getData(), JSON_UNESCAPED_SLASHES);

function getData(){
	
	$thermoConfigFile = './conf/WLANThermo.conf'; 
	$thermoConfig = getConfig($thermoConfigFile, ";");		//This line is slow!
	
	//Channel Temps:
	$output = array();
	$currenttemp = file_get_contents($_SESSION["current_temp"]);
	while (preg_match("/TEMPLOG/i", $currenttemp) != "1"){
		$currenttemp = file_get_contents($_SESSION["current_temp"]);
	}
	$temp = explode(";",$currenttemp);
	
	//System:
	$output['system']['time'] = DateTime::createFromFormat('d.m.y H:i:s', $temp[0])->getTimestamp();
	$output['system']['rssi'] = getRSSI();
	$output['system']['unit'] = strtoupper(substr($_SESSION["temp_unit"],0,1));
	
	//Channel:
	for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
		$output['channel'][strval($i)] = array();
		$output['channel'][strval($i)]['number'] = $i+1;
		$output['channel'][strval($i)]['name'] = $_SESSION["ch_name".strval($i)];
		$output['channel'][strval($i)]['temp'] = floatval($temp[$i + 1]==0 ? 999 : $temp[$i + 1]);
		$output['channel'][strval($i)]['typ'] = $thermoConfig['Sensoren']['ch'.strval($i).'']-1;
		$output['channel'][strval($i)]['min'] = floatval($_SESSION["temp_min".strval($i)]);
		$output['channel'][strval($i)]['max'] = floatval($_SESSION["temp_max".strval($i)]);
		$output['channel'][strval($i)]['alarm'] = $_SESSION["alert".strval($i)] == 'True' ? true : false;
		//$output['channel'][strval($i)]['show'] = $_SESSION["ch_show".strval($i)] == 'True' ? true : false;
		$output['channel'][strval($i)]['color'] = substr($_SESSION["color_ch".strval($i)],0,1)=='#' ? $_SESSION["color_ch".strval($i)] : getRGB($_SESSION["color_ch".strval($i)]);
	}
	
	//Pitmaster:
	$output['pitmaster'][0]['id'] = 0;
	$output['pitmaster'][0]['channel'] = $thermoConfig['Pitmaster']['pit_ch'];
	$output['pitmaster'][0]['value'] = $thermoConfig['Pitmaster']['pit_man'];
	$output['pitmaster'][0]['set'] = $thermoConfig['Pitmaster']['pit_set'];
	$output['pitmaster'][0]['io'] = $thermoConfig['Pitmaster']['pit_io_gpio'];
	$output['pitmaster'][0]['profil'] = 0;
	if ($thermoConfig['ToDo']['pit_on']=='False'){
		$typ = 'off';
	}else{
		if($thermoConfig['Pitmaster']['pit_man']=='0'){
			$typ = 'auto';
		}else{
			$typ = 'manual';
		}
	}
	$output['pitmaster'][0]['typ'] = $typ;
	$output['pitmaster'][0]['set_color'] = getRGB('yellow');
	$output['pitmaster'][0]['value_color'] = getRGB('khaki');
	
	$output['pitmaster'][1]['id'] = 1;
	$output['pitmaster'][1]['channel'] = $thermoConfig['Pitmaster2']['pit_ch'];
	$output['pitmaster'][1]['value'] = $thermoConfig['Pitmaster2']['pit_man'];
	$output['pitmaster'][1]['set'] = $thermoConfig['Pitmaster2']['pit_set'];
	$output['pitmaster'][1]['io'] = $thermoConfig['Pitmaster2']['pit_io_gpio'];
	$output['pitmaster'][1]['profil'] = 0;
	if ($thermoConfig['ToDo']['pit2_on']=='False'){
		$typ = 'off';
	}else{
		if($thermoConfig['Pitmaster2']['pit_man']=='0'){
			$typ = 'auto';
		}else{
			$typ = 'manual';
		}
	}
	$output['pitmaster'][1]['typ'] = $typ;
	$output['pitmaster'][1]['set_color'] = getRGB('gray');
	$output['pitmaster'][1]['value_color'] = getRGB('dark-grey');
	
	//Finish
	return $output;
}

function getRSSI(){
	//extract from wifi.php:
	exec('iwconfig wlan0',$return);		//This line is slow!
	preg_match('/Signal Level=(-[0-9]+)/i',$return[5],$result);
	return intval($result[1]);
}

function getRGB($colorname){
	//Converts colorname to RGBhex:
	$array = array('008000' => 'green', 'ff0000' => 'red', '0000ff' => 'blue', '808000' => 'olive','ff00ff' => 'magenta', 'ffff00' => 'yellow', 'ee82ee' => 'violet', 'ffa500' => 'orange','8968cd' => 'mediumpurple3', '7fffd4' => 'aquamarine', 'a52a2a' => 'brown', 'dda0dd' => 'plum','87ceeb' => 'skyblue', 'ff4500 ' => 'orange-red', 'fa8072' => 'salmon', 'ffffff' => 'black','a9a9a9' => 'dark-grey', '800080' => 'purple', '40e0d0' => 'turquoise', 'f0e68c' => 'khaki','9400d3' => 'dark-violet', '54ff9f ' => 'seagreen', '00b8ff' => 'web-blue', '4682b4' => 'steelblue', 'ffd700' => 'gold', '006400' => 'dark-green','191970' => 'midnight-blue', 'bdb76b' => 'dark-khaki', '556b2f' => 'dark-olivegreen', 'ffc0cb' => 'pink','7fff00' => 'chartreuse', '808080' => 'gray', '708090' => 'slategrey');
	return '#'.array_search($colorname, $array); 
}

?>