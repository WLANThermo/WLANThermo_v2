<?php
 /*************************************************** 
    Copyright (C) 2018  Florian Riedl
    ***************************
		@author Florian Riedl
		@version 0.2, 26/02/18
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
// error reporting
 error_reporting(E_ALL); 
//-----------------------------------------------------------------------------
// start runtome counter
 $time_start = microtime(true);
//-----------------------------------------------------------------------------
// WLANThermo config path
$thermoConfigFile = '../conf/WLANThermo.conf'; 
//-----------------------------------------------------------------------------
// sensor config path
$sensorConfigFile = '../conf/sensor.conf'; 
//-----------------------------------------------------------------------------



//-----------------------------------------------------------------------------
// main 

// load config
$thermoConfig = getConfig($thermoConfigFile, ";");
$sensorConfig = getConfig($sensorConfigFile, ";");

//$jsonArr = array();
$jsonArr = createJSON($thermoConfig,$sensorConfig);

$test = printJSON($jsonArr);
echo $test;




//-----------------------------------------------------------------------------	
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
						// Strip double slashes
						$value = substr($value, 1, -1); 
					}  elseif (is_numeric($value)) {
						// Convert numeric values
						$value = $value + 0;
					} else {
						$value = stripcslashes($value);
					}
					
					$config[$section][$key] = $value;
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
//-----------------------------------------------------------------------------
function printJSON($array){
	return json_encode($array, JSON_UNESCAPED_SLASHES);		
}
//-----------------------------------------------------------------------------
function createJSON($thermoConfig,$sensorConfig){
	$JsonArr = array();
	$JsonArr['display']['lcd_present'] = $thermoConfig['Display']['lcd_present'];
	$JsonArr['display']['error_val'] = $thermoConfig['Display']['error_val'];
	$JsonArr['display']['lcd_type'] = $thermoConfig['Display']['lcd_type'];
	$JsonArr['display']['dim'] = $thermoConfig['Display']['dim'];
	$JsonArr['display']['timeout'] = $thermoConfig['Display']['timeout'];
	$JsonArr['display']['start_page'] = $thermoConfig['Display']['start_page'];
	$JsonArr['display']['serialspeed'] = $thermoConfig['Display']['serialspeed'];
	$JsonArr['display']['serialdevice'] = $thermoConfig['Display']['serialdevice'];
	$JsonArr['display']['nextion_update_enabled'] = $thermoConfig['Display']['nextion_update_enabled'];
	
	$JsonArr['telegram']['telegram_alert'] = $thermoConfig['Telegram']['telegram_alert'];
	$JsonArr['telegram']['telegram_chat_id'] = $thermoConfig['Telegram']['chat_id'];
	$JsonArr['telegram']['telegram_token'] = $thermoConfig['Telegram']['telegram_token'];
	
	$JsonArr['sound']['beeper_enabled'] = $thermoConfig['Sound']['beeper_enabled'];
	$JsonArr['sound']['beeper_on_start'] = $thermoConfig['Sound']['beeper_on_start'];
	$JsonArr['sound']['websound_enabled'] = $thermoConfig['Sound']['websound_enabled'];
	
	$JsonArr['alert']['alarm_high_template'] = $thermoConfig['Alert']['alarm_high_template'];
	$JsonArr['alert']['alarm_low_template'] = $thermoConfig['Alert']['alarm_low_template'];
	$JsonArr['alert']['status_template'] = $thermoConfig['Alert']['status_template'];
	$JsonArr['alert']['message_template'] = $thermoConfig['Alert']['message_template'];
	$JsonArr['alert']['status_interval'] = $thermoConfig['Alert']['status_interval'];
	$JsonArr['alert']['alarm_interval'] = $thermoConfig['Alert']['alarm_interval'];
	
	$JsonArr['email']['email_alert'] = $thermoConfig['Email']['email_alert'];
	$JsonArr['email']['server'] = $thermoConfig['Email']['server'];
	$JsonArr['email']['auth'] = $thermoConfig['Email']['auth'];
	$JsonArr['email']['starttls'] = $thermoConfig['Email']['starttls'];
	$JsonArr['email']['username'] = $thermoConfig['Email']['username'];
	$JsonArr['email']['password'] = $thermoConfig['Email']['password'];
	$JsonArr['email']['email_from'] = $thermoConfig['Email']['email_from'];
	$JsonArr['email']['email_to'] = $thermoConfig['Email']['email_to'];
	$JsonArr['email']['email_subject'] = $thermoConfig['Email']['email_subject'];
	
	
	return $JsonArr;
}
//-----------------------------------------------------------------------------
?>