		$(function() {	
			if( $.session.get("ToggleStatusPlot") == 1 ) {
				$('.ThermoPlot').slideDown('slow');
			}
		});

		$(function() {	
			if( $.session.get("ToggleStatusWebcam") == 1 ) {
				$('.webcam').slideDown('slow');
			}
		});
		$(function() {	
			if( $.session.get("ToggleStatusraspicam") == 1 ) {
				$('.raspicam').slideDown('slow');
			}
		});
		
		$(function() {	
			$('#ThermoPlot_button').click(function() {
				if( $.session.get("ToggleStatusPlot") == 1 ) {
					$('.ThermoPlot').slideUp('slow');
					$.session.set("ToggleStatusPlot", "NULL");
				}else{
					$('.ThermoPlot').slideDown('slow');
					$.session.set("ToggleStatusPlot", "1");
				}
			});
		});

		$(function() {	
			$('#webcam_button').click(function() {
				if( $.session.get("ToggleStatusWebcam") == 1 ) {
					$('.webcam').slideUp('slow');
					$.session.set("ToggleStatusWebcam", "NULL");
				}else{
					$('.webcam').slideDown('slow');
					$.session.set("ToggleStatusWebcam", "1");
				}
			});
		});
		$(function() {	
			$('#raspicam_button').click(function() {
				if( $.session.get("ToggleStatusraspicam") == 1 ) {
					$('.raspicam').slideUp('slow');
					$.session.set("ToggleStatusraspicam", "NULL");
				}else{
					$('.raspicam').slideDown('slow');
					$.session.set("ToggleStatusraspicam", "1");
				}
			});
		});