	// Eingabefelder für PID Regelung deaktivieren
	function pit_settings_disable() {
		/* TODO: implement multiple Pitmaster
		document.getElementById("pit_curve").disabled=true;
		document.getElementById("pit_kp").disabled=true;
		document.getElementById("pit_ki").disabled=true;
		document.getElementById("pit_kd").disabled=true;
		document.getElementById("pit_kp_a").disabled=true;
		document.getElementById("pit_ki_a").disabled=true;
		document.getElementById("pit_kd_a").disabled=true;
		document.getElementById("pit_controller_type").disabled=true;
		document.getElementById("pit_inverted").disabled=true;
		document.getElementById("pit_open_lid_detection").disabled=true;
		document.getElementById("pit_type").disabled=true;
		document.getElementById("pit_ch").disabled=true;
		document.getElementById("pit_pause").disabled=true;
		document.getElementById("pit_set").disabled=true;
		document.getElementById("pit_servo_min").disabled=true;
		document.getElementById("pit_servo_max").disabled=true;
		document.getElementById("pit_pwm_max").disabled=true;
		document.getElementById("pit_pwm_min").disabled=true;
		document.getElementById("pit_io_gpio").disabled=true;
		*/
	}
	
	function pit_settings_enable() {
		document.getElementById("pit_curve").disabled=false;
		document.getElementById("pit_kp").disabled=false;
		document.getElementById("pit_ki").disabled=false;
		document.getElementById("pit_kd").disabled=false;
		document.getElementById("pit_kp_a").disabled=false;
		document.getElementById("pit_ki_a").disabled=false;
		document.getElementById("pit_kd_a").disabled=false;
		document.getElementById("pit_controller_type").disabled=false;
		document.getElementById("pit_inverted").disabled=false;
		document.getElementById("pit_open_lid_detection").disabled=false;
		document.getElementById("pit_type").disabled=false;
		document.getElementById("pit_ch").disabled=false;
		document.getElementById("pit_pause").disabled=false;
		document.getElementById("pit_set").disabled=false;		
		document.getElementById("pit_servo_min").disabled=false;
		document.getElementById("pit_servo_max").disabled=false;
		document.getElementById("pit_pwm_min").disabled=false;
		document.getElementById("pit_pwm_max").disabled=false;
		// document.getElementById("pit_io_gpio").disabled=false;
	}
	
	function pid_settings_disable() {
		/* TODO: implement multiple Pitmaster
		document.getElementById("pit_kp").disabled=true;
		document.getElementById("pit_ki").disabled=true;
		document.getElementById("pit_kd").disabled=true;
		document.getElementById("pit_kp_a").disabled=true;
		document.getElementById("pit_ki_a").disabled=true;
		document.getElementById("pit_kd_a").disabled=true;
		*/
	}
	
	// Eingabefelder für PID Regelung aktivieren
	function pid_settings_enable() {
		/* TODO: implement multiple Pitmaster
		document.getElementById("pit_kp").disabled=false;
		document.getElementById("pit_ki").disabled=false;
		document.getElementById("pit_kd").disabled=false;
		document.getElementById("pit_kp_a").disabled=false;
		document.getElementById("pit_ki_a").disabled=false;
		document.getElementById("pit_kd_a").disabled=false;
		*/
	}

	// Eingabefelder für Plot Dienst deaktivieren
	function plot_settings_disable() {
		document.getElementById("plot_size").disabled=true;
		document.getElementById("plot_name").disabled=true;
		document.getElementById("plotbereich_min").disabled=true;
		document.getElementById("plotbereich_max").disabled=true;
		document.getElementById("plot_keybox").disabled=true;
		document.getElementById("plot_keyboxframe").disabled=true;
		document.getElementById("plot_pit").disabled=true;
		document.getElementById("plot_color_pit").disabled=true;
	}
	
	// Eingabefelder für Plot Dienst aktivieren
	function plot_settings_enable() {
		document.getElementById("plot_size").disabled=false;
		document.getElementById("plot_name").disabled=false;
		document.getElementById("plotbereich_min").disabled=false;
		document.getElementById("plotbereich_max").disabled=false;
		document.getElementById("plot_keybox").disabled=false;
		document.getElementById("plot_keyboxframe").disabled=false;
		document.getElementById("plot_pit").disabled=false;
		document.getElementById("plot_color_pit").disabled=false;
	}
		
	// Eingabefelder für Telegram Einstellungen aktivieren
	function telegram_settings_enable() {
		document.getElementById("telegram_token").disabled=false;
		document.getElementById("telegram_chat_id").disabled=false;
	}
	// Eingabefelder für Telegram Einstellungen deaktivieren
	function telegram_settings_disable() {
		document.getElementById("telegram_token").disabled=true;
		document.getElementById("telegram_chat_id").disabled=true;
	}
	// Eingabefelder für Push Einstellungen aktivieren
	function push_settings_enable() {
		document.getElementById("push_body").disabled=false;
		document.getElementById("push_url").disabled=false;
	}
	// Eingabefelder für Push Einstellungen deaktivieren
	function push_settings_disable() {
		document.getElementById("push_body").disabled=true;
		document.getElementById("push_url").disabled=true;
	}	
	// Eingabefelder für das Nextion Display deaktivieren
	function nextion_settings_disable() {
		document.getElementById("startpage").disabled=true;
	}

	// Eingabefelder für das Nextion Display aktivieren
	function nextion_settings_enable() {
		document.getElementById("startpage").disabled=false;
	}

	// Eingabefelder für Display deaktivieren
	function lcd_settings_disable() {
		nextion_settings_disable();
		document.getElementById("lcd_type").disabled=true;
	}

	// Eingabefelder für Display aktivieren
	function lcd_settings_enable() {
		nextion_settings_enable();
		document.getElementById("lcd_type").disabled=false;
	}

	// Überprüfen welcher LCD Type ausgewählt ist
	function check_lcd_type() {
		if ($('select#lcd_type').val() == 'wlt_2_nextion.py'){
			nextion_settings_enable();
		} else{
			nextion_settings_disable();
		}
	}	

	function check_push_present() {
		if( $('#push_on').is(':checked') ) { 
			push_settings_enable();
		} else{
			push_settings_disable();
		}
	}	
	function check_pit_present() {
		if( $('#pit_on').is(':checked') ) { 
			pit_settings_enable();
			check_pid_present();
			/* TODO: implement multiple Pitmaster
			if($('select#pit_type').val() == "servo"){
				document.getElementById("pit_pwm_min").disabled=true;
				document.getElementById("pit_pwm_max").disabled=true;
				document.getElementById("pit_io_gpio").disabled=true;
			}
			if(($('select#pit_type').val() == "fan") || ($('select#pit_type').val() == "fan_pwm")){
				document.getElementById("pit_servo_min").disabled=true;
				document.getElementById("pit_servo_max").disabled=true;
				document.getElementById("pit_io_gpio").disabled=true;
			}
			if(($('select#pit_type').val() == "io") || ($('select#pit_type').val() == "io_pwm")){
				document.getElementById("pit_servo_min").disabled=true;
				document.getElementById("pit_servo_max").disabled=true;
			}
			*/

		}else{
			pit_settings_disable();
		}	
	}
	function check_pid_present(){
		if( $('#pit_controller_type').is(':checked') ) { 
			pid_settings_enable();
			/* TODO: implement multiple Pitmaster
			document.getElementById("pit_curve").disabled=true;
			*/
		}else{
			pid_settings_disable();
			document.getElementById("pit_curve").disabled=false;
		}
	}
	function check_lcd_present(){
		if( $('#lcd_present').is(':checked') ) { 
			lcd_settings_enable();
			check_lcd_type();
		}else{
			lcd_settings_disable();
		}
	}
	function check_telegram_present(){
		if( $('#telegram_alert').is(':checked') ) { 
			telegram_settings_enable();
		}else{
			telegram_settings_disable();
		}
	}
	function check_plot_present() {
		if( $('#plot_start').is(':checked') ) { 
			plot_settings_enable();
		}else{
			plot_settings_disable();
		}
	}
	function webcam_settings_enable(){
		document.getElementById("webcam_name").disabled=false;
		document.getElementById("webcam_size").disabled=false;
	}

	function webcam_settings_disable(){
		document.getElementById("webcam_name").disabled=true;
		document.getElementById("webcam_size").disabled=true;
	}

	function raspicam_settings_enable(){
		document.getElementById("raspicam_name").disabled=false;
		document.getElementById("raspicam_size").disabled=false;
		document.getElementById("raspicam_exposure").disabled=false;
	}

	function raspicam_settings_disable(){
		document.getElementById("raspicam_name").disabled=true;
		document.getElementById("raspicam_size").disabled=true;
		document.getElementById("raspicam_exposure").disabled=true;
	}

	function check_webcam(){
		if( $('#webcam_start').is(':checked') ) { 
			webcam_settings_enable();	
		}else{
			webcam_settings_disable();
		}
	}

	function check_raspicam(){
		if( $('#raspicam_start').is(':checked') ) { 
			raspicam_settings_enable();
		}else{
			raspicam_settings_disable();
		}
	}

	function email_settings_enable(){
		email_auth_enable();
		document.getElementById("email_to").disabled=false;
		document.getElementById("email_from").disabled=false;
		document.getElementById("email_subject").disabled=false;
		document.getElementById("email_smtp").disabled=false;
		document.getElementById("email_auth_check").disabled=false;
	}

	function email_settings_disable(){
		email_auth_disable();
		document.getElementById("email_to").disabled=true;
		document.getElementById("email_from").disabled=true;
		document.getElementById("email_subject").disabled=true;
		document.getElementById("email_smtp").disabled=true;
		document.getElementById("email_auth_check").disabled=true;
		
	}

	function email_auth_enable(){
		document.getElementById("email_password").disabled=false;
		document.getElementById("email_username").disabled=false;
		document.getElementById("email_starttls").disabled=false;
	}

	function email_auth_disable(){
		document.getElementById("email_password").disabled=true;
		document.getElementById("email_username").disabled=true;
		document.getElementById("email_starttls").disabled=true;
	}

	function check_email_auth(){
		if( $('#email_auth_check').is(':checked') ) { 
			email_auth_enable();
		}else{
			email_auth_disable();
		}
	}	

	function check_email_present(){
		if( $('#email').is(':checked') ) { 
			email_settings_enable();
			check_email_auth();
		}else{
			email_settings_disable();
		}
	}

	function check_channel_ch0(){
		if( $('#show_ch0').is(':checked') ) { 
			$( "#ch0" ).show();
		}else{
			$( "#ch0" ).hide();
		}
	}

	function check_channel_ch1(){
		if( $('#show_ch1').is(':checked') ) { 
			$( "#ch1" ).show();
		}else{
			$( "#ch1" ).hide();
		}
	}

	function check_channel_ch2(){
		if( $('#show_ch2').is(':checked') ) { 
			$( "#ch2" ).show();
		}else{
			$( "#ch2" ).hide();
		}
	}

	function check_channel_ch3(){
		if( $('#show_ch3').is(':checked') ) { 
			$( "#ch3" ).show();
		}else{
			$( "#ch3" ).hide();
		}
	}

	function check_channel_ch4(){
		if( $('#show_ch4').is(':checked') ) { 
			$( "#ch4" ).show();
		}else{
			$( "#ch4" ).hide();
		}
	}

	function check_channel_ch5(){
		if( $('#show_ch5').is(':checked') ) { 
			$( "#ch5" ).show();
		}else{
			$( "#ch5" ).hide();
		}
	}

	function check_channel_ch6(){
		if( $('#show_ch6').is(':checked') ) { 
			$( "#ch6" ).show();
		}else{
			$( "#ch6" ).hide();
		}
	}

	function check_channel_ch7(){
		if( $('#show_ch7').is(':checked') ) { 
			$( "#ch7" ).show();
		}else{
			$( "#ch7" ).hide();
		}
	}
	function enableallcheckbox(){
		//$("input:checkbox").attr('disabled', 'disabled'); //disable
		$("input").removeAttr('disabled'); //enable			
	}
	
	check_telegram_present();
	check_pit_present();
	check_plot_present();
	check_channel_ch0();
	check_channel_ch1();
	check_channel_ch2();
	check_channel_ch3();
	check_channel_ch4();
	check_channel_ch5();
	check_channel_ch6();
	check_channel_ch7();
	check_email_present();
	check_webcam();
	check_raspicam();
	check_lcd_present();
	check_push_present();
	
    $("#pit_type").change(function () {
        check_pit_present();
    });
    $("#push_on").change(function () {
        check_push_present();
    });
    $("#telegram_alert").change(function () {
        check_telegram_present();
    });

	$( "#pit_on" ).change(function() {
		check_pit_present();
	});	
	$( "#pit_controller_type" ).change(function() {
		check_pid_present();
	});	
	$( "#plot_start" ).change(function() {
		check_plot_present();
	});	
	$( "#show_ch0" ).change(function() {
		check_channel_ch0();
	});
	$( "#show_ch1" ).change(function() {
		check_channel_ch1();
	});
	$( "#show_ch2" ).change(function() {
		check_channel_ch2();
	});
	$( "#show_ch3" ).change(function() {
		check_channel_ch3();
	});
	$( "#show_ch4" ).change(function() {
		check_channel_ch4();
	});
	$( "#show_ch5" ).change(function() {
		check_channel_ch5();
	});
	$( "#show_ch6" ).change(function() {
		check_channel_ch6();
	});
	$( "#show_ch7" ).change(function() {
		check_channel_ch7();
	});
	$( "#email" ).change(function() {
		check_email_present();
	});
	$( "#email_auth_check" ).change(function() {
		check_email_auth();
	});
	$( "#lcd_present" ).change(function() {
		check_lcd_present();
	});
	$( "#webcam_start" ).change(function() {
		check_webcam();
	});
	$( "#raspicam_start" ).change(function() {
		check_raspicam();
	});

	// Funktion aufrufen falls LCD Type umgestellt wird
	$( "#lcd_type" ).change(function() {
		check_lcd_type();
	});
	// Funktion aufrufen wenn Seite aufgerufen wird
    
    function fill_telegram_chat_id() {
        $.getJSON("telegram.php?telegram_getid=true&telegram_token="+$('#telegram_token').val(), function(data) {
            $("#telegram_chatid_select").empty();
            $("#telegram_chatid_select").append('<option value="" selected="selected">'+ '---' +'</option>')
            $.each(data, function(){
                $("#telegram_chatid_select").append('<option value="'+ this.id +'" >'+ this.name +' - '+ this.id +'</option>')
            }
            )
        }
        )
    };
    
    $( "#telegram_chatid_select" ).focus(function() {
        fill_telegram_chat_id();
        $( "#telegram_chatid_select" ).select();
    });
    $( "#telegram_chatid_select" ).change(function() {
        var chatid = $( "#telegram_chatid_select option:selected" ).val();
        if (chatid != '') {
            $("#telegram_chat_id").val(chatid);
        }
    });
