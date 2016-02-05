<?php
$directory_log = './thermolog/';
$directory_plot = './thermoplot/';
	
if(isset ($_POST['id']) AND isset ($_POST['id'])) { 

	$umlaute = array("/ä/","/ö/","/ü/","/Ä/","/Ö/","/Ü/","/ß/");
	$replace = array("ae","oe","ue","Ae","Oe","Ue","ss");
	
	$current_logfilename = ''.$directory_log.''.$_POST['id'].'';	//Alter Name des Logfile's ohne .csv
	$new_logfilename = $_POST['value'];
	$new_logfilename = preg_replace($umlaute, $replace, $new_logfilename); 
	$new_logfilename = preg_replace("/[^a-zA-Z0-9_\-]/","",$new_logfilename);
	//$new_logfilename = preg_replace("/[^a-zA-Z0-9_\-\. ]/","",$new_logfilename);
	$new_logfilename = ''.$directory_log.$new_logfilename.'.csv';

	$current_plotfilename = $_POST['id'];	//Alter Name der PlotGrafik	
	$current_plotfilename = ''.$directory_plot.''.substr($current_plotfilename, 0, -4).'.png';
	
	$new_plotfilename = $_POST['value'];
	$new_plotfilename = preg_replace($umlaute, $replace, $new_plotfilename); 
	$new_plotfilename = preg_replace("/[^a-zA-Z0-9_\-]/","",$new_plotfilename);
	$new_plotfilename = ''.$directory_plot.''.$new_plotfilename.'.png';
	
	if (file_exists(iconv("UTF-8", "ISO-8859-1", $current_logfilename))) {
		rename(iconv("UTF-8", "ISO-8859-1", $current_logfilename) , iconv("UTF-8", "ISO-8859-1", $new_logfilename));
		echo $_POST['value'];
		if (file_exists(iconv("UTF-8", "ISO-8859-1", $current_plotfilename))) {
			rename(iconv("UTF-8", "ISO-8859-1", $current_plotfilename) , iconv("UTF-8", "ISO-8859-1", $new_plotfilename));
		}
	}else{
		echo "Fehler...";
	}
}

?>