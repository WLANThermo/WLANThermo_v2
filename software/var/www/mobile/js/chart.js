function getChartConfig(){
	var config = {
      type: 'line',
      data: {
        labels: [],
        datasets: [
           {
			   label: "#1",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',           
			   data: []
           },{
			   label: "#2",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#3",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#4",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#5",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#6",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#7",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#8",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#9",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           },{
			   label: "#10",
			   yAxisID: "A",
			   radius: 0,
			   borderColor: 'white',
			   data: []
           }
        ]
      },
	  options:{
		scales:{
			xAxes:[{
			type: 'time',
				time: {
				  displayFormats: {
					'millisecond': 'k:mm:ss',
					'second': 'k:mm:ss',
					'minute': 'k:mm:ss',
					'hour': 'k:mm:ss',
					'day': 'k:mm:ss',
					'week': 'k:mm:ss',
					'month': 'k:mm:ss',
					'quarter': 'k:mm:ss',
					'year': 'k:mm:ss',
				  }
				},
				ticks:{
					autoSkip: true,
					maxTicksLimit: 10
				}
			}],
			yAxes:[{
					id: 'A',
					position: 'right',
					ticks:{
						userCallback: function(label, index, labels) {
							return label.toFixed(1) + '°C';
						}
					}
				},{
					id: 'B',
					position: 'left',
					ticks:{
						min: 0,
						max: 100,
						userCallback: function(label, index, labels) {
							return label + '%';
						}
					}
				},

			]		
		},
		tooltips: {
            enabled: true,
            callbacks: {
                label: function(tooltipItems, data) { 
					if(tooltipItems.datasetIndex == '9'){
						return tooltipItems.yLabel + '%' + ' - ' + ch_name[tooltipItems.datasetIndex];
					}else{
						return tooltipItems.yLabel + '°' + unit + ' - ' + ch_name[tooltipItems.datasetIndex];
					} 
                }
            }
        }
	  }
	};

	return config;
}

function timeConverter(UNIX_timestamp){
  var a = new Date(UNIX_timestamp * 1000);
  var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var year = a.getFullYear();
  var month = months[a.getMonth()];
  var date = a.getDate();
  var hour = a.getHours();
  hour = ("0" + hour).slice(-2);
  var min = a.getMinutes();
  min = ("0" + min).slice(-2);
  var sec = a.getSeconds();
  sec = ("0" + sec).slice(-2);
  var time = date + ' ' + month + ' ' + year + ' ' + hour + ':' + min + ':' + sec ;
  return time;
}