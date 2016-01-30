<?php
	session_start();
	include("function.php");
	session("./conf/WLANThermo.conf");
	include("header.php");
//-------------------------------------------------------------------------------------------------------------------------------------	
// Ausgabe der Temperaturen ###########################################################################################################
//-------------------------------------------------------------------------------------------------------------------------------------
?>	
					<div id="temp"></div>
					<div id="ThermoPlot1" style="display: none;">
						<p>
							<img id="ThermoPlot" src="../tmp/temperaturkurve.png" onload="reload(3000)" onerror="reload(1)" alt="">
						</p>
					</div>	

					<div id="webcam1" style="display: none;">
						<p>
						<?php if (file_exists("".$document_root."tmp/webcam.jpg")){ ?>
							<img id="webcam" src="../tmp/webcam.jpg" onload="reload_webcam(9000)" onerror="reload_webcam(1)" alt="">
						<?php } ?>
						</p>
					</div>

					<div id="raspicam1" style="display: none;">
						<p>
						<?php if (file_exists("".$document_root."tmp/raspicam.jpg")){ ?>
							<img id="raspicam" src="../tmp/raspicam.jpg" onload="reload_raspicam(9000)" onerror="reload_raspicam(1)" alt="">
						<?php } ?>
						</p>
					</div>
<?php
include("footer.php");
?>