		$(function() {	
			if( $.session.get("ToggleStatusPlot") == 1 ) {
				$('#ThermoPlot1').slideDown('slow');
			}
			if( $.session.get("ToggleStatusWebcam") == 1 ) {
				$('#webcam1').slideDown('slow');
			}
			if( $.session.get("ToggleStatusraspicam") == 1 ) {
				$('#raspicam1').slideDown('slow');
			}
		});
		
		$(function() {	
			$('#ThermoPlot_button').click(function() {
				if( $.session.get("ToggleStatusPlot") == 1 ) {
					$('#ThermoPlot1').slideUp('slow');
					$.session.set("ToggleStatusPlot", "NULL");
				}else{
					$('#ThermoPlot1').slideDown('slow');
					$.session.set("ToggleStatusPlot", "1");
				}
			});
			$('#webcam_button').click(function() {
				if( $.session.get("ToggleStatusWebcam") == 1 ) {
					$('#webcam1').slideUp('slow');
					$.session.set("ToggleStatusWebcam", "NULL");
				}else{
					$('#webcam1').slideDown('slow');
					$.session.set("ToggleStatusWebcam", "1");
				}
			});
			$('#raspicam_button').click(function() {
				if( $.session.get("ToggleStatusraspicam") == 1 ) {
					$('#raspicam1').slideUp('slow');
					$.session.set("ToggleStatusraspicam", "NULL");
				}else{
					$('#raspicam1').slideDown('slow');
					$.session.set("ToggleStatusraspicam", "1");
				}
			});
		});
