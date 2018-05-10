<?php
	session_start();
	require_once("function.php");
	session("./conf/WLANThermo.conf");
	include("header.php");
//-------------------------------------------------------------------------------------------------------------------------------------	
// Ausgabe der Temperaturen ###########################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
?>	
					<div id="temp"></div>
					<div id="ThermoPlot1" class="ThermoPlot" style="display: none;">
						<p>
							<img name="ThermoPlot" id="ThermoPlot" src="../tmp/temperaturkurve.png" onload="reload(3000)" onerror="reload(3000)" alt="">
						</p>
					</div>	

					<div id="webcam1" class="webcam" style="display: none;">
						<p>
						<?php if (file_exists("".$document_root."/tmp/webcam.jpg")){ ?>
							<img name="webcam" id="webcam" src="../tmp/webcam.jpg" onload="reload_webcam(9000)" onerror="reload_webcam(3000)" alt="">
						<?php } ?>
						</p>
					</div>

					<div id="raspicam1" class="raspicam" style="display: none;">
						<p>
						<?php if (file_exists("".$document_root."/tmp/raspicam.jpg")){ ?>
							<img name="raspicam" id="raspicam" src="../tmp/raspicam.jpg" onload="reload_raspicam(9000)" onerror="reload_raspicam(3000)" alt="">
						<?php } ?>
						</p>
					</div>

<?php
include("footer.php");
?>