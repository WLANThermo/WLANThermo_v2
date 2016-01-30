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
				$('#webalert_false').live("click",function() {
					$.get('session.php?websoundalert=False', function(data) {

					});
				});
			});	

			$(function() {
				$('#webalert_true').live("click",function() {
					$.get('session.php?websoundalert=True', function(data) {

					});
				});
			});	

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
			
			$(function() {
				$(".dial").knob({
					
				});
			});
