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

//-----------------------------------------------------------------------------
//Time test:
/*
$before = microtime(true); //designer2k2 hack!
for ($i=0 ; $i<30 ; $i++) {
	getData();
}	
$after = microtime(true);
echo ($after-$before)/$i . " sec/perRun\n";

/*
1.20 sec full
/etc/sudoers.s/WLANThermo muss um /sbin/iwlist erweitert werden!
*/
//-----------------------------------------------------------------------------

header('Content-type:application/json;charset=utf-8');	
echo json_encode(getData(), JSON_UNESCAPED_SLASHES);

function getData(){
	
	$output = array();
	$output['Connect'] = true;
	$output['Scantime'] = time();
	
	//SSID:
	exec('iwconfig wlan0',$return);
	preg_match('/ESSID:\"([a-zA-Z0-9\s]+)\"/i',$return[0],$result);
	preg_match('/Signal Level=(-[0-9]+)/i',$return[5],$result2);
	$output['SSID'] = $result[1];
	$output['RSSI'] = intval($result2[1]);
	unset($return);
	unset($result);
	unset($result2);
	
	//IP:
	exec('ifconfig wlan0',$return);
	if ((preg_match('/inet addr:([0-9.]+)/i',$return[1],$result)) or (preg_match('/inet Adresse:([0-9.]+)/i',$return[1],$result))){
			$output['IP'] = $result[1];
	}
	unset($return);
	unset($result);
	
	//Scan wifi:
	exec('sudo iwlist wlan0 scan',$return);	
	$return = parse_iwlist($return);

	foreach($return as $key => $value){
		if (substr($value['ssid'],0,5) != '\\x00\\')
		{
			$output['Scan'][$key]['SSID'] = $value['ssid'];
			$output['Scan'][$key]['RSSI'] = intval($value['rssi']);
			$output['Scan'][$key]['Enc'] = $value['encryption']==true ? 1 : 7;
		}
	}
	
	//Finish
	return $output;
}

function parse_iwlist($arLines)
    {	
        if (count($arLines) == 1) {
            return array();
        }
        $bStandaloneRates = false;
        $arCells      = array();
        $nCurrentCell = -1;
        $nCount       = count($arLines);
        for ($nA = 1; $nA < $nCount; $nA++) {
            $strLine = trim($arLines[$nA]);
            if ($strLine == '') {
                continue;
            }
            if (substr($strLine, 0, 4) == 'Cell') {
                $nCurrentCell++;
                $nCell = substr($strLine, 5, strpos($strLine, ' ', 5) - 5);
                $arCells[$nCurrentCell]['cell'] = $nCell;
                $strLine = substr($strLine, strpos($strLine, '- ') + 2);
            }
            $nPos       = strpos($strLine, ':');
            $nPosEquals = strpos($strLine, '=');
            if ($nPosEquals !== false && ($nPos === false || $nPosEquals < $nPos)) {
                $nPos = $nPosEquals;
            }
            $nPos++;
            $strId    = strtolower(substr($strLine, 0, $nPos - 1));
            $strValue = trim(substr($strLine, $nPos));
            switch ($strId) {
            case 'address':
                $arCells[$nCurrentCell]['mac'] = $strValue;
                break;
            case 'essid':
                if ($strValue[0] == '"') {
                    $arCells[$nCurrentCell]['ssid'] = substr($strValue, 1, -1);
                } else {
                    $arCells[$nCurrentCell]['ssid'] = $strValue;
                }
                break;
            case 'encryption key':
                if ($strValue == 'on') {
                    $arCells[$nCurrentCell]['encryption'] = true;
                } else {
				$arCells[$nCurrentCell]['encryption'] = false;
                }
                break;
            case 'mode':
                if (strtolower($strValue) == 'master') {
                    $arCells[$nCurrentCell]['mode'] = 'master';
                } else {
                    $arCells[$nCurrentCell]['mode'] = 'ad-hoc';
                }
                break;
            case 'signal level':
                $arCells[$nCurrentCell]['rssi'] = substr($strValue, 0, strpos($strValue, ' '));
                break;
            case 'quality':
                $arData = explode('  ', $strValue);
                $arCells[$nCurrentCell]['quality'] = $arData[0];
                if (trim($arData[1]) != '') {
                    $arLines[$nA] = $arData[1];
                    $nA--;
                    if (isset($arData[2])) {
                        $arLines[$nA - 1] = $arData[1];
                        $nA--;
                    }
                }
                break;
            default:
                break;
            }
        }
        return $arCells;
    }

?>