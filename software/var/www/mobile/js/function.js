    // ----------------------------------------------------------------------------------- 
	var byId = function( id ) { return document.getElementById( id ); };
	var byClass = function( id ) { return document.getElementsByClassName( id ); };
	var getIcon = function( icon ) { return '<span class="icon-'  + icon + '"></span>'; };
	byId('index').style.display = "inline";
	var unit = '°';
	var pit_act = false;
	var ch_name = new Array('#1', '#2', '#3', '#4', '#5', '#6', '#7', '#8', '#9', '#10');
	// -----------------------------------------------------------------------------------
	// Menü
	(function (window, document) {
		var layout = byId('layout'),menu = byId('menu'),menuLink = byId('menuLink'),menuHome = byId('menuHome'),menuAbout = byId('menuAbout'),content  = byId('main');
		function toggleClass(element, className) {
			var classes = element.className.split(/\s+/), length = classes.length, i = 0;
			for(; i < length; i++) {
			  if (classes[i] === className) {
				classes.splice(i, 1);
				break;
			  }
			}
			// The className is not found
			if (length === classes.length) {
				classes.push(className);
			}
			element.className = classes.join(' ');
		}

		function toggleAll(e) {
			var active = 'active';
			e.preventDefault();
			toggleClass(layout, active);
			toggleClass(menu, active);
			toggleClass(menuLink, active);
		}

		menuLink.onclick = function (e) {toggleAll(e);};
		menuHome.onclick = function (e) {if (menu.className.indexOf('active') !== -1) {toggleAll(e);showIndex();}};
		menuAbout.onclick = function (e) {if (menu.className.indexOf('active') !== -1) {toggleAll(e);showAbout();}};
		content.onclick = function(e) {if (menu.className.indexOf('active') !== -1) {toggleAll(e);}};
	}(this, this.document));
	// -----------------------------------------------------------------------------------

	
	document.addEventListener("DOMContentLoaded", function(event) { 
		setInterval("readTemp();", 2000);
	});
				
	function showLoader(show){
		if (show == 'true') {
			byId('cover').classList.add("cover_active");
			byId('spinner').classList.add("spinner");		
		}else{
			byId('cover').classList.remove("cover_active");
			byId('spinner').classList.remove("spinner");
		}
	}	
	
	function showIndex(){
		hideAll();
		byId('index').style.display = "inline";
	}
	
	function showAbout(){
		hideAll();
		byId('about').style.display = "inline";
	}	

	function hideAll(){
		hideIDs = ['index','about'];
		for (var i = 0; i < hideIDs.length; i++) {
			byId(hideIDs[i]).style.display = "none";
		}
	}
	
    function loadJSON(url, data, timeout, callback) {
        var xobj = new XMLHttpRequest();
        xobj.overrideMimeType("application/json");
        xobj.open('POST', url, true);
        xobj.setRequestHeader("Content-Type", "application/json");
		xobj.timeout = timeout;
        xobj.onreadystatechange = function () {
            if (xobj.readyState == 4 && xobj.status == "200") {
                callback(xobj.responseText);
            }
        }
		xobj.ontimeout = function (e) {

		};
        xobj.send(data);
    }
	
	var channels_api = "../app.php"; // API der Kanäle 
	var refreshInterval = "5000"; // Refresh Intervall in ms der Temp Werte
	var getTimeout = "10000"; // Timeout der get API's
	
	$(document).ready(function(){
		readTemp();
		setInterval("readTemp();", refreshInterval);	
	});

	function addChannel(){
		$( ".channel_template:first" ).children().clone().appendTo(".channel_index:last");
		$(".channel_index").children().last().addClass("temp_index");
		$(".channel_index").children().last().click(function () {
			showSetChannel(this.getElementsByClassName('chnumber')[0].innerHTML);
		});	
	}
	
	function removeChannel(){
		$(".channel_index").children().last().remove();
	}
	
	function readTemp(){
			loadJSON(channels_api, '', getTimeout, function (response) {
				jr = JSON.parse(response);				
				var channel_length = 0;
				for(var temp in jr.channel){
					channel_length++;
				}
			    while ($(".channel_index").children().length < channel_length) {
					addChannel();
				}
				while ($(".channel_index").children().length > channel_length) {
					removeChannel();
				}					
				var channel_index = 0;
				byId('thermoname').innerHTML = jr.timestamp;

				for(var channel in jr.channel){
					byClass("temp_index")[channel_index].getElementsByClassName('1-box channel')[0].style.borderColor = jr.channel[channel].color;
					byClass("temp_index")[channel_index].getElementsByClassName('chtitle')[0].innerHTML = jr.channel[channel].name;
					var chnumber = channel_index + 1;
					byClass("temp_index")[channel_index].getElementsByClassName('chnumber')[0].innerHTML = "#" + chnumber;
					byClass("temp_index")[channel_index].getElementsByClassName('tempmin')[0].innerHTML = getIcon('temp_down') + jr.channel[channel].temp_min + "°";
					byClass("temp_index")[channel_index].getElementsByClassName('tempmax')[0].innerHTML = getIcon('temp_up') + jr.channel[channel].temp_max + "°";
					if (jr.channel[channel].state == 'er'){
						byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].innerHTML = 'OFF';
						byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.color = "#FFFFFF";		
						byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.fontWeight = 'normal';
						byClass("temp_index")[channel_index].style.display = 'none';
					}else{
						byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].innerHTML = jr.channel[channel].temp.toFixed(1) + "°C";
						if (jr.channel[channel].temp < jr.channel[channel].alert_low_limit){
							byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.color = "#1874cd";
							byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.fontWeight = 'bold';
						}else if (jr.channel[channel].temp > jr.channel[channel].alert_high_limit){
							byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.color = "red";
							byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.fontWeight = 'bold';
						}else{
							byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.color = "#FFFFFF";
							byClass("temp_index")[channel_index].getElementsByClassName('temp')[0].style.fontWeight = 'normal';
						}
						byClass("temp_index")[channel_index].style.display = 'inline';
					}						
					channel_index++;
				}
				addData(jr.timestamp,jr.channel);
			})
	}

	function validateNumber(number,decimal) {
		val = number.value.replace(/[^0-9.,]/g,'').replace(/[,]/g, '.');
		switch(decimal) {
			case '1': 
				if(val){val = val.toString().match(/^-?\d+(?:\.\d{0,1})?/)[0];}
				break;
			case '2': 
				if(val){val = val.toString().match(/^-?\d+(?:\.\d{0,2})?/)[0];}
				break;
			case '3':
				if(val){val = val.toString().match(/^-?\d+(?:\.\d{0,3})?/)[0];}
				break;
			case '4':
				if(val){val = val.toString().match(/^-?\d+(?:\.\d{0,4})?/)[0];}
				break;
			default:
				if(val){val = val.toString().match(/^-?\d+(?:\.\d{0,1})?/)[0];}
		} 
		if(val.split('.').length>2){val = val.replace(/\.+$/,"");}		
		number.value = val;
	}
//---------------------------
	
// Chart config
// ----------------------------------------------------------------------------	
	Chart.defaults.global.animationSteps = 50;
	Chart.defaults.global.tooltipYPadding = 16;
	Chart.defaults.global.tooltipCornerRadius = 0;
	Chart.defaults.global.defaultFontColor= 'white';
	Chart.defaults.global.tooltipTitleFontStyle = "normal";
	Chart.defaults.global.tooltips.mode = "index";
	Chart.defaults.global.tooltips.intersect = false;
	Chart.defaults.global.legend.labels.boxWidth = 15;
	Chart.defaults.global.animationEasing = "easeOutBounce";
	Chart.defaults.global.responsive = true;
	Chart.defaults.global.scaleFontSize = 16;
	var myContext = document.getElementById("nanoChart");		
	var nanoChart = new Chart(myContext, getChartConfig());   
	var ch_name_chart = new Array("Kanal 0","Kanal 1","Kanal 2","Kanal 3","Kanal 4","Kanal 5","Kanal 6","Kanal 7","Kanal 8","Kanal 9");
	function loadChartHistory(){  
		inc_row = 10;
		url = "../thermolog/TEMPLOG.csv";
		Papa.parse(url+"?_="+ (new Date).getTime(), {
			download: true,
			header: true,
			step: function(row) {	
				if(inc_row == 10){
					inc_row = 0;
					var parseArray = ["Datum_Uhrzeit","Kanal 0","Kanal 1","Kanal 2","Kanal 3","Kanal 4","Kanal 5","Kanal 6","Kanal 7","Kanal 8","Kanal 9","Regler Ausgangswert","Regler Sollwert","Regler 2 Ausgangswert","Regler 2 Sollwert"];
					if(isset(row.data[0]['Datum_Uhrzeit'])){
						var timestamp = moment(row.data[0]['Datum_Uhrzeit'].replace(/\./g, '-'), 'DD-MM-YY HH:mm:ss').unix();
						timestamp = timeConverter(timestamp);
						nanoChart.data.labels.push(timestamp);
						for(var i=0; i<ch_name_chart.length; i++) {
							if(isset(row.data[0]['Kanal ' + i]) && row.data[0]['Kanal ' + i].length > 0){
								nanoChart.data.datasets[i].data.push(row.data[0]['Kanal ' + i]);
							}else{
								nanoChart.data.datasets[i].data.push(null);
								
							}
							nanoChart.data.datasets[i].borderColor = 'white';
							nanoChart.data.datasets[i].backgroundColor = 'white';
							nanoChart.data.datasets[i].fill = false;
						}
					}
				}else{
					inc_row++;
				}
			},
			complete: function(results) {
				nanoChart.update();
			}
		});
	};

	function addData(timestamp,channel) {
		var timestamp = timestamp.replace(/\./g, '-');
		var timestamp = timestamp.replace(/\T/g, ' '); 
		//console.log(timestamp);
		var timestamp = moment(timestamp, 'YYYY-MM-DD HH:mm:ss').unix();
		//console.log(timestamp);
		timestamp = timeConverter(timestamp);
		nanoChart.data.labels.push(timestamp);
		for(var i in channel){	
			nanoChart.data.datasets[i].borderColor = channel[i].color;
			nanoChart.data.datasets[i].backgroundColor = channel[i].color;
			nanoChart.data.datasets[i].fill = false;			
			if (channel[i].state == 'er'){
				nanoChart.data.datasets[i].data.push(null);
			}else{
				nanoChart.data.datasets[i].data.push(channel[i].temp.toFixed(1));		
			}			
		}
		nanoChart.update();
	}
	
	function isset(variable){
		return (typeof v === 'undefined');
	}
readTemp();	
loadChartHistory();	

	