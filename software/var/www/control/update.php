<?php
	session_start();
	$message = "";
	$document_root = getenv('DOCUMENT_ROOT');
	include("../function.php");
	include("../header.php");
	$inipath = '../conf/WLANThermo.conf';	
	if (!isset($_SESSION["current_temp"])) {
		$message .= "Variable - Config neu einlesen\n";
		session("../conf/WLANThermo.conf");
	}
	if((file_exists('../tmp/update')) OR (file_exists('../tmp/nextionupdatelog'))){
		echo '<div id="info_site">';
		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>Das Update wurde bereits gestartet...</h2></body>";
		echo '</div>';
		exit;
	}
	if ((!isset($_SESSION["newversion"])) and (!isset($_SESSION["nextionupdate"]))){
		echo '<div id="info_site">';
		echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>keine neuen Updates vorhanden...</h2></body>";
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
if(isset($_POST["back"])) {
	echo "<div class=\"infofield\">";
	 echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>Verlassen der Seite ohne Update zu installieren!...</h2></body>";
	echo "</div>";

}elseif(isset($_POST["update_confirm_pwd"])){

	//echo nl2br(print_r($_POST,true));
	//echo "Passwort";
	$pwderror = "";
	$pwd1 = $_POST["pwd1"];
	$pwd2 = $_POST["pwd2"];
	If ((strlen($pwd1) < "5") or (strlen($pwd2) < "5")){
		$pwderror = "1"; 
		//echo "Passwort zu kurz";
	}
	If ($pwd1 !== $pwd2) {
		//echo " Passwort ungleich";
		$pwderror = "2";
	}
	If (($pwd1 !== $pwd2) and ((strlen($pwd1) < "5") or (strlen($pwd2) < "5"))){
		$pwderror = "3";
	}
	If (empty($pwderror)){
		?>
		<div id="info_site">
			<h1>Update Installieren</h1>
			<br>
			<?php
			//$datei = fopen("../tmp/update","w");
			//fwrite($datei, $pwd1);
			//fclose($datei);
			exec('echo "'.$pwd1.'" > /var/www/tmp/update');
			if(file_exists('../tmp/update')){
				if(get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
				$ini = getConfig("../conf/WLANThermo.conf", ";");  // dabei ist ; das zeichen für einen kommentar.
				$ini['ToDo']['start_update'] = "True";
				write_ini($inipath, $ini);
				//exec("/usr/bin/touch /var/www/tmp/update",$output);
				echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>Das Update wird nun Installiert...</h2></body>";
			}else{
				echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>Keine Schreibrechte auf /var/www/tmp...</h2></body>";
			}
			?>
		</div>
		<?php
	}else{
	?>
	<form action="./update.php" method="POST" >
	<div id="info_site">
		<h1>Update Installieren</h1>
		<p> bitte geben Sie ein Kennwort f&uuml;r den gesch&uuml;tzten Bereich ein</p>
		<br>
		<?php
			if ($pwderror == "1"){
				echo "<b>Die eingegebenen Kennw&ouml;rter sind zu kurz</b><br>";
			}
			if ($pwderror == "2"){
				echo "<b>Die eingegebenen Kennw&ouml;rter sind ungleich </b><br>";
			}
			if ($pwderror == "3"){
				echo "<b>Die eingegebenen Kennw&ouml;rter sind zu kurz</b><br>";
				echo "<b>Die eingegebenen Kennw&ouml;rter sind ungleich </b><br>";
			}
		?>
		<table border="0">
		<br>
		<tr>
			<td align="left" >
				<b>Kennwort:</b>
			</td>
			<td>
				&nbsp;&nbsp;<input type="password" name="pwd1" value="" size="25" maxlength="50">
			</td>
		</tr>
		<tr>
			<td align="left" >
				<b>Kennwort wiederholen:</b>
			</td>
			<td>
				&nbsp;&nbsp;<input type="password" name="pwd2" value="" size="25" maxlength="50">
			</td>
		</tr>
		</table>
		<br>
		<p>Wollen Sie das Update installieren?</p>			
	</div>
	<br>						
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="update_confirm_pwd"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>	
	<br>	
	<?php		
	}
}elseif(isset($_POST["update_confirm"])){
	?>
	<form action="./update.php" method="POST" >
	<div id="info_site">
		<h1>Update Installieren</h1>
		<p> Bitte geben Sie ein Kennwort f&uuml;r den gesch&uuml;tzten Bereich ein</p>
		<br>
		<table border="0">
		<tr>
			<td align="left" >
				<b>Kennwort:</b>
			</td>
			<td>
				&nbsp;&nbsp;<input type="password" name="pwd1" value="" size="25" maxlength="50">
			</td>
		</tr>
		<tr>
			<td align="left" >
				<b>Kennwort wiederholen:</b>
			</td>
			<td>
				&nbsp;&nbsp;<input type="password" name="pwd2" value="" size="25" maxlength="50">
			</td>
		</tr>
		</table>
		<br>
		<p>Wollen Sie das Update Installieren?</p>			
	</div>
	<br>						
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="update_confirm_pwd"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>	
	<br>	
	<?php
}elseif(isset($_POST["update_pwd_false"])){
	?>
	<div id="info_site">
		<h1>Update Installieren</h1>
		<p> Bitte geben Sie ein Kennwort f&uuml;r den gesch&uuml;tzten Bereich ein</p>
		<br>
		<p>Die eingegebenen Kennwörter sind nicht gleich!</p>
		<table border="0">
		<tr>
			<td align="left" >
				<b>Kennwort:</b>
			</td>
			<td>
				&nbsp;&nbsp;<input type="password" name="pwd1" size="25" maxlength="50">
			</td>
		</tr>
		<tr>
			<td align="left" >
				<b>Kennwort wiederholen:</b>
			</td>
			<td>
				&nbsp;&nbsp;<input type="password" name="pwd2" size="25" maxlength="50">
			</td>
		</tr>
		</table>
		<br>
		<p>Wollen Sie das Update installieren?</p>			
	</div>
	<br>
		<form action="./control/update.php" method="post" >						
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="update_confirm_pwd"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>	
	<br>	
	<?php
	
}elseif(isset($_POST["update_nextion"])){
	?>
	<div id="info_site">
		<h1>Update Installieren</h1>
		<p> f&uuml;r das NEXTION Display wurde ein neues Update gefunden</p>
		<br>
		<br>
		<br>
		<p>Wollen Sie das Update installieren?</p>	
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
}elseif(isset($_POST["nextion_update_confirm"])){
?>
		<div id="info_site">
			<h1>Update Installieren</h1>
			<br>
			<?php
				exec("sudo /usr/sbin/wlt_2_updatenextion.sh /usr/share/WLANThermo/nextion/ > /var/www/tmp/error.txt &",$output);
				echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"> </head> <body> <h2>Das Update wird nun Installiert...</h2></body>";
			?>
		</div>
		<?php

}else{
// ####################################################################################################################################
?>
</div>
	<div id="info_site">
		<h1>Update Installieren</h1>
		<p> f&uuml;r das WLANThermometer wurde ein neues Update gefunden</p>
		<br>
		<p>Installierte Version: <b><?php if (isset($_SESSION["webGUIversion"])) {echo $_SESSION["webGUIversion"];}?></b></p>
		<p>Aktuelle Version: <b><?php if (isset($_SESSION["newversion"])) {echo $_SESSION["newversion"];}?></b></p>
		<br>
		<br>
		<p>Wollen Sie das Update installieren?</p>	
		<form action="./update.php" method="POST" >							
				<table align="center" width="80%">
					<tr>
						<td width="20%"></td>
						<td align="center"> 
							<input type="submit" class=button_yes name="update_confirm"  value="">
							<input type="submit" class=button_back name="back"  value=""> 
						</td>
						<td width="20%"></td>
					</tr>
				</table>
		</form>			
	</div>

<div class="clear"></div>
</div>
<?php
include("".$document_root."/footer.php");
}
?>