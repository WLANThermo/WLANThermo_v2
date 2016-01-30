<?php
session_start();

if($_GET["websoundalert"] == "False"){
	$_SESSION['websoundalert'] = "False";
}
if($_GET["websoundalert"] == "True"){
	$_SESSION['websoundalert'] = "True";
}
?>