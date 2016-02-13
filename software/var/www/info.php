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

<div id="info_site">
	<div id="info_site_left">
		<h1><?php echo $title; ?></h1>
		<p>ein Projekt der BBQ-Community</p>
		<br>
		<p>Idee, Hardware und Backend (C) 2013-2016 by </p><p>&#10026; <b>Armin Thinnes</b> &#10026;</p>
		<hr class="linie">
		<p>Web-Frontend (C) 2013-2016 by </p><p>&#10026; <b>Florian Riedl</b> &#10026;</p>
		<hr class="linie">
		<p>Watchdog &amp; Pitmaster (C) 2013-2015 by</p><p>&#10026; <b>Joe16</b> &#10026;</p>
		<hr class="linie">
		<p>Display &amp; Pitmaster (C) 2015-2016 by</p><p>&#10026; <b>Bj&ouml;rn</b> &#10026;</p>
		<hr class="linie">
		<p>Grafik (C) 2013 by</p><p>&#10026; <b>Michael Spanel</b> &#10026;</p>
		<hr class="linie">
		<p>PCB Design und Layout (C) 2013-2015 by </p><p>&#10026; <b>Grillprophet</b> &#10026;</p>
		<hr class="linie">
		<p>Display Design &amp; PCB v3 Mini(C) 2015-2016 by </p><p>&#10026; <b>Alexander Sch&auml;fer</b> &#10026;</p>
	</div>
	<div id="info_site_right">
		<h1>Information</h1>
		<p>&nbsp;</p>
		<br>
		<p>Software Version: <b><?php if (isset($_SESSION["webGUIversion"])) {echo $_SESSION["webGUIversion"];}?></b></p>
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
<?php
include("".$document_root."/footer.php");
?>

	
