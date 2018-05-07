<?php
	session_start();
	$message = "";
	$document_root = getenv('DOCUMENT_ROOT');
	include("".$document_root."/header.php");
	include("function.php");
	if (!isset($_SESSION["current_temp"])) {
		$message .= "Variable - Config neu einlesen\n";
		session("./conf/WLANThermo.conf");
	}

// ##################################################################################
?>
</div>

<div id="info_site">
	<div id="info_site_left">
		<h1><?php echo $title; ?></h1>
		<p><?php echo gettext("a WLANThermo community project");?></p>
		<br>
		<p>Idee, Hardware &amp; Backend (C) 2013-2016 by </p><p>&#10026; <b>Armin Thinnes</b> &#10026;</p>
		<hr class="linie">
		<p>Web-Frontend (C) 2013-2016 by </p><p>&#10026; <b>Florian Riedl</b> &#10026;</p>
		<hr class="linie">
		<p>Watchdog &amp; Pitmaster (C) 2013-2015 by</p><p>&#10026; <b>Joe16</b> &#10026;</p>
		<hr class="linie">
		<p>Display &amp; Pitmaster (C) 2015-2018 by</p><p>&#10026; <b>Bj&ouml;rn</b> &#10026;</p>
		<hr class="linie">
		<p>Grafik (C) 2013 by</p><p>&#10026; <b>Michael Spanel</b> &#10026;</p>
		<hr class="linie">
		<p>PCB Design &amp; Layout (C) 2013-2015 by </p><p>&#10026; <b>Grillprophet</b> &#10026;</p>
		<hr class="linie">
		<p>Display Design &amp; PCB v3 Mini(C) 2015-2017 by </p><p>&#10026; <b>Alexander Sch&auml;fer</b> &#10026;</p>
	</div>
	<div id="info_site_right">
		<h1><?php echo gettext("Information");?></h1>
		<p><?php echo gettext("This software is licensed under the");?> <b><a href="LICENSE.txt" target="_blank">GPL</a></b> <?php echo gettext("License");?></p>
		<br>
		<p><?php echo gettext("Software version");?>: <b><?php if (isset($_SESSION["webGUIversion"])) {echo $_SESSION["webGUIversion"];}?></b></p>
		<p>&nbsp;</p>
		<hr class="linie">
		<?php
		if ($_SESSION["checkUpdate"] == "True"){
			$updates = update_check();
			$updates_shown = False;
			if ($updates === False) {
				echo "<p>&#10026; <b>".gettext("WLANThermo update").":</b> &#10026;</p>";
				echo "<p>".gettext("Error during update check, please wait 5min after boot!")."</p>";
				echo '<hr class="linie">';
			} else {
				if (isset($updates['system']['available']) && $updates['system']['available'] === True) {
					echo "<p>&#10026; <b>".gettext("WLANThermo update").":</b> &#10026;</p>";
					echo "<p>".gettext("System updates available")."</p>";
					echo '<p>'.gettext('Update count').': <b>';
					if (isset($updates['system']['count'])) {
						echo $updates['system']['count'];
					}
					echo '</b></p>';
					echo '<hr class="linie">';
					$updates_shown = True;
				}
				if (isset($updates['wlanthermo']['available']) && $updates['wlanthermo']['available'] === True) {
					echo "<p>&#10026; <b>".gettext("WLANThermo update").":</b> &#10026;</p>";
					echo "<p>".gettext("WLANThermo update available")."</p>";
					echo '<p>'.gettext('Version information:').'<b><br>';
					if (isset($updates['wlanthermo']['oldversion'])) {
						echo gettext('Old version: ') . $updates['wlanthermo']['oldversion'];
						echo '<br>';
						echo gettext('New version: ') . $updates['wlanthermo']['newversion'];
					}
					echo '</b></p>';
					echo '<hr class="linie">';
					$updates_shown = True;
				}
				echo '</b></p>';
				if ($updates_shown === True) {
					echo '<form action="./control/update.php">';
					echo '<p><input class="button" type="submit" value="'.gettext('Update').'"/></p>';
					echo '</form>';
                                        echo '<hr class="linie">';
				}
			}
		} else {
			echo "<p>&#10026; <b>".gettext("WLANThermo update").":</b> &#10026;</p>";
			echo "<p>".gettext("Update check disabled!")."</p>";
			echo '<hr class="linie">';
		}
		if	(isset($_SESSION["nextionupdate"])){
				
				echo "<p>&#10026; <b>Nextion Update:</b> &#10026;</p>";
				echo "<p>".gettext("new update available")."</p>";
				echo '</b></p>';
				echo '<hr class="linie">';
				echo '<form action="./control/update.php" method="post">';
				echo '<p><input class="button" type="submit" name="update_nextion" value="'.gettext('Update').'"/></p>';
				echo '</form>';
                                echo '<hr class="linie">';
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

	
