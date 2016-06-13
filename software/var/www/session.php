<?php
session_start();

if($_GET["websoundalert"] == "False"){
	$_SESSION['websoundalert'] = "False";
	touch(__DIR__ . '/alert.ack');
}
if($_GET["websoundalert"] == "True"){
	$_SESSION['websoundalert'] = "True";
}
?>