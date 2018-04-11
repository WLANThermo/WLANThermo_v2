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
	$thermoConfig = getConfig($thermoConfigFile, ";");
	
	//Channel Temps:
	$output = array();
	
	$currenttemp = file_get_contents($_SESSION["current_temp"].'json');
	$temp = json_decode($currenttemp, true);
	
	//System:
	$output['system']['time'] = $temp['time'];
	$output['system']['rssi'] = getRSSI();
	$output['system']['unit'] = strtoupper(substr($_SESSION["temp_unit"],0,1));
	
	//Channel:
	for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
		$output['channel'][strval($i)] = array();
		$output['channel'][strval($i)]['number'] = $i+1;
		$output['channel'][strval($i)]['name'] = $_SESSION["ch_name".strval($i)];
		$output['channel'][strval($i)]['temp'] = floatval($temp['cht_'.$i]==0 ? 999 : $temp['cht_'.$i]);
		$output['channel'][strval($i)]['typ'] = $thermoConfig['Sensoren']['ch'.strval($i).'']-1;
		$output['channel'][strval($i)]['min'] = floatval($_SESSION["temp_min".strval($i)]);
		$output['channel'][strval($i)]['max'] = floatval($_SESSION["temp_max".strval($i)]);
		$output['channel'][strval($i)]['alarm'] = $_SESSION["alert".strval($i)] == 'True' ? true : false;
		//$output['channel'][strval($i)]['show'] = $_SESSION["ch_show".strval($i)] == 'True' ? true : false;
		$output['channel'][strval($i)]['color'] = $thermoConfig['ch_color']['color_ch'.strval($i)];
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
	$output['pitmaster'][0]['set_color'] = '#ffff00';
	$output['pitmaster'][0]['value_color'] = '#fa8072';
	
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
	$output['pitmaster'][1]['set_color'] = '#808080';
	$output['pitmaster'][1]['value_color'] = '#191970';
	
	//Finish
	return $output;
}

function getRSSI(){
	//extract from wifi.php:
	exec('iwconfig wlan0',$return);		//This line is slow!
	preg_match('/Signal Level=(-[0-9]+)/i',$return[5],$result);
	return intval($result[1]);
}

?>