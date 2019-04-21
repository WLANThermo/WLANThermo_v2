<?php
session_start();

// ##################################################################################
// Files einbinden ------------------------------------------------------------------
// ##################################################################################

include("../header.php");
require_once("../function.php");
session("../conf/WLANThermo.conf");
$inipath = '../conf/WLANThermo.conf';

// gnuplot color names, to be converted to CSS color names by to_css_color($gnuplotcolor) if needed.
$plotcolors = array('green', 'red', 'blue', 'olive', 'magenta', 'yellow', 'violet', 'orange',
	'mediumpurple3', 'aquamarine', 'brown', 'plum', 'skyblue', 'orange-red', 'salmon',
	'black', 'dark-grey', 'purple', 'turquoise', 'khaki', 'dark-violet', 'seagreen', 'web-blue',
	'steelblue', 'gold', 'dark-green', 'midnight-blue', 'dark-khaki', 'dark-olivegreen',
	'pink', 'chartreuse', 'gray', 'slategrey');

$log_levels = array('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');

$app_devices=array('Companion' => '0'); 
// ##################################################################################
// Config-Files einlesen ------------------------------------------------------------
// ##################################################################################

if (get_magic_quotes_runtime()) set_magic_quotes_runtime(0); 
$ini = getConfig("../conf/WLANThermo.conf", ";");  // dabei ist ; das zeichen für einen kommentar.	
$sensor_ini = getConfig("../conf/sensor.conf", ";");  // dabei ist ; das zeichen für einen kommentar.

// ##################################################################################
// Hochgeladenes Config-Files einlesen ----------------------------------------------
// ##################################################################################

if (isset($_POST["upload_file"])) {
	if ($_FILES["configfile"]["error"] == UPLOAD_ERR_OK && $_FILES['configfile']['size'] != 0) {
		if (is_uploaded_file($_FILES['configfile']['tmp_name'])) {
			exec("/usr/bin/wlt_2_updateconfig.py {$_FILES['configfile']['tmp_name']} &> /var/www/tmp/updateconfig.log", $output);
			echo "<head> <meta http-equiv=\"refresh\" content=\"1;URL='config.php'\"> </head> <body> <h2>" . gettext("File has been processed...") . "</h2></body>";
    		} else {
			echo "<head> <meta http-equiv=\"refresh\" content=\"1;URL='config.php'\"> </head> <body> <h2>" . gettext("Error during file processing...") . "</h2></body>";
            }
	} else {
		echo "<head> <meta http-equiv=\"refresh\" content=\"1;URL='config.php'\"> </head> <body> <h2>" . gettext("Error during upload...") . "</h2></body>";
	}

// ##################################################################################
// Formular auswerten ---------------------------------------------------------------
// ##################################################################################	

} elseif(isset($_POST["save"])) {
	$error = "";				
	$restart = false;
	$restart_pit = false;
	$restart_pit2 = false;
	$new_logfile = false;
	$lcd_restart = false;

			for ($i = 0; $i < $_SESSION["channel_count"]; $i++){
				if($ini['ch_show']['ch'.$i] == "True"){
				
					// Überprüfen ob sich die Sensorenauswahl geändert hat (Restart)
					if($ini['Sensoren']['ch'.$i] !== $_POST['fuehler'.$i]){ 
						$ini['Sensoren']['ch'.$i] = $_POST['fuehler'.$i];
					}
					// Überprüfen ob sich der Messwiderstand geändert hat (Restart)
					if($ini['Messen']['messwiderstand'.$i] !== to_numeric($_POST['measuring_resistance'.$i])){ 
						$ini['Messen']['messwiderstand'.$i] = to_numeric($_POST['measuring_resistance'.$i]);
					}
					// Farben für den Plotter ändern --------------------------------
					$ini['plotter']['color_ch'.$i] = $_POST['plot_color'.$i];

					// Kanalbezeichnung ändern --------------------------------------
					$ini['ch_name']['ch_name'.$i] = $_POST['tch'.$i];
					
					// Temp "min" prüfen und Speichern ------------------------------
					$temp_min = to_numeric($_POST['temp_min'.$i]);
					if($temp_min > -40 && $temp_min < 380){
						$ini['temp_min']['temp_min'.$i] = $temp_min;
					}else{
						$ini['temp_min']['temp_min'.$i] = 0;
						$error .= "Die \"min\" Temperatur f&uuml;r \"".$_POST['tch'.$i]."\" liegt ausserhalb des G&uuml;ltigen Bereichs! ==> G&uuml;ltige Werte: -40 - 380Grad<br>";
					}
					
					// Temp "max" prüfen und Speichern ------------------------------
					$temp_max = to_numeric($_POST['temp_max'.$i]);
					if ($temp_max > -20 && $temp_max < 380) {
						$ini['temp_max']['temp_max'.$i] = $temp_max;
					}else{
						$ini['temp_max']['temp_max'.$i] = "200";
						$error .= "Die \"max\" Temperatur f&uuml;r \"".$_POST['tch'.$i]."\" liegt ausserhalb des G&uuml;ltigen Bereichs! ==> G&uuml;ltige Werte: -20 - 380Grad<br>";
					}						
					
					// Alarmierung prüfen und Speichern -----------------------------
					if(isset ($_POST['alert'.$i])) {
						$ini['web_alert']['ch'.$i] = "True";
					} else {
						$ini['web_alert']['ch'.$i] = "False";
					}
				}
				
				// ch_show prüfen und Speichern -------------------------------------
				if(isset ($_POST['ch_show'.$i])) {
					$ini['ch_show']['ch'.$i] = "True";
				} else {
					$ini['ch_show']['ch'.$i] = "False";
				}
			}
			
			// ######################################################################
			// Plot Einstellungen ---------------------------------------------------
			// ######################################################################
			
			// Plot-Dienst Starten/Stoppen 
			if(isset ($_POST['plot_start'])) { $ini['ToDo']['plot_start'] = "True"; } else { $ini['ToDo']['plot_start'] = "False";}
			
			// Pitansteuerung plotten 
			if(isset ($_POST['plot_pit'])) { $ini['plotter']['plot_pit'] = "True"; } else { $ini['plotter']['plot_pit'] = "False";}
			
			// Pitansteuerung 2 plotten
			if(isset ($_POST['plot_pit2'])) { $ini['plotter']['plot_pit2'] = "True"; } else { $ini['plotter']['plot_pit2'] = "False";}
			
			// Farben für den Plotter ändern 
			if (isset($_POST['color_pit'])) {
				$ini['plotter']['color_pit'] = $_POST['color_pit'];
			}
			
			// Farben für den Plotter ändern 
			if (isset($_POST['color_pitsoll'])) {
				$ini['plotter']['color_pitsoll'] = $_POST['color_pitsoll'];
			}
			
			// Farben für den Plotter ändern
			if (isset($_POST['color_pit2'])) {
				$ini['plotter']['color_pit2'] = $_POST['color_pit2'];
			}
				
			// Farben für den Plotter ändern
			if (isset($_POST['color_pit2soll'])) {
				$ini['plotter']['color_pit2soll'] = $_POST['color_pit2soll'];
			}
			
			// Plot-Dienst keyboxframe 
			if(isset ($_POST['keyboxframe'])) { $ini['plotter']['keyboxframe'] = "True"; } else { $ini['plotter']['keyboxframe'] = "False";}
			
			// Plotbereich MIN
			if (isset($_POST['plotbereich_min'])) {
				$ini['plotter']['plotbereich_min'] = $_POST['plotbereich_min'];
			}
			// Plotbereich MAX
			if (isset($_POST['plotbereich_max'])) {
				$ini['plotter']['plotbereich_max'] = $_POST['plotbereich_max'];
			}
			// Plotsize
			if (isset($_POST['plotsize'])) {
				$ini['plotter']['plotsize'] = $_POST['plotsize'];
			}
			// Plotname
			if (isset($_POST['plotname'])) {
				$ini['plotter']['plotname'] = $_POST['plotname'];
			}
			// Keybox Rahmen
			if (isset($_POST['keybox'])) {
				$ini['plotter']['keybox'] = $_POST['keybox'];
			}		
			// ######################################################################
			// Alarm Einstellungen --------------------------------------------------
			// ######################################################################
			
			// Template für Temperaturüberschreitung
			if (isset($_POST['alarm_high_template'])) {
				if($ini['Alert']['alarm_high_template'] !== $_POST['alarm_high_template']){
					$ini['Alert']['alarm_high_template'] = $_POST['alarm_high_template'];
				}
			}
			// Template für Temperaturunterschreitung
			if (isset($_POST['alarm_low_template'])) {
				if($ini['Alert']['alarm_low_template'] !== $_POST['alarm_low_template']){
					$ini['Alert']['alarm_low_template'] = $_POST['alarm_low_template'];
				}
			}
			// Template für Statusmeldungen
			if (isset($_POST['status_template'])) {
				if($ini['Alert']['status_template'] !== $_POST['status_template']){
					$ini['Alert']['status_template'] = $_POST['status_template'];
				}
			}
			// Template für die Nachricht
			if (isset($_POST['message_template'])) {
				if($ini['Alert']['message_template'] !== $_POST['message_template']){
					$ini['Alert']['message_template'] = $_POST['message_template'];
				}
			}
			// Intervall für Statusmeldungen
			if (isset($_POST['status_interval'])) {
				if($ini['Alert']['status_interval'] !== intval($_POST['status_interval'])){
					$ini['Alert']['status_interval'] = intval($_POST['status_interval']);
				}
			}
			// Intervall für Alarmmeldungen
			if (isset($_POST['alarm_interval'])) {
				if($ini['Alert']['alarm_interval'] !== intval($_POST['alarm_interval'])){
					$ini['Alert']['alarm_interval'] = intval($_POST['alarm_interval']);
				}
			}
			// ######################################################################
			// Email Einstellungen --------------------------------------------------
			// ######################################################################
			
			// Emailbenachrichtigung Aktivieren/Deaktivieren
			if(isset ($_POST['email'])) {$_POST['email'] = "True"; }else{ $_POST['email'] = "False";}
			if($ini['Email']['email_alert'] !== $_POST['email']){
				$ini['Email']['email_alert'] = $_POST['email'];
			}
			// Emailtls Aktivieren/Deaktivieren 
			if(isset ($_POST['starttls'])) {$_POST['starttls'] = "True"; }else{ $_POST['starttls'] = "False";}
			if($ini['Email']['starttls'] !== $_POST['starttls']){
				$ini['Email']['starttls'] = $_POST['starttls'];
			}
			// Email Authentifizierung Aktivieren/Deaktivieren
			if(isset ($_POST['auth_check'])) {$_POST['auth_check'] = "True"; }else{ $_POST['auth_check'] = "False";}
			if($ini['Email']['auth'] !== $_POST['auth_check']){
				$ini['Email']['auth'] = $_POST['auth_check'];
			}
			// Email Empfänger
			if (isset($_POST['email_to'])) {
				if($ini['Email']['email_to'] !== $_POST['email_to']){
					$ini['Email']['email_to'] = $_POST['email_to'];
				}
			}
			// Email Absender
			if (isset($_POST['email_from'])) {
				if($ini['Email']['email_from'] !== $_POST['email_from']){
					$ini['Email']['email_from'] = $_POST['email_from'];
				}
			}	
			// Email Betreff 
			if (isset($_POST['email_subject'])) {
				if($ini['Email']['email_subject'] !== $_POST['email_subject']){
					$ini['Email']['email_subject'] = $_POST['email_subject'];
				}
			}
			// Email Server
			if (isset($_POST['email_smtp'])) {
				if($ini['Email']['server'] !== $_POST['email_smtp']){
					$ini['Email']['server'] = $_POST['email_smtp'];
				}
			}
			// Email Passwort
			if (isset($_POST['email_password'])) {
				if($ini['Email']['password'] !== $_POST['email_password']){
					$ini['Email']['password'] = $_POST['email_password'];
				}
			}
			// Email Benutzername
			if (isset($_POST['email_username'])) {
				if($ini['Email']['username'] !== $_POST['email_username']){
					$ini['Email']['username'] = $_POST['email_username'];
				}			
			}
			
			// ######################################################################
			// Push Einstellungen --------------------------------------------------
			// ######################################################################
			
			// Pushbenachrichtigung Aktivieren/Deaktivieren
			if(isset ($_POST['push_on'])) {$_POST['push_on'] = "True"; }else{ $_POST['push_on'] = "False";}
			if($ini['Push']['push_on'] !== $_POST['push_on']){
				$ini['Push']['push_on'] = $_POST['push_on'];
			}
			// Push URL
			if (isset($_POST['push_url'])) {
				if($ini['Push']['push_url'] !== $_POST['push_url']){
					$ini['Push']['push_url'] = $_POST['push_url'];
				}
			}
			// Push Body
			if (isset($_POST['push_body'])) {
				if($ini['Push']['push_body'] !== $_POST['push_body']){
					$ini['Push']['push_body'] = $_POST['push_body'];
				}
			}
			
			// ######################################################################
			// Telegram Einstellungen --------------------------------------------------
			// ######################################################################
				
			// Telegrambenachrichtigung Aktivieren/Deaktivieren
			if(isset ($_POST['telegram_alert'])) {$_POST['telegram_alert'] = "True"; }else{ $_POST['telegram_alert'] = "False";}
			if($ini['Telegram']['telegram_alert'] !== $_POST['telegram_alert']){
				$ini['Telegram']['telegram_alert'] = $_POST['telegram_alert'];
			}
			// Telegram telegram_chat_id
			if (isset($_POST['telegram_chat_id'])) {
				if($ini['Telegram']['telegram_chat_id'] !== $_POST['telegram_chat_id']){
					$ini['Telegram']['telegram_chat_id'] = $_POST['telegram_chat_id'];
				}			
			}
			// Telegram telegram_token
			if (isset($_POST['telegram_token'])) {
				if($ini['Telegram']['telegram_token'] !== $_POST['telegram_token']){
					$ini['Telegram']['telegram_token'] = $_POST['telegram_token'];
				}			
			}

			// ###################################################################### //Dominik
			// App Einstellungen ----------------------------------------------------
			// ######################################################################
			
			// Pushbenachrichtigung Aktivieren/Deaktivieren
			if(isset ($_POST['app_alert'])) {$_POST['app_alert'] = "True"; }else{ $_POST['app_alert'] = "False";}
			if($ini['App']['app_alert'] !== $_POST['app_alert']){
				$ini['App']['app_alert'] = $_POST['app_alert'];
			}
			
			// App app_inst_id
			if (isset($_POST['app_inst_id'])) {
				if($ini['App']['app_inst_id'] !== $_POST['app_inst_id']){
					$ini['App']['app_inst_id'] = $_POST['app_inst_id'];
				}
			}
			// App app_device
			if (isset($_POST['app_device_id1'])) {
				if($ini['App']['app_device'] !== $_POST['app_device_id1']){
					$ini['App']['app_device'] = $_POST['app_device_id1'];
				}			
			}
			// App app_inst_id2
			if (isset($_POST['app_inst_id2'])) {
				if($ini['App']['app_inst_id2'] !== $_POST['app_inst_id2']){
					$ini['App']['app_inst_id2'] = $_POST['app_inst_id2'];
				}			
			}
			// App app_device2
			if (isset($_POST['app_device_id2'])) {
				if($ini['App']['app_device2'] !== $_POST['app_device_id2']){
					$ini['App']['app_device2'] = $_POST['app_device_id2'];
				}			
			}
			// App app_inst_id3
			if (isset($_POST['app_inst_id3'])) {
				if($ini['App']['app_inst_id3'] !== $_POST['app_inst_id3']){
					$ini['App']['app_inst_id3'] = $_POST['app_inst_id3'];
				}			
			}
			// App app_device3
			if (isset($_POST['app_device_id3'])) {
				if($ini['App']['app_device3'] !== $_POST['app_device_id3']){
					$ini['App']['app_device3'] = $_POST['app_device_id3'];
				}
			}
			// App app_sound
			if (isset($_POST['app_sound'])) {
				if($ini['App']['app_sound'] !== $_POST['app_sound']){
					$ini['App']['app_sound'] = $_POST['app_sound'];
				}			
			}
			// ######################################################################
			// LCD Einstellungen ----------------------------------------------------
			// ######################################################################
			
			// LCD EIN/AUS
			if(isset ($_POST['lcd_show'])) { $_POST['lcd_show'] = "True"; } else { $_POST['lcd_show'] = "False";}	
			if($ini['Display']['lcd_present'] !== $_POST['lcd_show']){
				$ini['Display']['lcd_present'] = $_POST['lcd_show'];
				$restart = true;
				$lcd_restart = true;
			}			
			
			// LCD Start Seite
			if (isset($_POST['lcd_start_page'])) {
				$ini['Display']['start_page'] = $_POST['lcd_start_page'];
			}
			
			// LCD Type
			if (isset($_POST['lcd_type'])) {
				$ini['Display']['lcd_type'] = $_POST['lcd_type'];
			}
		
			// New Logfile on restart -----------------------------------------------
			if(isset ($_POST['new_logfile_restart'])) { $_POST['new_logfile_restart'] = "True"; } else { $_POST['new_logfile_restart'] = "False";}
				if($ini['Logging']['write_new_log_on_restart'] !== $_POST['new_logfile_restart']){
					$ini['Logging']['write_new_log_on_restart'] = $_POST['new_logfile_restart'];
				}
				
			// checkUpdate ----------------------------------------------------------
			if(isset ($_POST['checkUpdate'])) { $_POST['checkUpdate'] = "True"; } else { $_POST['checkUpdate'] = "False";}
				if($ini['update']['checkupdate'] !== $_POST['checkUpdate']){
					$ini['update']['checkupdate'] = $_POST['checkUpdate'];
				}

			// showCPUlast ----------------------------------------------------------
			if(isset ($_POST['showcpulast'])) { $_POST['showcpulast'] = "True"; } else { $_POST['showcpulast'] = "False";}
				if($ini['Hardware']['showcpulast'] !== $_POST['showcpulast']){
					$ini['Hardware']['showcpulast'] = $_POST['showcpulast'];
				}
			
			// Beeper EIN/AUS -------------------------------------------------------
			if(isset ($_POST['beeper_enabled'])) { $_POST['beeper_enabled'] = "True"; } else { $_POST['beeper_enabled'] = "False";}
				if($ini['Sound']['beeper_enabled'] !== $_POST['beeper_enabled']){
					$ini['Sound']['beeper_enabled'] = $_POST['beeper_enabled'];
					$restart = true;
				}

			// Beeper bei start EIN/AUS -------------------------------------------------------
			if(isset ($_POST['beeper_on_start'])) { $_POST['beeper_on_start'] = "True"; } else { $_POST['beeper_on_start'] = "False";}
				if($ini['Sound']['beeper_on_start'] !== $_POST['beeper_on_start']){
					$ini['Sound']['beeper_on_start'] = $_POST['beeper_on_start'];
					$restart = true;
				}
								
			// Hardware Version				
			if($ini['Hardware']['version'] !== $_POST['hardware_version']){
				for ($pitmaster = 0; $pitmaster < $_SESSION["pitmaster_count"]; $pitmaster++) {
					$pitmaster_str = $pitmaster == 0 ? '' : strval($pitmaster +1);
					$ini['ToDo']['restart_pitmaster' . $pitmaster_str] = 'True';
				}
				
				$ini['Hardware']['version'] = $_POST['hardware_version'];
				$new_logfile = true;
				$lcd_restart = true;
				$restart_pit = true;
				$restart_pit2 = true;
			}
			
			// Allgemeine Einstellungen
			if (isset($_POST['language'])) {
				$ini['locale']['locale'] = $_POST['language'];
			}
			if (isset($_POST['temp_unit'])) {
				$ini['locale']['temp_unit'] = $_POST['temp_unit'];
			}
			// ######################################################################
			// Dienste nach Änderung neu starten ------------------------------------
			// ######################################################################
			
			// wlt_2_comp.py neu starten
			if($restart == true){
				$ini['ToDo']['restart_thermo'] = "True";
			}
			
			// LCD-Dienst neu starten 
			if($lcd_restart == true){
				$ini['ToDo']['restart_display'] = "True";
			}
			
			// Neues Logfile
			if($new_logfile == true){
				$ini['ToDo']['create_new_log'] = 'True';
			}
			
			// Restart Pitmaster
			if($restart_pit == true){
				$ini['ToDo']['restart_pitmaster'] = "True";
			}
			
			// Restart Pitmaster 2
			if($restart_pit2 == true){
				$ini['ToDo']['restart_pitmaster2'] = "True";
			}
			
			//#######################################################################
			// Pitmaster Einstellungen ----------------------------------------------
			//#######################################################################
			for ($pitmaster = 0; $pitmaster < $_SESSION["pitmaster_count"]; $pitmaster++) {
				$pitmaster_str = $pitmaster == 0 ? '' : strval($pitmaster +1);
				$post_prefix = 'pit' . $pitmaster_str;
				$config_section = 'Pitmaster' . $pitmaster_str;
				// Pitmaster EIN/AUS
				if(isset ($_POST[$post_prefix . '_on'])) {$_POST[$post_prefix . '_on'] = "True"; }else{ $_POST[$post_prefix . '_on'] = "False";}
				if($ini['ToDo'][$post_prefix . '_on'] !== $_POST[$post_prefix . '_on']){
					$ini['ToDo'][$post_prefix . '_on'] = $_POST[$post_prefix . '_on'];
				}
				// Pit invertierung EIN/AUS
				if(isset ($_POST[$post_prefix . '_inverted'])) {$_POST[$post_prefix . '_inverted'] = "True"; }else{ $_POST[$post_prefix . '_inverted'] = "False";}
				if($ini[$config_section]['pit_inverted'] !== $_POST[$post_prefix . '_inverted']){
					$ini[$config_section]['pit_inverted'] = $_POST[$post_prefix . '_inverted'];
				}
                // Pit Servo invertierung EIN/AUS
				if(isset ($_POST[$post_prefix . '_servo_inverted'])) {$_POST[$post_prefix . '_servo_inverted'] = "True"; }else{ $_POST[$post_prefix . '_servo_inverted'] = "False";}
				if($ini[$config_section]['pit_servo_inverted'] !== $_POST[$post_prefix . '_servo_inverted']){
					$ini[$config_section]['pit_servo_inverted'] = $_POST[$post_prefix . '_servo_inverted'];
				}
				// Pitmaster PID EIN/AUS
				if(isset ($_POST[$post_prefix . '_controller_type'])) {$_POST[$post_prefix . '_controller_type'] = "PID"; }else{ $_POST[$post_prefix . '_controller_type'] = "False";}
				if($ini[$config_section]['pit_controller_type'] !== $_POST[$post_prefix . '_controller_type']){
					$ini[$config_section]['pit_controller_type'] = $_POST[$post_prefix . '_controller_type'];
				}
				// Open Lid detection EIN/AUS
				if(isset ($_POST[$post_prefix . '_open_lid_detection'])) {$_POST[$post_prefix . '_open_lid_detection'] = "True"; }else{ $_POST[$post_prefix . '_open_lid_detection'] = "False";}
				if($ini[$config_section]['pit_open_lid_detection'] !== $_POST[$post_prefix . '_open_lid_detection']){
					$ini[$config_section]['pit_open_lid_detection'] = $_POST[$post_prefix . '_open_lid_detection'];
					//$ini['ToDo']['restart_pitmaster'] = "True";
				}
				// Pitmaster manuell einstellen
	
				if (isset($_POST[$post_prefix . '_man'])) {
					$pit2_man = to_numeric($_POST[$post_prefix . '_man']);
					if($ini[$config_section]['pit_man'] != $pit2_man){
						$ini[$config_section]['pit_man'] = $pit2_man;
					}
				}
				// Pitmaster bei Änderung neu starten
				if (isset($_POST[$post_prefix . '_curve'])) {
					//if($ini[$config_section]['pit_curve'] !== $_POST[$post_prefix . '_curve']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_curve'] = $_POST[$post_prefix . '_curve'];
				}
				if (isset($_POST[$post_prefix . '_type'])) {
					//if($ini[$config_section]['pit_type'] !== $_POST[$post_prefix . '_type']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_type'] = $_POST[$post_prefix . '_type'];
				}
				//if (isset($_POST[$post_prefix . '_controller_type'])) {
				//	if($ini[$config_section]['pit_controller_type'] !== $_POST[$post_prefix . '_controller_type']){
				//		$ini['ToDo']['restart_pitmaster'] = "True";
				//	}			
				//}
				//Pitmaster PID kp
				if (isset($_POST[$post_prefix . '_kp'])) {
					//if($ini[$config_section]['pit_kp'] !== $_POST[$post_prefix . '_kp']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_kp'] = to_numeric($_POST[$post_prefix . '_kp']);
				}
				//Pitmaster PID ki
				if (isset($_POST[$post_prefix . '_ki'])) {
					//if($ini[$config_section]['pit_ki'] !== $_POST[$post_prefix . '_ki']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_ki'] = to_numeric($_POST[$post_prefix . '_ki']);
				}
				//Pitmaster PID kd
				if (isset($_POST[$post_prefix . '_kd'])) {
					//if($ini[$config_section]['pit_kd'] !== $_POST[$post_prefix . '_kd']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_kd'] = to_numeric($_POST[$post_prefix . '_kd']);
				}
				//Pitmaster PID kp_a
				if (isset($_POST[$post_prefix . '_kp_a'])) {
					//if($ini[$config_section]['pit_kp_a'] !== $_POST[$post_prefix . '_kp_a']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_kp_a'] = to_numeric($_POST[$post_prefix . '_kp_a']);
				}
				//Pitmaster PID ki_a
				if (isset($_POST[$post_prefix . '_ki_a'])) {
					//if($ini[$config_section]['pit_ki_a'] !== $_POST[$post_prefix . '_ki_a']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_ki_a'] = to_numeric($_POST[$post_prefix . '_ki_a']);
				}
				//Pitmaster PID kd_a
				if (isset($_POST[$post_prefix . '_kd_a'])) {
					//if($ini[$config_section]['pit_kd_a'] !== $_POST[$post_prefix . '_kd_a']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_kd_a'] = to_numeric($_POST[$post_prefix . '_kd_a']);
				}
				//Pitmaster IO GPIO
				if (isset($_POST[$post_prefix . '_io_gpio'])) {
					//if($ini[$config_section]['pit_io_gpio'] !== $_POST[$post_prefix . '_io_gpio']){
					//	$ini['ToDo']['restart_pitmaster'] = "True";
					//}
					$ini[$config_section]['pit_io_gpio'] = $_POST[$post_prefix . '_io_gpio'];
				}						
				// Pitmaster Kanal
				if (isset($_POST[$post_prefix . '_ch'])) {
					$ini[$config_section]['pit_ch'] = $_POST[$post_prefix . '_ch'];
				}
				// Pitmaster Temperatur 
				if (isset($_POST[$post_prefix . '_set'])) {
					$ini[$config_section]['pit_set'] = to_numeric($_POST[$post_prefix . '_set']);
				}
				// Pitmaster Zyklendauer
				if (isset($_POST[$post_prefix . '_pause'])) {
					$ini[$config_section]['pit_pause'] = to_numeric($_POST[$post_prefix . '_pause']);
				}
				// Pitmaster Servo Totband
				if (isset($_POST[$post_prefix . '_servo_deadband'])) {
					$ini[$config_section]['pit_servo_deadband'] = to_numeric($_POST[$post_prefix . '_servo_deadband']);
				}
				// Pitmaster Ratenbegrenzung steigend
				if (isset($_POST[$post_prefix . '_ratelimit_rise'])) {
					$ini[$config_section]['pit_ratelimit_rise'] = to_numeric($_POST[$post_prefix . '_ratelimit_rise']);
				}
				// Pitmaster Ratenbegrenzung fall
				if (isset($_POST[$post_prefix . '_ratelimit_fall'])) {
					$ini[$config_section]['pit_ratelimit_fall'] = to_numeric($_POST[$post_prefix . '_ratelimit_fall']);
				}
				// Pitmaster Damper Offset
				if (isset($_POST[$post_prefix . '_damper_offset'])) {
                    $ini[$config_section]['pit_damper_offset'] = to_numeric($_POST[$post_prefix . '_damper_offset']);
				}
				// Pitmaster Damper Steigung
				if (isset($_POST[$post_prefix . '_damper_pitch'])) {
                    $ini[$config_section]['pit_damper_pitch'] = to_numeric($_POST[$post_prefix . '_damper_pitch']);
				}
				// Pitmaster PWM min 
				if (isset($_POST[$post_prefix . '_pwm_min'])) {
					if(to_numeric($_POST[$post_prefix . '_pwm_min']) < 0){
						$ini[$config_section]['pit_pwm_min'] = 0;
					}else{
						$ini[$config_section]['pit_pwm_min'] = to_numeric($_POST[$post_prefix . '_pwm_min']);
					}
				}
				// Pitmaster PWM max 
				if (isset($_POST[$post_prefix . '_pwm_max'])) {
					if(to_numeric($_POST[$post_prefix . '_pwm_max']) > 100){
						$ini[$config_section]['pit_pwm_max'] = 100;
					}else{
						$ini[$config_section]['pit_pwm_max'] = to_numeric($_POST[$post_prefix . '_pwm_max']);
					}
				}
				
				// Pitmaster Servo min
				if (isset($_POST[$post_prefix . '_servo_min'])) {
					$pit_servo_min = to_numeric($_POST[$post_prefix . '_servo_min']);
					if($pit_servo_min < 500){
						$ini[$config_section]['pit_servo_min'] = "500";
					}elseif($pit_servo_min > 2500){
						$ini[$config_section]['pit_servo_min'] = "2500";
					}else{
						$ini[$config_section]['pit_servo_min'] = $pit_servo_min;
					}
				}
				// Pitmaster Servo max 
				if (isset($_POST[$post_prefix . '_servo_max'])) {
					$pit_servo_max = to_numeric($_POST[$post_prefix . '_servo_max']);
					if($pit_servo_max < 500){
						$ini[$config_section]['pit_servo_max'] = "500";
					}elseif($pit_servo_max > 2500){
						$ini[$config_section]['pit_servo_max'] = "2500";
					}else{
						$ini[$config_section]['pit_servo_max'] = $pit_servo_max;
					}				
				}
			}
			
			//#######################################################################
			// Maverick Einstellungen -------------------------------------------------
			//#######################################################################
			
			if(isset ($_POST['maverick_enabled']))
				{$_POST['maverick_enabled'] = "True";
			} else {
				$_POST['maverick_enabled'] = "False";
			}
			if ($ini['ToDo']['maverick_enabled'] !== $_POST['maverick_enabled']){
				$ini['ToDo']['maverick_enabled'] = $_POST['maverick_enabled'];
					
			}

		    //#######################################################################
			// MAX31855 Einstellungen -------------------------------------------------
			//#######################################################################

			if(isset ($_POST['max31855']))
				{$_POST['max31855'] = "True";
			} else {
				$_POST['max31855'] = "False";
			}
			if ($ini['Hardware']['max31855'] !== $_POST['max31855']){
				$ini['Hardware']['max31855'] = $_POST['max31855'];

			}
			//#######################################################################
			// Webcam Einstellungen -------------------------------------------------
			//#######################################################################
			
			// Webcam EIN/AUS
			if(isset ($_POST['webcam_start'])) {$_POST['webcam_start'] = "True"; }else{ $_POST['webcam_start'] = "False";}
				if($ini['webcam']['webcam_start'] !== $_POST['webcam_start']){
					$ini['webcam']['webcam_start'] = $_POST['webcam_start'];
					
			}
			// Raspicam EIN/AUS
			if(isset ($_POST['raspicam_start'])) {$_POST['raspicam_start'] = "True"; }else{ $_POST['raspicam_start'] = "False";}
				if($ini['webcam']['raspicam_start'] !== $_POST['raspicam_start']){
					$ini['webcam']['raspicam_start'] = $_POST['raspicam_start'];
			}
			// Webcamsize
			if (isset($_POST['webcam_size'])) {
				$ini['webcam']['webcam_size'] = $_POST['webcam_size'];
			}
			// Raspicamsize
			if (isset($_POST['raspicam_size'])) {
				$ini['webcam']['raspicam_size'] = $_POST['raspicam_size'];
			}
			// Webcamname
			if (isset($_POST['webcam_name'])) {
				$ini['webcam']['webcam_name'] = $_POST['webcam_name'];
			}
			// Raspicamname
			if (isset($_POST['raspicam_name'])) {
				$ini['webcam']['raspicam_name'] = $_POST['raspicam_name'];
			}
			// Raspicamexposure
			if (isset($_POST['raspicam_exposure'])) {
				$ini['webcam']['raspicam_exposure'] = $_POST['raspicam_exposure'];
			}
			//#######################################################################
		
			// Logging level pitmaster
			if (isset($_POST['loglevel_pit'])) {
				$ini['daemon_logging']['level_pit'] = $_POST['loglevel_pit'];
			}
			// Logging level watchdog
			if (isset($_POST['loglevel_wd'])) {
				$ini['daemon_logging']['level_wd'] = $_POST['loglevel_wd'];
			}
			// Logging level compy
			if (isset($_POST['loglevel_compy'])) {
				$ini['daemon_logging']['level_compy'] = $_POST['loglevel_compy'];
			}
			// Logging level display
			if (isset($_POST['loglevel_display'])) {
				$ini['daemon_logging']['level_display'] = $_POST['loglevel_display'];
			}
	// Alle POST Variablen Anzeigen ###################################################################################################
	// echo nl2br(print_r($_POST,true));
	// --------------------------------------------------------------------------------------------------------------------------------
	
	// --------------------------------------------------------------------------------------------------------------------------------
	// Schreiben der WLANThermo.conf ##################################################################################################
	// --------------------------------------------------------------------------------------------------------------------------------
	
	write_ini($inipath, $ini);
	
	// --------------------------------------------------------------------------------------------------------------------------------
	// Flag setzen ####################################################################################################################
	// --------------------------------------------------------------------------------------------------------------------------------	
	exec("/usr/bin/touch /var/www/tmp/flag",$output);
		
	echo "<div class=\"infofield\">";
	echo "<head><meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"></head>
          <body>
            <h2>" . gettext("Settings have been saved...") . "</h2>
          </body>";	
	if($restart == true){
		echo "<h2>" . gettext("wlt_2_comp.py will be restarted...") . "</h2>";
	}
	echo "</div>";

// ##################################################################################
// Zurück Button auswerten ----------------------------------------------------------
// ##################################################################################

} elseif(isset($_POST["back"])) {
	echo "<div class=\"infofield\">";
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='../index.php'\"></head>
			<body> <h2>" . gettext("Leaving the page without saving...") . "</h2></body>";
	echo "</div>";
} elseif(isset($_GET["alert-test"]) && $_GET["alert-test"] == "true") {
	touch( __DIR__ . '/../alert.test' );
	echo "<div class=\"infofield\">";
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='config.php'\"></head>
			<body> <h2>" . gettext("Test alert will be sent...") . "</h2></body>";
	echo "</div>";
} elseif(isset($_GET["update-nextion"]) && $_GET["update-nextion"] == "true") {
	touch( __DIR__ . '/../tmp/nextionupdate' );
	echo "<div class=\"infofield\">";
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='config.php'\"></head>
		<body> <h2>" . gettext("Update flag has been set...") . "</h2></body>";
	echo "</div>";
    $_SESSION["nextionupdate"] = True;
} elseif(isset($_GET["calibrate-display"]) && $_GET["calibrate-display"] == "true") {
	$ini['ToDo']['calibrate_display'] = 'True';
	write_ini($inipath, $ini);
	echo "<div class=\"infofield\">";
	echo "  <head> <meta http-equiv=\"refresh\" content=\"1;URL='config.php'\"></head>
		<body> <h2>" . gettext("Display calibration is started...") . "</h2></body>";
	echo "</div>";
} else {

// ##################################################################################
// Formular ausgeben ----------------------------------------------------------------
// ##################################################################################
?>
<div id="config">	
	<h1><?php echo gettext("Settings");?></h1>
	<form action="config.php" method="post" >
	
<?php
// ##################################################################################
// Formular Fühler/Farbe/Temp min/Temp max/Kanal ------------------------------------
// ##################################################################################
		for ($i = 0; $i < $_SESSION["channel_count"]; $i++){ ?>
			<div id="ch<?php echo $i; ?>" class="config small">
				<div class="headline"><?php echo htmlentities($ini['ch_name']['ch_name'.$i], ENT_QUOTES, "UTF-8"); ?></div>
				<div class="headicon"><font color="<?php echo to_css_color($ini['plotter']['color_ch'.$i]);?>">#<?php echo $i?></font></div>
				<div class="config_text row_1 col_1"><?php echo gettext("Name");?>:</div>
				<div class="config_text row_1 col_6"<?php if ($i > 7) echo ' style="display: none;"';?>><?php echo gettext("Probe Type");?>:</div>
				<div class="config_text row_1 col_3"><input type="text" name="tch<?php echo $i;?>" size="25" maxlength="28" value="<?php echo $ini['ch_name']['ch_name'.$i];?>"></div>
				<div class="config_text row_3 col_1"><?php echo gettext("Probe Thresholds");?></div>
				<div class="config_text row_3 col_2"><?php echo gettext("min");?>:</div>
				<div class="config_text row_3 col_3"><input type="text" onkeyup="this.value=this.value.replace(/[^0-9-]/g,'');" name="temp_min<?php echo $i;?>" size="6" maxlength="3" value="<?php echo $ini['temp_min']['temp_min'.$i];?>"></div>
				<div class="config_text row_3 col_4"><?php echo gettext("max");?>:</div>
				<div class="config_text row_3 col_5"><input type="text" onkeyup="this.value=this.value.replace(/\D/, '');" name="temp_max<?php echo $i;?>" size="6" maxlength="3" value="<?php echo $ini['temp_max']['temp_max'.$i];?>"></div>
				<div class="config_text row_2 col_6"><?php echo gettext("Plot Color");?>:</div>
				<div class="config_text row_2 col_1"<?php if ($i > 7) echo ' style="display: none;"';?>><?php echo gettext("Measuring Resistance");?>:</div>
				<div class="config_text row_2 col_3"<?php if ($i > 7) echo ' style="display: none;"';?>><input type="text" onkeyup="this.value=this.value.replace(/[^0-9.]/g,'');" name="measuring_resistance<?php echo $i;?>" size="6" maxlength="6" value="<?php echo $ini['Messen']['messwiderstand'.$i];?>"></div>
				<div class="config_text row_1 col_7"<?php if ($i > 7) echo ' style="display: none;"';?>>
					<select name="fuehler<?php echo $i?>" size="1">	
						<?php
						foreach($sensor_ini AS $sensor_number => $sensor_name)
						{
							 $sensor_number = $sensor_name['number'];?> 
							<option value="<?php echo $sensor_number ?>" <?php if ($ini['Sensoren']['ch'.$i] == $sensor_number){echo " selected";} ?> ><?php echo $sensor_name['name'] ?></option><?php
						}?>
					</select>
				</div>
				<div class="config_text row_2 col_7">
					<select name="plot_color<?php echo $i?>" size="1">
					<?php
					foreach($plotcolors AS $color)
					{
					?>
						<option <?php if($ini['plotter']['color_ch'.$i] == $color)	{echo " selected";} ?> ><?php echo $color ?></option>
					<?php
					}
					?>
					</select>				
				</div>
				<div class="config_text row_3 col_7"><input type="checkbox" name="alert<?php echo $i;?>" value="salarm<?php echo $i?>" <?php if($ini['web_alert']['ch'.$i] == "True") {echo "checked=\"checked\"";}?> ></div>
				<div class="config_text row_3 col_6"><?php echo gettext("Browser Alarm");?>:</div>
			</div>
<?php 	}
// ##################################################################################
// Formular Alarmierungseinstellungen -----------------------------------------------------
// ##################################################################################	
?>
		<div class="config middle">
			<div class="headline"><?php echo gettext("Alarm Notification Settings");?></div>
			<div class="headicon"><img src="../images/icons16x16/speaker.png" alt=""></div>
			<div class="config_text row_1 col_6"><?php echo gettext("Alarm Interval (s)");?>:</div>
			<div class="config_text row_1 col_7"><input type="text" onkeyup="this.value=this.value.replace(/[^0-9.]/g,'');" name="alarm_interval" size="6" maxlength="6" value="<?php echo $ini['Alert']['alarm_interval'];?>"></div>
			<div class="config_text row_2 col_6"><?php echo gettext("Status Interval (s)");?>:</div>
			<div class="config_text row_2 col_7"><input type="text" onkeyup="this.value=this.value.replace(/[^0-9.]/g,'');" name=status_interval size="6" maxlength="6" value="<?php echo $ini['Alert']['status_interval'];?>"></div>
			<div class="config_text row_1 col_1"><?php echo gettext("Over Temp");?>:</div>
			<div class="config_text row_2 col_1"><?php echo gettext("Under Temp");?>:</div>
			<div class="config_text row_3 col_1"><?php echo gettext("Status");?>:</div>
			<div class="config_text row_4 col_1"><?php echo gettext("Message");?>:</div>
			<div class="config_text row_1 col_5"><input type="text" name="alarm_high_template" id="alarm_high_template" size="35" maxlength="250" value="<?php echo $ini['Alert']['alarm_high_template'];?>"></div>
			<div class="config_text row_2 col_5"><input type="text" name="alarm_low_template" id="alarm_low_template" size="35" maxlength="250" value="<?php echo $ini['Alert']['alarm_low_template'];?>"></div>
			<div class="config_text row_3 col_5"><input type="text" name="status_template" id="status_template" size="35" maxlength="250" value="<?php echo $ini['Alert']['status_template'];?>"></div>
			<div class="config_text row_4 col_5"><input type="text" name="message_template" id="message_template" size="35" maxlength="250" value="<?php echo $ini['Alert']['message_template'];?>"></div>
			<div class="config_text row_4 col_6"><button type="button" onclick="$.get('config.php?alert-test=true')" class="wide"><?php echo gettext("Send Test Message");?></button></div>

		</div>
<?php
// ##################################################################################
// Formular EMail Einstellungen -----------------------------------------------------
// ##################################################################################	
?>
		<div class="config middle">
			<div class="headline"><?php echo gettext("Email Notification Settings");?></div>
			<div class="config_text row_4 col_4"><?php echo gettext("TLS encryption");?>:&nbsp;<input type="checkbox" name="starttls" id="email_starttls" value="True" <?php if($ini['Email']['starttls'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_1 col_6"><?php echo gettext("Enable Email Notification");?>:</div>			
			<div class="config_text row_1 col_7"><input type="checkbox" name="email" id="email" value="True" <?php if($ini['Email']['email_alert'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="headicon"><img src="../images/icons16x16/mail.png" alt=""></div>
			<div class="config_text row_2 col_6"><?php echo gettext("Authentication");?>:</div>
			<div class="config_text row_2 col_7"><input type="checkbox" name="auth_check" id="email_auth_check" value="True" <?php if($ini['Email']['auth'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_1 col_1"><?php echo gettext("To");?>:</div>
			<div class="config_text row_2 col_1"><?php echo gettext("From");?>:</div>
			<div class="config_text row_3 col_1"><?php echo gettext("Subject");?>:</div>
			<div class="config_text row_1 col_5"><input type="text" name="email_to" id="email_to" size="35" maxlength="50" value="<?php echo $ini['Email']['email_to'];?>"></div>
			<div class="config_text row_2 col_5"><input type="text" name="email_from" id="email_from" size="35" maxlength="50" value="<?php echo $ini['Email']['email_from'];?>"></div>
			<div class="config_text row_3 col_5"><input type="text" name="email_subject" id="email_subject" size="35" maxlength="50" value="<?php echo $ini['Email']['email_subject'];?>"></div>
			<div class="config_text row_3 col_6"><?php echo gettext("Server");?>:</div>
			<div class="config_text row_3 col_7"><input type="text" name="email_smtp" id="email_smtp" size="18" maxlength="50" value="<?php echo $ini['Email']['server'];?>"></div>
			<div class="config_text row_4 col_6"><?php echo gettext("Password");?>:</div>
			<div class="config_text row_4 col_7"><input type="password" name="email_password" id="email_password" size="18" maxlength="50" value="<?php echo $ini['Email']['password'];?>"></div>
			<div class="config_text row_4 col_1"><?php echo gettext("Username");?>:</div>
			<div class="config_text row_4 col_3"><input type="text" name="email_username" id="email_username" size="15" maxlength="50" value="<?php echo $ini['Email']['username'];?>"></div>
		</div>

<?php
// ##################################################################################
// Formular Telegram Einstellungen --------------------------------------------------
// ##################################################################################
?>
		<div class="config small">
			<div class="headline"><?php echo gettext("Telegram Settings");?></div>
			<div class="headicon"><img src="../images/icons16x16/telegram.png" alt=""></div>
            <div class="config_text row_1 col_1"><?php echo gettext("Set Chat-ID");?>:</div>
            <div class="config_text row_1 col_4"><select name="telegram_chatid_select" id="telegram_chatid_select" size="1" style="width:260px;">
                                <option value="" selected="selected">---</option>
                                </select></div>
            <div class="config_text row_2 col_1"><?php echo gettext("Please enter token below and send '/start' to the Bot before getting Chat-ID!");?></div>
			<div class="config_text row_3 col_1"><?php echo gettext("Token");?>:</div>
			<div class="config_text row_3 col_3"><input type="text" name="telegram_token" id="telegram_token" size="25" maxlength="50" value="<?php echo $ini['Telegram']['telegram_token'];?>"></div>
			<div class="config_text row_3 col_4"><?php echo gettext("Chat-ID");?>: <input type="text" name="telegram_chat_id" id="telegram_chat_id" size="18" maxlength="20" value="<?php echo $ini['Telegram']['telegram_chat_id'];?>"></div>
			<div class="config_text row_3 col_5"></div>
			<div class="config_text row_3 col_6"><?php echo gettext("Enable Telegram");?>:</div>			
			<div class="config_text row_3 col_7"><input type="checkbox" name="telegram_alert" id="telegram_alert" value="True" <?php if($ini['Telegram']['telegram_alert'] == "True") {echo "checked=\"checked\"";}?> ></div>
		</div>
<?php
// ##################################################################################
// Formular Push Einstellungen --------------------------------------------------
// ##################################################################################
?>
		<div class="config little">
			<div class="headline"><?php echo gettext("Push Notification Settings");?></div>
			<div class="config_text row_1 col_6"><?php echo gettext("Enable Push Notification");?>:</div>			
			<div class="config_text row_1 col_7"><input type="checkbox" name="push_on" id="push_on" value="True" <?php if($ini['Push']['push_on'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="headicon">&nbsp;</div>
			<div class="config_text row_1 col_1"><?php echo gettext("URL");?>:</div>
			<div class="config_text row_1 col_4"><?php echo gettext("Body");?>: <input type="text" name="push_body" id="push_body" size="23" maxlength="500" value="<?php echo $ini['Push']['push_body'];?>"></div>
			<div class="config_text row_1 col_3"><input type="text" name="push_url" id="push_url" size="25" maxlength="500" value="<?php echo $ini['Push']['push_url'];?>"></div>
			<div class="config_text row_1 col_5"></div>
		</div>
<?php

// ################################################################################## //Dominik
// Formular App Einstellungen -----------------------------------------------------
// ##################################################################################
?>
		<div class="config middle">
			<div class="headline"><?php echo gettext("App Settings");?></div>
			<div class="config_text row_1 col_6"><?php echo gettext("Enable App Notification");?>:</div>			
			<div class="config_text row_1 col_7"><input type="checkbox" name="app_alert" id="app_alert" value="True" <?php if($ini['App']['app_alert'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="headicon"><img src="../images/icons16x16/app.png" alt=""></div>
			<div class="config_text row_2 col_1"><?php echo gettext("Device ID");?> 1:</div>
			<div class="config_text row_3 col_1"><?php echo gettext("Device ID");?> 2:</div>
			<div class="config_text row_4 col_1"><?php echo gettext("Device ID");?> 3:</div>
			<div class="config_text row_2 col_5"><input type="text" name="app_inst_id" id="app_inst_id" size="35" maxlength="200" value="<?php echo $ini['App']['app_inst_id'];?>"></div>
			<div class="config_text row_3 col_5"><input type="text" name="app_inst_id2" id="app_inst_id2" size="35" maxlength="200" value="<?php echo $ini['App']['app_inst_id2'];?>"></div>
			<div class="config_text row_4 col_5"><input type="text" name="app_inst_id3" id="app_inst_id3" size="35" maxlength="200" value="<?php echo $ini['App']['app_inst_id3'];?>"></div>
			<div class="config_text row_2 col_4"></div>
			<div class="config_text row_3 col_4"></div>
			<div class="config_text row_4 col_4"></div>
			<div class="config_text row_2 col_5"></div>
			<div class="config_text row_3 col_5"></div>
			<div class="config_text row_4 col_5"></div>
			<div class="config_text row_2 col_6"><?php echo gettext("Device Type");?> 1:</div>
			<div class="config_text row_3 col_6"><?php echo gettext("Device Type");?> 2:</div>
			<div class="config_text row_4 col_6"><?php echo gettext("Device Type");?> 3:</div>
			<div class="config_text row_2 col_7">
				<select name="app_device" id="app_device_id1" size="1">	
					<?php
					foreach($app_devices as $device_name => $device_id)
					{?> 
						<option value="<?php echo $device_id ?>" <?php if ($ini['App']['app_device'] == $device_id){echo " selected";} ?> ><?php echo $device_name ?></option><?php
					}?>
				</select>			
			</div>
			<div class="config_text row_3 col_7">
				<select name="app_device2" id="app_device_id2" size="1">	
					<?php
					foreach($app_devices as $device_name => $device_id)
					{?> 
						<option value="<?php echo $device_id ?>" <?php if ($ini['App']['app_device2'] == $device_id){echo " selected";} ?> ><?php echo $device_name ?></option><?php
					}?>
				</select>			
			</div>
			<div class="config_text row_4 col_7">
				<select name="app_device3" id="app_device_id3" size="1">	
					<?php
					foreach($app_devices as $device_name => $device_id)
					{?> 
						<option value="<?php echo $device_id ?>" <?php if ($ini['App']['app_device3'] == $device_id){echo " selected";} ?> ><?php echo $device_name ?></option><?php
					}?>
				</select>			
			</div>
		</div>
 <?php

// ##################################################################################
// Formular Plotter Einstellungen ---------------------------------------------------
// ##################################################################################

?>
        <div class="config five_lines">
            <div class="headline"><?php echo gettext("Chart Settings");?></div>           
            <div class="headicon"><img src="../images/icons16x16/chart.png" alt=""></div>
            <div class="config_text row_1 col_1"><?php echo gettext("Chart Name");?>:</div>
            <div class="config_text row_1 col_3"><input type="text" name="plotname" id="plot_name" size="18" maxlength="25" value="<?php echo $ini['plotter']['plotname'];?>"></div>
            <div class="config_text row_1 col_6"><?php echo gettext("Enable Chart");?>:</div>
            <div class="config_text row_1 col_7"><input type="checkbox" name="plot_start" id="plot_start" value="True" <?php if($ini['ToDo']['plot_start'] == "True") {echo "checked=\"checked\"";}?> ></div>
            <div class="config_text row_2 col_1"><?php echo gettext("Chart Range");?></div>
            <div class="config_text row_2 col_2"><?php echo gettext("from");?>:</div>
            <div class="config_text row_2 col_3"><input type="text" onkeyup="this.value=this.value.replace(/[^0-9-]/g,'');" name="plotbereich_min" id="plotbereich_min" size="6" maxlength="3" value="<?php echo $ini['plotter']['plotbereich_min'];?>"></div>
            <div class="config_text row_2 col_4"><?php echo gettext("to");?>:</div>
            <div class="config_text row_2 col_5"><input type="text" onkeyup="this.value=this.value.replace(/\D/, '');" name="plotbereich_max" id="plotbereich_max" size="6" maxlength="3" value="<?php echo $ini['plotter']['plotbereich_max'];?>"></div>
            <div class="config_text row_2 col_6"><?php echo gettext("Show Legend");?>:</div>
            <div class="config_text row_2 col_7">
                <select name="keybox" id="plot_keybox" size="1">
                    <option <?php if($ini['plotter']['keybox'] == "top left")                {echo " selected";} ?> value="top left"     ><?php echo gettext("top left");?></option>
                    <option <?php if($ini['plotter']['keybox'] == "top right")                {echo " selected";} ?> value="top right"     ><?php echo gettext("top right");?></option>
                    <option <?php if($ini['plotter']['keybox'] == "bottom left")            {echo " selected";} ?> value="bottom left"     ><?php echo gettext("bottom left");?></option>
                    <option <?php if($ini['plotter']['keybox'] == "bottom right")            {echo " selected";} ?> value="bottom right" ><?php echo gettext("bottom right");?></option>
                    <option <?php if($ini['plotter']['keybox'] == "center left")            {echo " selected";} ?> value="center left"     ><?php echo gettext("center left");?></option>
                    <option <?php if($ini['plotter']['keybox'] == "center right")            {echo " selected";} ?> value="center right" ><?php echo gettext("center right");?></option>
                </select>       
            </div>
            <div class="config_text row_3 col_1"><?php echo gettext("Chart Size");?>:</div>
            <div class="config_text row_3 col_3">
                <select name="plotsize" id="plot_size" size="1">                       
                    <option <?php if($ini['plotter']['plotsize'] == "700x350")              {echo " selected";} ?> value="700x350" >700x350</option>
                    <option <?php if($ini['plotter']['plotsize'] == "800x500")              {echo " selected";} ?> value="800x500" >800x500</option>
                    <option <?php if($ini['plotter']['plotsize'] == "900x600")              {echo " selected";} ?> value="900x600" >900x600</option>
                    <option <?php if($ini['plotter']['plotsize'] == "1000x700")             {echo " selected";} ?> value="1000x700" >1000x700</option>
                    <option <?php if($ini['plotter']['plotsize'] == "1280x1024")            {echo " selected";} ?> value="1280x1024" >1280x1024</option>
                    <option <?php if($ini['plotter']['plotsize'] == "1600x1200")            {echo " selected";} ?> value="1600x1200" >1600x1200</option>
                    <option <?php if($ini['plotter']['plotsize'] == "1920x1200")            {echo " selected";} ?> value="1920x1200" >1920x1200</option>
                </select>
            </div>
            <div class="config_text row_3 col_6"><?php echo gettext("Enable Frame Legend");?>:</div>
            <div class="config_text row_3 col_7"><input type="checkbox" name="keyboxframe" id="plot_keyboxframe" value="True" <?php if($ini['plotter']['keyboxframe'] == "True") {echo "checked=\"checked\"";}?> ></div>   
            <div class="config_text row_4 col_1"><?php echo gettext("Pit out");?>:</div>
            <div class="config_text row_4 col_3">
                <select name="color_pit" id="plot_color_pit" size="1">
                <?php
                foreach($plotcolors AS $color)
                {
                ?>
                    <option <?php if($ini['plotter']['color_pit'] == $color)    {echo " selected";} ?> ><?php echo $color ?></option>
                <?php
                }
                ?>
                </select>
            </div>           
            <div class="config_text row_4 col_6"><?php echo gettext("Enable Pitmaster Chart");?>:</div>
            <div class="config_text row_4 col_7"><input type="checkbox" name="plot_pit" id="plot_pit" value="True" <?php if($ini['plotter']['plot_pit'] == "True") {echo "checked=\"checked\"";}?> ></div>
            <div class="config_text row_5 col_1"><?php echo gettext("Pit setpoint");?>:</div>
            <div class="config_text row_5 col_3">
                <select name="color_pitsoll" id="plot_color_pitsoll" size="1">
                <?php
                foreach($plotcolors AS $color)
                {
                ?>
                    <option <?php if($ini['plotter']['color_pitsoll'] == $color) {echo " selected";} ?>><?php echo $color ?></option>
                <?php
                }
                ?>
                </select>
            </div>
            <div class="config_text row_4 col_4"><?php echo gettext("Pit 2 out");?>:&nbsp;
                <select name="color_pit2" id="plot_color_pit2" size="1">
                <?php
                foreach($plotcolors AS $color)
                {
                ?>
                    <option <?php if($ini['plotter']['color_pit2'] == $color)    {echo " selected";} ?> ><?php echo $color ?></option>
                <?php
                }
                ?>
                </select>
            </div>
            
            <div class="config_text row_5 col_6"><?php echo gettext("Enable Pitmaster 2 Chart");?>:</div>
            <div class="config_text row_5 col_7"><input type="checkbox" name="plot_pit2" id="plot_pit2" value="True" <?php if($ini['plotter']['plot_pit2'] == "True") {echo "checked=\"checked\"";}?> ></div>
            <div class="config_text row_5 col_4"><?php echo gettext("Pit 2 setpoint");?>:&nbsp
                <select name="color_pit2soll" id="plot_color_pit2soll" size="1">
                <?php
                foreach($plotcolors AS $color)
                {
                ?>
                    <option <?php if($ini['plotter']['color_pit2soll'] == $color) {echo " selected";} ?>><?php echo $color ?></option>
                <?php
                }
                ?>
                </select>
            </div>
        </div> 	
<?php
// ##################################################################################
// Formular Webcam Einstellungen ----------------------------------------------------
// ##################################################################################
?>	
		<div class="config middle">
			<div class="headline"><?php echo gettext("Webcam Settings");?></div>
			<div class="headicon"><img src="../images/icons16x16/webcam.png" alt=""></div>
			<div class="config_text row_1 col_1"><?php echo gettext("Name");?>:</div>
			<div class="config_text row_1 col_3"><input type="text" name="webcam_name" id="webcam_name" size="25" maxlength="28" value="<?php echo $ini['webcam']['webcam_name'];?>"></div>
			<div class="config_text row_1 col_6"><?php echo gettext("Enable Webcam");?>:</div>
			<div class="config_text row_1 col_7"><input type="checkbox" name="webcam_start" id="webcam_start" value="True" <?php if($ini['webcam']['webcam_start'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_2 col_1"><?php echo gettext("Resolution");?>:</div>
			<div class="config_text row_2 col_3">
				<select name="webcam_size" id="webcam_size" size="1">						
					<option <?php if($ini['webcam']['webcam_size'] == "320x240")			{echo " selected";} ?> >320x240</option>
					<option <?php if($ini['webcam']['webcam_size'] == "640x480")			{echo " selected";} ?> >640x480</option>
					<option <?php if($ini['webcam']['webcam_size'] == "1080x720")			{echo " selected";} ?> >1080x720</option>
		            <option <?php if($ini['webcam']['webcam_size'] == "1280x1024")			{echo " selected";} ?> >1280x1024</option>
				</select>
			</div>					
			<div class="config_text row_3 col_1"><?php echo gettext("Name");?>:</div>
			<div class="config_text row_3 col_3"><input type="text" name="raspicam_name" id="raspicam_name" size="25" maxlength="28" value="<?php echo $ini['webcam']['raspicam_name'];?>"></div>
			<div class="config_text row_3 col_6"><?php echo gettext("Enable Raspicam");?>:</div>
			<div class="config_text row_3 col_7"><input type="checkbox" name="raspicam_start" id="raspicam_start" value="True" <?php if($ini['webcam']['raspicam_start'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_4 col_1"><?php echo gettext("Resolution");?>:</div>
			<div class="config_text row_4 col_3">
				<select name="raspicam_size" id="raspicam_size" size="1">						
					<option <?php if($ini['webcam']['raspicam_size'] == "320x240")			{echo " selected";} ?> >320x240</option>
					<option <?php if($ini['webcam']['raspicam_size'] == "640x480")			{echo " selected";} ?> >640x480</option>
					<option <?php if($ini['webcam']['raspicam_size'] == "1024x768")			{echo " selected";} ?> >1024x768</option>
					<option <?php if($ini['webcam']['raspicam_size'] == "1280x720")			{echo " selected";} ?> >1280x720</option>
					<option <?php if($ini['webcam']['raspicam_size'] == "1280x1024")		{echo " selected";} ?> >1280x1024</option>
					<option <?php if($ini['webcam']['raspicam_size'] == "2592x1944")		{echo " selected";} ?> >2592x1944</option>
				</select>
			</div>
			<div class="config_text row_3 col_4"><?php echo gettext("Exposure");?>:&nbsp;&nbsp;
				<select name="raspicam_exposure" id="raspicam_exposure" size="1">						
					<option <?php if($ini['webcam']['raspicam_exposure'] == "off")			{echo " selected";} ?> >off</option>
					<option <?php if($ini['webcam']['raspicam_exposure'] == "auto")			{echo " selected";} ?> >auto</option>
					<option <?php if($ini['webcam']['raspicam_exposure'] == "night")		{echo " selected";} ?> >night</option>
					<option <?php if($ini['webcam']['raspicam_exposure'] == "backlight")	{echo " selected";} ?> >backlight</option>
					<option <?php if($ini['webcam']['raspicam_exposure'] == "spotlight")	{echo " selected";} ?> >spotlight</option>
				</select>
			</div>
			
		</div>
<?php
// ##################################################################################
// Formular Pitmaster Einstellungen -------------------------------------------------
// ##################################################################################
for ($pitmaster = 0; $pitmaster < $_SESSION["pitmaster_count"]; $pitmaster++) {
	$pitmaster_str = $pitmaster == 0 ? '' : strval($pitmaster +1);
	$post_prefix = 'pit' . $pitmaster_str;
	$config_section = 'Pitmaster' . $pitmaster_str;?>	
        <div class="config five_lines">
            <div class="headline"><?php echo gettext(sprintf("Pitmaster %u Settings", $pitmaster +1));?></div>
            <div class="headicon"><img src="../images/icons16x16/pitmaster.png" alt=""></div>
            <div class="config_text row_1 col_1"><?php echo gettext("Temperature");?>:</div>
            <div class="config_text row_3 col_1"><?php echo gettext("Control Curve");?>:</div>
            <div class="config_text row_1 col_6"><?php echo gettext("Enable Pitmaster");?>:</div>
            <div class="config_text row_1 col_7"><input type="checkbox" name="<?php echo $post_prefix;?>_on" id="<?php echo $post_prefix;?>_on" value="True" <?php if(isset($ini['ToDo'][$post_prefix . '_on']) && $ini['ToDo'][$post_prefix . '_on'] == "True") {echo "checked=\"checked\"";}?> ></div>
            <div class="config_text row_3 col_6"></div>
            <div class="config_text row_3 col_7"></div>
            <div class="config_text row_3 col_5"><input type="text" name="<?php echo $post_prefix;?>_curve" id="<?php echo $post_prefix;?>_curve" size="35" maxlength="50" value="<?php if (isset($ini[$config_section]['pit_curve']))  echo $ini[$config_section]['pit_curve'];?>"></div>
            <div class="config_text row_2 col_6"><?php echo gettext("Channel");?>:</div>
			<div class="config_text row_2 col_7">
				<select name="<?php echo $post_prefix;?>_ch" id="<?php echo $post_prefix;?>_ch" size="1">
				    <?php for ($i = 0; $i < $_SESSION["channel_count"]; $i++) {?>
                    <option <?php if(isset($ini[$config_section]['pit_ch']) && $ini[$config_section]['pit_ch'] == $i) {echo " selected";} ?> value="<?php echo $i; ?>"><?php echo gettext("Channel") . ' ' . $i;?></option>
                    <?php } ?>
                </select>
            </div>
            <div class="config_text row_1 col_3"><input type="text" onkeyup="this.value=this.value.replace(/[^0-9.]/g,'');" name="<?php echo $post_prefix;?>_set" id="<?php echo $post_prefix;?>_set" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_set'])) echo $ini[$config_section]['pit_set'];?>"></div>
            <div class="config_text row_1 col_4"><?php echo gettext("Delay");?>: </div>
            <div class="config_text row_2 col_3"><input type="text" onkeyup="this.value=this.value.replace(/[^0-9.]/g,'');" name="<?php echo $post_prefix;?>_man" id="<?php echo $post_prefix;?>_man" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_man'])) echo $ini[$config_section]['pit_man'];?>"></div>
            <div class="config_text row_2 col_1"><?php echo gettext("Manual Control");?>: </div>
            <div class="config_text row_1 col_5"><input type="text" onkeyup="this.value=this.value.replace(/[^\d\.]/g, '');" name="<?php echo $post_prefix;?>_pause" id="<?php echo $post_prefix;?>_pause" size="5" maxlength="4" value="<?php if (isset($ini[$config_section]['pit_pause'])) echo $ini[$config_section]['pit_pause'];?>"></div>
            <div class="config_text row_5 col_6"><?php echo gettext("PID Control");?>:</div>
			<div class="config_text row_5 col_7"><input type="checkbox" name="<?php echo $post_prefix;?>_controller_type" id="<?php echo $post_prefix;?>_controller_type" value="True" <?php if($ini[$config_section]['pit_controller_type'] == "PID") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_4 col_6"><?php echo gettext("Open Lid detection");?>:</div>
			<div class="config_text row_4 col_7"><input type="checkbox" name="<?php echo $post_prefix;?>_open_lid_detection" id="<?php echo $post_prefix;?>_open_lid_detection" value="True" <?php if($ini[$config_section]['pit_open_lid_detection'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_4 col_1"><?php echo gettext("Kp");?>:</div>
			<div class="config_text row_4 col_1_5"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_kp" id="<?php echo $post_prefix;?>_kp" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_kp'])) echo $ini[$config_section]['pit_kp'];?>"></div>
			<div class="config_text row_4 col_2"><?php echo gettext("Ki");?>:</div>
			<div class="config_text row_4 col_3"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_ki" id="<?php echo $post_prefix;?>_ki" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_ki'])) echo $ini[$config_section]['pit_ki'];?>"></div>
			<div class="config_text row_4 col_4"><?php echo gettext("Kd");?>:</div>
			<div class="config_text row_4 col_5"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_kd" id="<?php echo $post_prefix;?>_kd" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_kd'])) echo $ini[$config_section]['pit_kd'];?>"></div>
			<div class="config_text row_5 col_1"><?php echo gettext("Kp_a");?>:</div>
			<div class="config_text row_5 col_1_5"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_kp_a" id="<?php echo $post_prefix;?>_kp_a" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_kp_a'])) echo $ini[$config_section]['pit_kp_a'];?>"></div>
			<div class="config_text row_5 col_2"><?php echo gettext("Ki_a");?>:</div>
			<div class="config_text row_5 col_3"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_ki_a" id="<?php echo $post_prefix;?>_ki_a" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_ki_a'])) echo $ini[$config_section]['pit_ki_a'];?>"></div>
			<div class="config_text row_5 col_4"><?php echo gettext("Kd_a");?>:</div>
			<div class="config_text row_5 col_5"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_kd_a" id="<?php echo $post_prefix;?>_kd_a" size="5" maxlength="5" value="<?php if (isset($ini[$config_section]['pit_kd_a'])) echo $ini[$config_section]['pit_kd_a'];?>"></div>
		</div>
		<div class="config five_lines">
            <div class="headline"><?php echo gettext(sprintf("Pit %u Settings", $pitmaster +1));?></div>
            <div class="config_text row_1 col_1"><?php echo gettext("Type");?>:</div>
            <div class="config_text row_1 col_2">
                <select name="<?php echo $post_prefix;?>_type" id="<?php echo $post_prefix;?>_type" size="1">
                    <option <?php if(isset($ini[$config_section]['pit_type']) && $ini[$config_section]['pit_type'] == "servo")            	{echo " selected";} ?> value="servo"><?php echo gettext("Servo");?></option>
                    <option <?php if(isset($ini[$config_section]['pit_type']) && $ini[$config_section]['pit_type'] == "fan_pwm")            {echo " selected";} ?> value="fan_pwm"><?php echo gettext("PWM Fan");?></option>
                    <option <?php if(isset($ini[$config_section]['pit_type']) && $ini[$config_section]['pit_type'] == "fan")            	{echo " selected";} ?> value="fan"><?php echo gettext("Fan");?></option>
                    <option <?php if(isset($ini[$config_section]['pit_type']) && $ini[$config_section]['pit_type'] == "io")                	{echo " selected";} ?> value="io"><?php echo gettext("IO");?></option>
                    <option <?php if(isset($ini[$config_section]['pit_type']) && $ini[$config_section]['pit_type'] == "io_pwm")         	{echo " selected";} ?> value="io_pwm"><?php echo gettext("IO with PWM");?></option>
                    <?php if ($ini['Hardware']['version'] == "miniV2" or $ini['Hardware']['version'] == "miniplus") { ?>
                    <option <?php if(isset($ini[$config_section]['pit_type']) && $ini[$config_section]['pit_type'] == "damper")         	{echo " selected";} ?> value="damper"><?php echo gettext("Servo Damper");?></option>
                    <?php } ?>
                </select>
            </div>
            <div class="config_text row_2 col_1"><?php echo gettext("Duty Cycle (%)");?></div>
			<div class="config_text row_2 col_2"><?php echo gettext("min");?>:</div>
		    <div class="config_text row_2 col_2"></div>
            <div class="config_text row_2 col_3"><input type="text" onkeyup="this.value=this.value.replace(/\D/, '');" name="<?php echo $post_prefix;?>_pwm_min" id="<?php echo $post_prefix;?>_pwm_min" size="5" maxlength="3" value="<?php if (isset($ini[$config_section]['pit_pwm_min'])) echo $ini[$config_section]['pit_pwm_min'];?>"></div>
            <div class="config_text row_2 col_4"><?php echo gettext("max");?>:</div>
            <div class="config_text row_2 col_5"><input type="text" onkeyup="this.value=this.value.replace(/\D/, '');" name="<?php echo $post_prefix;?>_pwm_max" id="<?php echo $post_prefix;?>_pwm_max" size="5" maxlength="3" value="<?php if (isset($ini[$config_section]['pit_pwm_max'])) echo $ini[$config_section]['pit_pwm_max'];?>" ></div>
			<div class="config_text row_2 col_6"></div>
			<div class="config_text row_2 col_7"></div>
            <div class="config_text row_3 col_1"><?php echo gettext("Servo Pulse (µs)");?>:</div>
            <div class="config_text row_3 col_2"><?php echo gettext("min");?>:</div>
            <div class="config_text row_3 col_3"><input type="text" onkeyup="this.value=this.value.replace(/\D/, '');" name="<?php echo $post_prefix;?>_servo_min" id="<?php echo $post_prefix;?>_servo_min" size="5" maxlength="4" value="<?php if (isset($ini[$config_section]['pit_servo_min'])) echo $ini[$config_section]['pit_servo_min'];?>"></div>
			<div class="config_text row_3 col_4"><?php echo gettext("max");?>:</div>
            <div class="config_text row_3 col_5"><input type="text" onkeyup="this.value=this.value.replace(/\D/, '');" name="<?php echo $post_prefix;?>_servo_max" id="<?php echo $post_prefix;?>_servo_max" size="5" maxlength="4" value="<?php if (isset($ini[$config_section]['pit_servo_max'])) echo $ini[$config_section]['pit_servo_max'];?>"></div>
			<div class="config_text row_2 col_6"><?php echo gettext("Reverse Drive");?>:</div>
            <div class="config_text row_2 col_7"><input type="checkbox" name="<?php echo $post_prefix;?>_inverted" id="<?php echo $post_prefix;?>_inverted" value="True" <?php if(isset($ini[$config_section]['pit_inverted']) && $ini[$config_section]['pit_inverted'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_3 col_6"><?php echo gettext("Reverse Servo");?>:</div>
            <div class="config_text row_3 col_7"><input type="checkbox" name="<?php echo $post_prefix;?>_servo_inverted" id="<?php echo $post_prefix;?>_servo_inverted" value="True" <?php if(isset($ini[$config_section]['pit_servo_inverted']) && $ini[$config_section]['pit_servo_inverted'] == "True") {echo "checked=\"checked\"";}?> ></div>
            <div class="config_text row_4 col_1"><?php echo gettext("Damper control");?></div>
			<div class="config_text row_4 col_2"><?php echo gettext("offset");?>:</div>
            <div class="config_text row_4 col_3"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_damper_offset" id="<?php echo $post_prefix;?>_damper_offset" size="5" maxlength="3" value="<?php if (isset($ini[$config_section]['pit_damper_offset'])) echo $ini[$config_section]['pit_damper_offset'];?>"></div>
            <div class="config_text row_4 col_4"><?php echo gettext("pitch");?>:</div>
            <div class="config_text row_4 col_5"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_damper_pitch" id="<?php echo $post_prefix;?>_damper_pitch" size="5" maxlength="3" value="<?php if (isset($ini[$config_section]['pit_damper_pitch'])) echo $ini[$config_section]['pit_damper_pitch'];?>" ></div>
			<div class="config_text row_4 col_6"><?php echo gettext("Servo deadband (%)");?>:</div>
			<div class="config_text row_4 col_7"><input type="text" onkeyup="this.value=this.value.replace(/\D/, '');" name="<?php echo $post_prefix;?>_servo_deadband" id="<?php echo $post_prefix;?>_servo_deadband" size="3" maxlength="3" value="<?php if (isset($ini[$config_section]['pit_servo_deadband'])) echo $ini[$config_section]['pit_servo_deadband'];?>"></div>
			<div class="config_text row_5 col_1"><?php echo gettext("Rate limit (s)");?></div>
			<div class="config_text row_5 col_2"><?php echo gettext("rise");?>:</div>
            <div class="config_text row_5 col_3"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_ratelimit_rise" id="<?php echo $post_prefix;?>_ratelimit_rise" size="5" maxlength="3" value="<?php if (isset($ini[$config_section]['pit_ratelimit_rise'])) echo $ini[$config_section]['pit_ratelimit_rise'];?>"></div>
            <div class="config_text row_5 col_4"><?php echo gettext("fall");?>:</div>
            <div class="config_text row_5 col_5"><input type="text" onkeyup="this.value=this.value.replace(/,/, '.');" name="<?php echo $post_prefix;?>_ratelimit_fall" id="<?php echo $post_prefix;?>_ratelimit_fall" size="5" maxlength="3" value="<?php if (isset($ini[$config_section]['pit_ratelimit_fall'])) echo $ini[$config_section]['pit_ratelimit_fall'];?>"></div>
			<div class="config_text row_5 col_6"></div>
			<div class="config_text row_5 col_7"></div>
        </div>

<?php
}

// ##################################################################################
// Formular Allgemeine Einstellungen ------------------------------------------------
// ##################################################################################
?>
		<div class="config big">
			<div class="headline"><?php echo gettext("General Settings");?></div>		
			<div class="headicon"><img src="../images/icons16x16/settings.png" alt=""></div>
			<div class="config_text row_1 col_1"><?php echo gettext("Hardware Version");?>:</div>
			<div class="config_text row_1 col_4">
			<select name="hardware_version" id="hardware_version" size="1">
			<option value="v1" <?php if($ini['Hardware']['version'] == "v1") {echo "selected=\"selected\"";}?> >v1</option>
			<option  value="v2" <?php if($ini['Hardware']['version'] == "v2") {echo "selected=\"selected\"";}?> >v2</option>
			<option  value="v3" <?php if($ini['Hardware']['version'] == "v3") {echo "selected=\"selected\"";}?> >v3 / mini</option>
			<option  value="miniV2" <?php if($ini['Hardware']['version'] == "miniV2") {echo "selected=\"selected\"";}?> > miniV2</option>
			<option  value="miniplus" <?php if($ini['Hardware']['version'] == "miniplus") {echo "selected=\"selected\"";}?> > miniplus</option>
			</select>
			</div>
			<div class="config_text row_1 col_6"><?php echo gettext("Language");?>:</div>
			<div class="config_text row_1 col_7">
				<select name="language" id="language" size="1">
					<?php
					$language = get_available_languages();
					foreach($language AS $lang){?>
						<option <?php if($ini['locale']['locale'] == $lang)	{echo " selected";} ?> ><?php echo $lang; ?></option>
					<?php
					}
					?>
                </select>
			</div>
			<div class="config_text row_2 col_6"><?php echo gettext("Unit");?>:</div>
			<div class="config_text row_2 col_7">
				<select name="temp_unit" id="temp_unit" size="1">
					<option <?php if($ini['locale']['temp_unit'] == "celsius") {echo " selected";} ?> value="celsius">Celsius</option>
                    <option <?php if($ini['locale']['temp_unit'] == "fahrenheit") {echo " selected";} ?> value="fahrenheit">Fahrenheit</option>
                </select>
			</div>
			<div class="config_text row_2 col_1"><?php echo gettext("New Log File on Start");?>:</div>
			<div class="config_text row_2 col_4"><input type="checkbox" name="new_logfile_restart" value="True" <?php if($ini['Logging']['write_new_log_on_restart'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_3 col_1"><?php echo gettext("Auto-Check for Update");?>:</div>
			<div class="config_text row_3 col_4"><input type="checkbox" name="checkUpdate" value="True" <?php if($ini['update']['checkupdate'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_3 col_6"><?php echo gettext("Show CPU Usage");?>:</div>
			<div class="config_text row_3 col_7"><input type="checkbox" name="showcpulast" value="True" <?php if($ini['Hardware']['showcpulast'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_4 col_1"><?php echo gettext("Enable Sound");?>:</div>
			<div class="config_text row_4 col_4"><input type="checkbox" name="beeper_enabled" value="True" <?php if($ini['Sound']['beeper_enabled'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_4 col_6"><?php echo gettext("Beep at Start");?>:</div>
			<div class="config_text row_4 col_7"><input type="checkbox" name="beeper_on_start" value="True" <?php if($ini['Sound']['beeper_on_start'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_5 col_1"><?php echo gettext("Enable Maverick receiver");?>:</div>
			<div class="config_text row_5 col_4"><input type="checkbox" name="maverick_enabled" value="True" <?php if($ini['ToDo']['maverick_enabled'] == "True") {echo "checked=\"checked\"";}?> ></div>			
			<?php if ($ini['Hardware']['version'] == "miniV2") { ?>
			<div class="config_text row_5 col_6"><?php echo gettext("Enable TC add on");?>:</div>
			<div class="config_text row_5 col_7"><input type="checkbox" name="max31855" value="True" <?php if($ini['Hardware']['max31855'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<?php } ?>
			<div class="config_text row_6 col_1"><?php echo gettext("View Channels");?>:</div>
			<div class="config_text row_6 col_4"><?php for ($i = 0; $i < $_SESSION["channel_count"] / 2; $i++) {?>
            ch<?php echo $i;?>&nbsp;<input type="checkbox" name="ch_show<?php echo $i;?>" id="show_ch<?php echo $i;?>" value="True" <?php if($ini['ch_show']['ch' . $i] == "True") {echo "checked=\"checked\"";}?> >&nbsp;&nbsp;
            <?php } ?>
            </div>
            <div class="config_text row_7 col_4"><?php for ($i = $_SESSION["channel_count"] / 2; $i < $_SESSION["channel_count"]; $i++) {?>
            ch<?php echo $i;?>&nbsp;<input type="checkbox" name="ch_show<?php echo $i;?>" id="show_ch<?php echo $i;?>" value="True" <?php if($ini['ch_show']['ch' . $i] == "True") {echo "checked=\"checked\"";}?> >&nbsp;&nbsp;
            <?php } ?>
			</div>
		</div>
<?php
// ##################################################################################
// Display Einstellungen ------------------------------------------------------------
// ##################################################################################
?>
		<div class="config small">
			<div class="headline"><?php echo gettext("Display Einstellungen");?></div>		
			<div class="headicon"><img src="../images/icons16x16/display.png" alt=""></div>
			<div class="config_text row_1 col_6"><?php echo gettext("LCD Display");?>:</div>
			<div class="config_text row_1 col_7"><input type="checkbox" name="lcd_show" id="lcd_present" value="True" <?php if($ini['Display']['lcd_present'] == "True") {echo "checked=\"checked\"";}?> ></div>
			<div class="config_text row_2 col_6"><?php echo gettext("LCD Type");?>:</div>
			<div class="config_text row_2 col_7">
				<select name="lcd_type" id="lcd_type" size="1">
					<option <?php if($ini['Display']['lcd_type'] == "wlt_2_lcd_204.py") {echo " selected";} ?> value="wlt_2_lcd_204.py">4x20 HD44780</option>
                    <option <?php if($ini['Display']['lcd_type'] == "wlt_2_nextion.py") {echo " selected";} ?> value="wlt_2_nextion.py">Nextion LCD</option>
                </select>
            </div>
			<div class="config_text row_1 col_1"><?php echo gettext("Start Page");?>:</div>
			<div class="config_text row_1 col_3">
				<select name="lcd_start_page" id="startpage" size="1">
					<option <?php if($ini['Display']['start_page'] == "main") {echo " selected";} ?> value="main"><?php echo gettext("Menu");?></option>
                    <option <?php if($ini['Display']['start_page'] == "temp") {echo " selected";} ?> value="temp"><?php echo gettext("Temperature");?></option>
                </select>
            </div>
            <div class="config_text row_2 col_3"><button type="button" onclick="$.get('config.php?update-nextion=true')" class="wide"><?php echo gettext("Force update!");?></button></div>
	    <div class="config_text row_3 col_3"><button type="button" onclick="$.get('config.php?calibrate-display=true')" class="wide"><?php echo gettext("Calibrate Display!");?></button></div>
	</div>
<?php
// ##################################################################################
// Formular Logging Einstellungen ----------------------------------------------------
// ##################################################################################
?>	
		<div class="config middle">
			<div class="headline"><?php echo gettext("Logging settings");?></div>
			<div class="headicon"><img src="../images/icons16x16/log.png" alt=""></div>
			<div class="config_text row_1 col_1"><?php echo gettext("Logging level pitmaster");?>:</div>
			<div class="config_text row_1 col_4">
				<select name="loglevel_pit" id="loglevel_pit" size="1">
					<?php foreach($log_levels as $log_level) {?>
                    <option<?php if($ini['daemon_logging']['level_pit'] == $log_level) {echo " selected";}; echo " value=\"$log_level\">$log_level"; ?></option>
                    <?php } ?>
                </select>
			</div>
			<div class="config_text row_2 col_1"><?php echo gettext("Logging level watch dog");?>:</div>
			<div class="config_text row_2 col_4">
				<select name="loglevel_wd" id="loglevel_wd" size="1">
					<?php foreach($log_levels as $log_level) {?>
                    <option<?php if($ini['daemon_logging']['level_wd'] == $log_level) {echo " selected";}; echo " value=\"$log_level\">$log_level"; ?></option>
                    <?php } ?>
                </select>
			</div>					
			<div class="config_text row_3 col_1"><?php echo gettext("Logging level main program");?>:</div>
			<div class="config_text row_3 col_4">
				<select name="loglevel_compy" id="loglevel_compy" size="1">
					<?php foreach($log_levels as $log_level) {?>
                    <option<?php if($ini['daemon_logging']['level_compy'] == $log_level) {echo " selected";}; echo " value=\"$log_level\">$log_level"; ?></option>
                    <?php } ?>
                </select>
			</div>
			<div class="config_text row_4 col_1"><?php echo gettext("Logging level display");?>:</div>
			<div class="config_text row_4 col_4">
				<select name="loglevel_display" id="startpage" size="1">
					<?php foreach($log_levels as $log_level) {?>
                    <option<?php if($ini['daemon_logging']['level_display'] == $log_level) {echo " selected";}; echo " value=\"$log_level\">$log_level"; ?></option>
                    <?php } ?>
                </select>       
			</div>
			<div class="config_text row_3 col_6">
                <button type="reset" onclick="location.href='../thermolog/update.log'" class="wide"><?php echo gettext("Show update log")?></button>
            </div>
			<div class="config_text row_4 col_6">
                <button type="reset" onclick="location.href='../log/WLANThermo.log'" class="wide"><?php echo gettext("Show logfile")?></button>
            </div>
		</div>
<?php
// ##################################################################################
// Einstellungen Überprüfen und Felder aktivieren/deaktivieren ----------------------
// ##################################################################################
?>
	<script type="text/javascript" src="../js/config.php.js"></script>
 
<?php

// ##################################################################################
// Speichern/Zurück Button ----------------------------------------------------------
// ##################################################################################
?>
		<br>
			<table align="center" width="80%"><tr><td width="20%"></td>
				<td align="center">
					<input type="submit" class=button_yes name="save"  value="" onclick="enableallcheckbox()">
					<input type="submit" class=button_no name="back"  value=""> </td>
				<td width="20%"></td></tr>
			</table>
		<br>		
	</form>
	<h1><?php echo gettext("Config file upload/download");?></h1>
	<form enctype="multipart/form-data" action="config.php" method="POST">
	<div class="config small">
	<input type="hidden" name="upload_file" value="" />
	<input type="hidden" name="MAX_FILE_SIZE" value="10000" />
		<div class="headline"><?php echo gettext("Config file upload");?></div>
		<div class="headicon"><img src="../images/icons16x16/file_save.png" alt=""></div>
		<div class="config_text row_1 col_1"><?php echo gettext("Config file:");?></div>
		<div class="config_text row_1 col_4"><input name="configfile" type="file" /></div>
		<div class="config_text row_2 col_4">
			<button type="reset" onclick="location.href='../conf/WLANThermo.conf'" class="wide">
				<?php echo gettext("Download config")?>
			</button>
		</div>
	</div>
	<br>
	<table align="center" width="80%">
		<tr>
			<td width="20%"></td>
			<td align="center">
				<input type="submit" class=button_yes value="">
				<input type="submit" class=button_no name="back"  value="">
			</td>
			<td width="20%"></td>
		</tr>
	</table>
	<br>
	</form>
</div>
<?php
	}
// ----------------------------------------------------------------------------------

include("../footer.php");
?>
