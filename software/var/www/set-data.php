<?php
 /*************************************************** 
    Copyright (C) 2018  Stephan Marrtin
    ***************************
		@author Stephan Martin
		@version 0.1, 06/04/18
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
//-----------------------------------------------------------------------------
// include function.php
require_once("function.php");
$thermoConfigFile = './conf/WLANThermo.conf'; 
//-----------------------------------------------------------------------------
// posted file
$input = file_get_contents('php://input');
$input_JSON = json_decode($input, JSON_UNESCAPED_SLASHES);

// main
If(empty($input)){
	echo 'no input'; //no input
}else{
	//Input 
	if(json_last_error()==JSON_ERROR_NONE){		//validate
	
		if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
		$thermoConfig = getConfig($thermoConfigFile, ";");			// read config file
		
		//Modify according to the received json
		$number = $input_JSON['number'];
		$number = $number - 1;
		
		$thermoConfig['ch_name']['ch_name'.strval($number)] = $input_JSON['name'];
		$thermoConfig['Sensoren']['ch'.strval($number)] = $input_JSON['typ']+1;		//if its changed, restart_thermo = true!
		$thermoConfig['temp_min']['temp_min'.strval($number)] = $input_JSON['min'];
		$thermoConfig['temp_max']['temp_max'.strval($number)] = $input_JSON['max'];
		
		if ($input_JSON['color']!=''){
			$thermoConfig['ch_color']['color_ch'.strval($number)] = $input_JSON['color'];
		}
		
		write_ini($thermoConfigFile, $thermoConfig);	// write config file
		
	}else{
		echo 'JSON decode error';
	}
}
?>