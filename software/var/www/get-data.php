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
0.068s (RSSI generated here)
*/
//-----------------------------------------------------------------------------

header('Content-type:application/json;charset=utf-8');	
echo json_encode(getData(), JSON_UNESCAPED_SLASHES);

function getData(){
	
	//Channel Temps:
	$output = array();
	
	$currenttemp = file_get_contents($_SESSION["current_temp"].'json');
	$temp = json_decode($currenttemp, true);
	
	//add RSSI to the premade json: 
	$output['system']['rssi'] = getRSSI();
	$output = array_merge_recursive($temp, $output);
	
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