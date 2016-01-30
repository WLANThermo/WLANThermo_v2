    function bildreload()
		{ var number = Math.random();
     if(document.layers)
		document.ThermoPlot1.document.Cam.src = '../tmp/temperaturkurve.png?'+ number +'';
     else
		document.ThermoPlot.src = '../tmp/temperaturkurve.png?'+ number +''; 
	}

    function reload(zeit)
    { window.setTimeout("bildreload()",[zeit]); }
    window.onerror = "return true";
	
    function webcam()
    { var number = Math.random();
     if(document.layers)
    document.webcam1.document.Cam.src = '../tmp/webcam.jpg?'+ number +'';
     else
    document.webcam.src = '../tmp/webcam.jpg?'+ number +''; 
	}
    function reload_webcam(zeit)
    { window.setTimeout("webcam()",[zeit]); }
    window.onerror = "return true";
	
    function raspicam()
		{ var number = Math.random();
     if(document.layers)
		document.raspicam1.document.Cam.src = '../tmp/raspicam.jpg?'+ number +'';
     else
		document.raspicam.src = '../tmp/raspicam.jpg?'+ number +''; 
	}

    function reload_raspicam(zeit)
    { window.setTimeout("raspicam()",[zeit]); }
    window.onerror = "return true";	

	function reload_body() {
       bildreload();
       garden();
	   raspicam();
    }