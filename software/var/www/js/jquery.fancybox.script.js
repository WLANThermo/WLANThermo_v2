$(function() {
	// Instanz einmal ermitteln!
	var container = $('#ThermoPlot1, #webcam1, #raspicam1');
 
	// den Mauszeiger zu einem Zeigefinger machen (in der Regel alle Links)
	container.css('cursor', 'pointer');
});

jQuery(function ($) {
    $("#ThermoPlot1 img").click(function(e) {
		var ts = new Date().getTime();
		$.fancybox([
			'/tmp/temperaturkurve.png?'+ ts +'',
		],{
		// fancybox options 
		'type': 'image' // etc.
		//'loop'              : true,
        //'autoPlay'          : true,
        //'playSpeed'         : 4000
		}); // fancybox
    });
});

jQuery(function ($) {
    $("#webcam1 img").click(function(e) {
		var ts = new Date().getTime();
		$.fancybox([
			'/tmp/webcam.jpg?'+ ts +'',
		],{
		// fancybox options 
		'type': 'image' // etc.
		//'loop'              : true,
        //'autoPlay'          : true,
        //'playSpeed'         : 4000
		}); // fancybox
    });
});

jQuery(function ($) {
    $("#raspicam1 img").click(function(e) {
		var ts = new Date().getTime();
		$.fancybox([
			'/tmp/raspicam.jpg?'+ ts +'',
		],{
		// fancybox options 
		'type': 'image' // etc.
		//'loop'              : true,
        //'autoPlay'          : true,
        //'playSpeed'         : 4000
		}); // fancybox
    });
});

if ($.fancybox.isOpened) {
	$(".fancybox-inner").find("img").attr('src', src + "?time=" + timestamp);
}

$(document).ready(function () {
	$(".fancybox").fancybox();
});

