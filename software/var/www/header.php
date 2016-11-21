<?php
error_reporting(E_ALL);
ini_set('display_errors', TRUE);
$_SESSION["webGUIversion"] = "V2.5.0-0";
$title = "WLAN Thermometer";
$document_root = getenv('DOCUMENT_ROOT');
include("gettext.php");
if (isset($_SESSION["locale"])){	
	set_locale($_SESSION["locale"]);
}else{
	set_locale("de_DE.utf8");
	setlocale(LC_ALL, 'de_DE.utf8');
}

?>
<!DOCTYPE html>
<html lang="de">
<head>
	<meta charset="utf-8">
	<title><?php echo ''.$title.' ('.$_SESSION["webGUIversion"].')';?></title>
	<link rel="stylesheet" type="text/css" href="../css/style.css">
	<link rel="stylesheet" href="../css/jquery.fancybox.css" type="text/css" media="screen">
	<link rel="shortcut icon" type="image/x-icon" href="../images/icons16x16/thermo.png">
	<link rel="apple-touch-icon" href="images/apple-touch-icon-57x57-precomposed.png">	
    <script type="text/javascript" src="../js/jquery.min.js">				</script>
	<script type="text/javascript" src="../js/jquery.session.js">			</script>
	<script type="text/javascript" src="../js/jquery.fancybox.js">			</script>
	<script type="text/javascript" src="../js/jquery.fancybox.script.js">	</script>
	<script type="text/javascript" src="../js/jquery.div.slide.js">			</script>
	<script type="text/javascript" src="../js/jquery.jeditable.js">			</script>
	<script type="text/javascript" src="../js/function.js">					</script>
	<script type="text/Javascript" src="../js/wifi_functions.js">			</script>
	<script type="text/javascript" src="../js/jquery.image.reload.js">		</script>	
<?php
//###################################################################################
//Variablen etc. für das Menü -------------------------------------------------------
//###################################################################################
	$plot_start = 'style="display:none"';
	$webcam_start = 'style="display:none"';
	$raspicam_start = 'style="display:none"';
	if (isset($_SESSION["updateAvailable"])) {
		if ((($_SESSION["updateAvailable"] == "True") AND ($_SESSION['checkUpdate'] == "True")) OR (isset($_SESSION["nextionupdate"]))){
			echo '<script>$(function() { showUpdate();});</script>';
		}else{		
			echo '<script>$(function() { hideUpdate();});</script>';
		}	
	}else{
		echo '<script>$(function() { hideUpdate();});</script>';
	}
	if(!strpos($_SERVER["PHP_SELF"], "index.php") === false){
		if ($_SESSION["plot_start"] == "True"){
			$plot_start = 'style="display:inline"';
		}
		if ($_SESSION["webcam_start"] == "True"){
			$webcam_start = 'style="display:inline"';
		}
		if ($_SESSION["raspicam_start"] == "True"){
			$raspicam_start = 'style="display:inline"';
		}
	}
?>
</head>
<body onload="bildreload();garden()">
	<div id="wrapper">
		<div id="header">
			<div id="header_logo"><div class="header_link"><a href="../index.php"></a></div></div>
		</div>
		<div id="header_title"></div>
			<div id="mainmenu">
				<nav>
					<ul>
						<li class = "shutdown_menu">
							<a href="#" class="mainmenu"><img src="../images/icons32x32/shutdown.png" alt="Home" title="Shutdown"></a>
							<ul>
								<li><a href="../control/reboot.php"><b><?php echo gettext("Reboot");?></b></a></li>
								<li><a href="../control/shutdown.php"><b><?php echo gettext("Shutdown");?></b></a></li>
							</ul>
						</li>
						<li>
							<a href="../index.php" class="mainmenu"><img src="../images/icons32x32/home.png" alt="Home" title="Home"></a>
						</li>				
						<li>
							<a href="../info.php" class="mainmenu"><img src="../images/icons32x32/info.png" alt="Info" title="Info"></a>
						</li>
						<li>
							<a href="../control/wifi.php" class="mainmenu"><img src="../images/icons32x32/wifi.png" alt="<?php echo gettext("WiFi Settings");?>" title="<?php echo gettext("WiFi Settings");?>"></a>
						</li>
						<li>
							<a href="../control/config.php" class="mainmenu"><img src="../images/icons32x32/thermo.png" alt="<?php echo gettext("Settings");?>" title="<?php echo gettext("Settings");?>"></a>
						</li>	
						<li>
							<a href="../thermolog.php" class="mainmenu"><img src="../images/icons32x32/log.png" alt="<?php echo gettext("Log File");?>" title="<?php echo gettext("Log File");?>"></a>
						</li>
						<li <?php echo $raspicam_start;?>>
							<a href="#" id="raspicam_button" class="mainmenu"><img src="../images/icons32x32/raspicam.png" alt="RaspiCam" title="RaspiCam"></a>
						</li>
						<li <?php echo $webcam_start;?>>
							<a href="#" id="webcam_button" class="mainmenu"><img src="../images/icons32x32/webcam.png" alt="WebCam" title="WebCam"></a>
						</li>
						<li	<?php echo $plot_start;?>>
							<a href="#" id="ThermoPlot_button" class="mainmenu"><img src="../images/icons32x32/chart.png" alt="<?php echo gettext("Temperature Graph");?>" title="<?php echo gettext("Temperature Graph");?>"></a>
						</li>				
						<li>
							<div id="newlogmenu"><a href="../control/new_log_file.php" class="mainmenu" style="text-align:left;"><b><?php echo gettext("Create New Log File");?></b></a></div>
						</li>
					</ul>
				</nav>
			</div>
			<div class="clear"></div>
			<div id="content">
				<div class="inner">
