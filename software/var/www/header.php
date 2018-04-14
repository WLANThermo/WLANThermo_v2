<?php
error_reporting(E_ALL);
ini_set('display_errors', TRUE);
// Version is set by build script
$_SESSION["webGUIversion"] = "XXX_VERSION_XXX";
$title = "WLANThermo";
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
	<meta name="apple-mobile-web-app-capable" content="yes" />
	<meta name="apple-mobile-web-app-title" content="WlanThermo">
	<meta name="apple-mobile-web-app-status-bar-style" content="black" />
	<title></title>
	<link rel="stylesheet" type="text/css" href="../css/style.css">	
    <script type="text/javascript" src="../js/jquery.min.js">				</script>
	<script type="text/javascript" src="../js/jquery.session.js">			</script>
	<script type="text/javascript" src="../js/function.js">					</script>

</head>
<body onload="bildreload()">
	<div id="wrapper">
		<div id="header">
			<div id="header_logo"><div class="header_link"><a href="../index.php"></a></div></div>
		</div>
		<div id="header_title"></div>
			<div id="mainmenu">
			</div>
			<div class="clear"></div>
			<div id="content">
				<div class="inner">
