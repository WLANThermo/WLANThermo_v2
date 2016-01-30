			$(document).ready(function() {
   				setInterval(function() {
                $('#temp').load('main.php')
				},2000);
			$('#temp').load('main.php');
			});
			
			$(document).ready(function() {						
				$('.edit').editable('edit.php', {
					callback : function(value, settings) {
					window.location.reload();
					}
				});
			});
			
			$(function() {
				$('#webalert_true').live("click",function() {
					$.get('session.php?websoundalert=True', function(data) {

					});
				});
				$('#webalert_false').live("click",function() {
					$.get('session.php?websoundalert=False', function(data) {

					});
				});
			});	
	
			function showLoading(){
					$("#ThermoPlot1").slideUp("slow");
					$("#webcam1").slideUp("slow");
					$("#raspicam1").slideUp("slow");
					$body = $("body");
					$body.addClass("loading");
			}
			function hideLoading(){
					$body = $("body");
					$body.removeClass("loading");
			}
			function showUpdate() {
				var oldSrc = '../images/icons32x32/info.png';
				var newSrc = '../images/icons32x32/infoupdate.png';
				$('img[src="' + oldSrc + '"]').attr('src', newSrc);
			}				
			function hideUpdate() {
				var oldSrc = '../images/icons32x32/infoupdate.png';
				var newSrc = '../images/icons32x32/info.png';
				$('img[src="' + oldSrc + '"]').attr('src', newSrc);
			}			

			$(function() {
				// Instanz einmal ermitteln!
				var container = $('#header_logo');
 
				// den Mauszeiger zu einem Zeigefinger machen (in der Regel alle Links)
				container.css('cursor', 'pointer');
 
				// bei Klick zur jeweiligen Seite
				container.click(function(){
					location.href = $(this).find('a').attr('href');
				});
 
				// Titel vom Link für auch für die neue Verlinkung nutzen
				container.mouseover(function(){
					$(this).attr('title', $(this).find('a').attr('title'));
				});
			});		

		
