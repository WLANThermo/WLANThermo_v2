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

	include('./function.php');
	$inipath = './conf/WLANThermo.conf';

	if(file_exists($inipath)){
		if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
		$ini = getConfig($inipath, ";");  // dabei ist ; das zeichen für einen kommentar. kann geändert werden.
	}else{
		echo(false);
		die();
	}


	$ini['ToDo']['create_new_log'] = "True"; // Parameter für neues Logfile setzen
	write_ini($inipath, $ini);	// Schreiben der WLANThermo.conf

	echo (true);

?>
