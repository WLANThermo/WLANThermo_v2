<?php
	session_start();
	$message = "";
	$document_root = getenv('DOCUMENT_ROOT');
	require_once("../function.php");
	include("../header.php");
	$inipath = '../conf/WLANThermo.conf';	
	if (!isset($_SESSION["current_temp"])) {
		$message .= gettext("Variable - Config neu einlesen\n");
		session("../conf/WLANThermo.conf");
	}
	if((file_exists('../tmp/update.log')) OR (file_exists('../tmp/nextionupdatelog'))){
		echo '<div id="info_site">';
		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>" . gettext("Das Update wurde bereits gestartet...") . "</h2></body>";
		echo '</div>';
		exit;
	}
?>
		<script>
		$(function() {	

					$.session.set("ToggleStatusPlot", "NULL");
					$.session.set("ToggleStatusWebcam", "NULL");
					$.session.set("ToggleStatusraspicam", "NULL");
		});
		</script>
<?php
if (isset($_POST["back"])) {
	echo "<div class=\"infofield\">";
	 echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>" . gettext("Verlassen der Seite ohne Update zu installieren!...") . "</h2></body>";
	echo "</div>";
} elseif (isset($_POST["update_step1"])) {
	?>
	<form action="./update.php" method="POST" >
	<div id="info_site">
		<h1><?php echo gettext("Update Installieren");?></h1>
		<p><?php echo gettext("Wollen Sie das Update Installieren?");?></p>			
	</div>
	<br>						
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="update_step2"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>	
	<br>	
	<?php
} elseif (isset($_POST["update_step2"])) {
	?>
		<div id="info_site">
			<h1><?php echo gettext("Update Installieren");?></h1>
			<br>
			<?php
			$ini = getConfig("../conf/WLANThermo.conf", ";");
			$ini['ToDo']['start_system_update'] = "True";
			write_ini($inipath, $ini);
			echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>" . gettext("Das Update wird nun Installiert...") . "</h2></body>";
			?>
		</div>
	<?php
} elseif (isset($_POST["wlanthermo_update_step1"])) {
	?>
	<form action="./update.php" method="POST" >
	<div id="info_site">
		<h1><?php echo gettext("Update Installieren");?></h1>
		<p><?php echo gettext("Wollen Sie das Update Installieren?");?></p>			
	</div>
	<br>						
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="wlanthermo_update_step2"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>	
	<br>	
	<?php
} elseif (isset($_POST["wlanthermo_update_step2"])) {
	?>
		<div id="info_site">
			<h1><?php echo gettext("Update Installieren");?></h1>
			<br>
			<?php
			$ini = getConfig("../conf/WLANThermo.conf", ";");
			$ini['ToDo']['start_full_update'] = "True";
			write_ini($inipath, $ini);
			echo "<head><meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>" . gettext("Das Update wird nun Installiert...") . "</h2></body>";
			?>
		</div>
	<?php
} elseif (isset($_POST["update_nextion"])) {
	?>
	<div id="info_site">
		<h1><?php echo gettext("Update Installieren");?></h1>
		<p><?php echo gettext("f&uuml;r das NEXTION Display wurde ein neues Update gefunden");?></p>
		<br>
		<p><?php echo gettext("Wollen Sie das Update installieren?");?></p>	
		<form action="./update.php" method="POST" >							
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="nextion_update_confirm"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>			
	</div>
	<?php
} elseif(isset($_POST["nextion_update_confirm"])) {
?>
		<div id="info_site">
			<h1><?php echo gettext("Update Installieren");?></h1>
			<br>
			<?php
				exec("sudo /usr/sbin/wlt_2_updatenextion.sh /usr/share/WLANThermo/nextion/ {$_SESSION['nextion_variant']} > /var/www/tmp/error.txt &",$output);
				echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>" . gettext("Das Update wird nun Installiert...") . "</h2></body>";
			?>
		</div>
		<?php

} else {
// ####################################################################################################################################
		if ($_SESSION["checkUpdate"] == "True"){
			$updates = update_check();
			$updates_shown = False;
			if ($updates === False){
				?>
	<div id="info_site">
		<h1><?php echo gettext("Update Installieren");?></h1>
		<p><?php echo gettext("Fehler beim prüfen auf Updates!");?></p>
	</div>
				<?php
			} else {
				if (isset($updates['system']['available']) && $updates['system']['available'] === True) {
					$updates_shown = True;
					?>
	<div id="info_site">
		<h1><?php echo gettext("Update Installieren");?></h1>
		<p><?php echo gettext("f&uuml;r das Betriebssystem wurden neue Updates gefunden");?></p>
		<br>
		<p><?php echo gettext("Zu aktualisierende Pakete:");?> <b><?php if (isset($updates['system']['count'])) {echo $updates['system']['count'];}?></b></p>
		<br>
		<p><?php echo gettext("Wollen Sie das Update installieren?");?></p>	
		<form action="./update.php" method="POST" >							
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="update_step1"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>
	</div>
					<?php
				}
				if (isset($updates['wlanthermo']['available']) && $updates['wlanthermo']['available'] === True) {
					$updates_shown = True;
					?>
	<div id="info_site">
		<h1><?php echo gettext("Update Installieren");?></h1>
		<p><?php echo gettext("f&uuml;r das WLANThermometer wurde ein neues Update gefunden");?></p>
		<br>
		<p><?php echo gettext("Installierte Version:");?> <b><?php if (isset($updates['wlanthermo']['oldversion'])) {echo $updates['wlanthermo']['oldversion'];}?></b></p>
		<p><?php echo gettext("Aktuelle Version:");?> <b><?php if (isset($updates['wlanthermo']['newversion'])) {echo $updates['wlanthermo']['newversion'];}?></b></p>
		<br>
		<p><?php echo gettext("Wollen Sie das Update installieren?");?></p>
		<p><?php echo gettext("Dieses Update schließt automatisch das Systemupdate mit ein.");?></p>
		<form action="./update.php" method="POST" >							
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="wlanthermo_update_step1"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>
	</div>
					<?php
				}
			}
		} else {
			?>
	<div id="info_site">
		<h1><?php echo gettext("Update Installieren");?></h1>
		<p><?php echo gettext("Updates für das WLANThermo wurden deaktiviert");?></p>
	</div>
			<?php
		}
?>
</div>

<div class="clear"></div>
</div>
<?php
include("".$document_root."/footer.php");
}
?>
