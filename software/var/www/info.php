<?php
	session_start();
	$message = "";
	$document_root = getenv('DOCUMENT_ROOT');
	include("".$document_root."/header.php");
	if (!isset($_SESSION["current_temp"])) {
		include("function.php");
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}

// ##################################################################################
?>
</div>
<style>
/* customizable snowflake styling */
.snowflake {
  color: #fff;
  font-size: 1em;
  font-family: Arial;
  text-shadow: 0 0 1px #000;
}

@-webkit-keyframes snowflakes-fall{0%{top:-10%}100%{top:100%}}@-webkit-keyframes snowflakes-shake{0%{-webkit-transform:translateX(0px);transform:translateX(0px)}50%{-webkit-transform:translateX(80px);transform:translateX(80px)}100%{-webkit-transform:translateX(0px);transform:translateX(0px)}}@keyframes snowflakes-fall{0%{top:-10%}100%{top:100%}}@keyframes snowflakes-shake{0%{transform:translateX(0px)}50%{transform:translateX(80px)}100%{transform:translateX(0px)}}.snowflake{position:fixed;top:-10%;z-index:9999;-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;user-select:none;cursor:default;-webkit-animation-name:snowflakes-fall,snowflakes-shake;-webkit-animation-duration:10s,3s;-webkit-animation-timing-function:linear,ease-in-out;-webkit-animation-iteration-count:infinite,infinite;-webkit-animation-play-state:running,running;animation-name:snowflakes-fall,snowflakes-shake;animation-duration:10s,3s;animation-timing-function:linear,ease-in-out;animation-iteration-count:infinite,infinite;animation-play-state:running,running}.snowflake:nth-of-type(0){left:1%;-webkit-animation-delay:0s,0s;animation-delay:0s,0s}.snowflake:nth-of-type(1){left:10%;-webkit-animation-delay:1s,1s;animation-delay:1s,1s}.snowflake:nth-of-type(2){left:20%;-webkit-animation-delay:6s,.5s;animation-delay:6s,.5s}.snowflake:nth-of-type(3){left:30%;-webkit-animation-delay:4s,2s;animation-delay:4s,2s}.snowflake:nth-of-type(4){left:40%;-webkit-animation-delay:2s,2s;animation-delay:2s,2s}.snowflake:nth-of-type(5){left:50%;-webkit-animation-delay:8s,3s;animation-delay:8s,3s}.snowflake:nth-of-type(6){left:60%;-webkit-animation-delay:6s,2s;animation-delay:6s,2s}.snowflake:nth-of-type(7){left:70%;-webkit-animation-delay:2.5s,1s;animation-delay:2.5s,1s}.snowflake:nth-of-type(8){left:80%;-webkit-animation-delay:1s,0s;animation-delay:1s,0s}.snowflake:nth-of-type(9){left:90%;-webkit-animation-delay:3s,1.5s;animation-delay:3s,1.5s}
</style>
<div class="snowflakes" aria-hidden="true">
	<?php
	$i = 1;
	while ($i <= 2)
	{
		echo '<div class="snowflake"><FONT SIZE="7">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="6">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="5">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="4">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="3">&#10052;</FONT></div>';
		$i++;            // Wert wird um 1 erh?ht
	}
	?>
</div>
<div id="info_site">
	<div id="info_site_left">
		<h1><?php echo $title; ?></h1>
		<p>ein Projekt der BBQ-Community</p>
		<br>
		<p>Idee, Hardware und Backend (C) 2013-2015 by </p><p>&#10026; <b>Armin Thinnes</b> &#10026;</p>
		<hr class="linie">
		<p>Web-Frontend (C) 2013-2015 by </p><p>&#10026; <b>Florian Riedl</b> &#10026;</p>
		<hr class="linie">
		<p>Watchdog &amp; Pitmaster (C) 2013-2015 by</p><p>&#10026; <b>Joe16</b> &#10026;</p>
		<hr class="linie">
		<p>Display &amp; Pitmaster (C) 2015 by</p><p>&#10026; <b>Bj&ouml;rn</b> &#10026;</p>
		<hr class="linie">
		<p>Grafik (C) 2013 by</p><p>&#10026; <b>Michael Spanel</b> &#10026;</p>
		<hr class="linie">
		<p>PCB Design und Layout (C) 2013-2015 by </p><p>&#10026; <b>Grillprophet</b> &#10026;</p>
		<hr class="linie">
		<p>Display Design (C) 2015 by </p><p>&#10026; <b>Alexander Sch&auml;fer</b> &#10026;</p>
		<?php
		//<p><a href="http://www.a-thinnes.de/wlanthermometer" target=_blank>Aktuelles Repository</a></p>
		//<p><b><a href="http://www.grillsportverein.de/forum/eigenbauten/wlan-thermometer-selbst-bauen-mit-raspberry-pi-181768.html" target=_blank> Communitythread bei Grillsportverein </a></b></p>
		//<p><a href="mailto:wlanthermo@a-thinnes.de?subject=Anfrage zum WLAN-Thermometer">Email-Kontakt</a></p>
		//<h1>Gut Glut!</h1>
		?>
	</div>
	<div id="info_site_right">
		<h1>Information</h1>
		<p>&nbsp;</p>
		<br>
		<p>Backend: <b><?php if (isset($_SESSION["webGUIversion"])) {echo $_SESSION["webGUIversion"];}?></b> Frontend: <b><?php if (isset($_SESSION["webGUIversion"])) {echo $_SESSION["webGUIversion"];}?></b></p>
		<br>
		<br>
		<hr class="linie">
		<?php
		if ($_SESSION["checkUpdate"] == "True"){
			echo "<p>&#10026; <b>Update:</b> &#10026;</p>";	
			if ($_SESSION["updateAvailable"] == "False"){
				echo "<p>keine neuen Updates vorhanden</p>";
				echo '<hr class="linie">';
			}elseif	($_SESSION["updateAvailable"] == "True"){
				echo "<p>neues Update verf&uuml;gbar</p>";
				echo '<hr class="linie">';
				echo '<p>Installierte Version: <b>';
				if (isset($_SESSION["webGUIversion"])) {
					echo $_SESSION["webGUIversion"];
				}
				echo '</b></p>';
				echo '<p>Aktuelle Version: <b>';
				if (isset($_SESSION["newversion"])) {
					echo $_SESSION["newversion"];
				}
				echo '</b></p>';
				echo '<hr class="linie">';
				echo '<form action="./control/update.php">';
				echo '<p><input class="button" type="submit" value="Aktualisieren"/></p>';
				echo '</form>';				
			}
		}
		?>
		<div id="info_site_gutglut"></div>	
	</div>
<div class="clear"></div>

</div>			
</style>
<div class="snowflakes" aria-hidden="true">
	<?php
	$i = 1;
	while ($i <= 2)
	{
		echo '<div class="snowflake"><FONT SIZE="7">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="6">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="5">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="4">&#10052;</FONT></div>';
		echo '<div class="snowflake"><FONT SIZE="3">&#10052;</FONT></div>';
		$i++;            // Wert wird um 1 erh?ht
	}
	?>
</div>
<?php
include("".$document_root."/footer.php");
?>

	
