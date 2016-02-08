<?php
session_start();
include('../header.php');
include('../function.php');
$output = $return = 0;

if(isset($_GET['page'])) {
	$page = $_GET['page'];
}else{
	$page = 'wlan0_info';
}
?>
<div class="wifi_site">
	<div class="wifi_header">
		<h1>Raspbian WiFi Configuration Portal</h1>
	</div>
	<div class="wifi_menu">
		<input class="button" type="button" value="WiFi Info" name="wlan0_info" onclick="document.location='?page='+this.name" />
		<input class="button" type="button" value="Einstellungen" name="wpa_conf" onclick="document.location='?page='+this.name" />
	</div>

<div class="wifi_content">

<?php
switch($page) {

	case "wlan0_info":
		exec('ifconfig wlan0',$return);
		exec('iwconfig wlan0',$return);
		$strWlan0 = implode(" ",$return);
		$strWlan0 = preg_replace('/\s\s+/', ' ', $strWlan0);

		if ((preg_match('/HWaddr ([0-9a-f:]+)/i',$strWlan0,$result)) or (preg_match('/Hardware Adresse ([0-9a-f:]+)/i',$strWlan0,$result))){
			$strHWAddress = $result[1];
		}else{
			$strHWAddress = "no result";
		}
		if ((preg_match('/inet addr:([0-9.]+)/i',$strWlan0,$result)) or (preg_match('/inet Adresse:([0-9.]+)/i',$strWlan0,$result))){
			$strIPAddress = $result[1];
		}else{
			$strIPAddress = "no result";
		}
		if ((preg_match('/Mask:([0-9.]+)/i',$strWlan0,$result)) or (preg_match('/Maske:([0-9.]+)/i',$strWlan0,$result))){
			$strNetMask = $result[1];
		}else{
			$strNetMask = "no result";
		}
		if (preg_match('/RX packets:(\d+)/',$strWlan0,$result)){
			$strRxPackets = $result[1];
		}else{
			$strRxPackets = "no result";
		}
		if (preg_match('/TX packets:(\d+)/',$strWlan0,$result)){
			$strTxPackets = $result[1];
		}else{
			$strTxPackets = "no result";
		}
		if (preg_match('/RX Bytes:(\d+ \(\d+.\d+ [K|M|G]iB\))/i',$strWlan0,$result)){
			$strRxBytes = $result[1];
		}else{
			$strRxBytes = "no result";
		}
		if (preg_match('/TX Bytes:(\d+ \(\d+.\d+ [K|M|G]iB\))/i',$strWlan0,$result)){
			$strTxBytes = $result[1];
		}else{
			$strTxBytes = "no result";
		}
		if (preg_match('/ESSID:\"([a-zA-Z0-9\s]+)\"/i',$strWlan0,$result)){
			$strSSID = str_replace('"','',$result[1]);
		}else{
			$strSSID = "no result";
		}
		if (preg_match('/Access Point: ([0-9a-f:]+)/i',$strWlan0,$result)){
			$strBSSID = $result[1];
		}else{
			$strBSSID = "no result";
		}
		if (preg_match('/Bit Rate:([0-9+.]+ Mb\/s)/i',$strWlan0,$result)){
			$strBitrate = $result[1];
		}else{
			$strBitrate = "no result";
		}
		if (preg_match('/Link Quality=([0-9]+\/[0-9]+)/i',$strWlan0,$result)){
			$strLinkQuality = $result[1];
		}else{
			$strLinkQuality = "no result";
		}
		if (preg_match('/Signal Level=([0-9]+\/[0-9]+)/i',$strWlan0,$result)){
			$strSignalLevel = $result[1];
		}else{
			$strSignalLevel = "no result";
		}
		if(strpos($strWlan0, "UP") !== false && strpos($strWlan0, "RUNNING") !== false) {
			$strStatus = '<span style="color:green">Interface is up</span>';
		} else {
			$strStatus = '<span style="color:red">Interface is down</span>';
		}
		if(isset($_POST['ifdown_wlan0'])) {
			exec('ifconfig wlan0 | grep -i running | wc -l',$test);
			if($test[0] == 1) {
				exec('sudo ifdown wlan0',$return);
				echo '<p>Please wait...</p><script type="text/Javascript">window.setTimeout("document.location=\"?page=wlan0_info\"", 5000)</script>';
			} else {
				echo 'Interface already down';
			}
		} elseif(isset($_POST['ifup_wlan0'])) {
			exec('ifconfig wlan0 | grep -i running | wc -l',$test);
			if($test[0] == 0) {
				exec('sudo ifup wlan0',$return);
				echo '<p>Please wait...</p><script type="text/Javascript">window.setTimeout("document.location=\"?page=wlan0_info\"", 5000)</script>';
			} else {
				echo 'Interface already up';
			}
		}
	//print_r($strWlan0);
	echo '<div class="infobox">
<form action="?page=wlan0_info" method="POST">
<input type="submit" value="ifdown wlan0" name="ifdown_wlan0" />
<input type="submit" value="ifup wlan0" name="ifup_wlan0" />
<input type="button" value="Refresh" onclick="document.location.reload(true)" />
</form>
<div class="infoheader">Wireless Information and Statistics</div>
<div id="intinfo"><div class="intheader">Interface Information</div>
Interface Name : <b>wlan0</b><br />
Interface Status : <b>' . $strStatus . '</b><br />
IP Address : <b>' . $strIPAddress . '</b><br />
Subnet Mask : <b>' . $strNetMask . '</b><br />
Mac Address : <b>' . $strHWAddress . '</b><br />
<div class="intheader">Interface Statistics</div>
Received Packets : <b>' . $strRxPackets . '</b><br />
Received Bytes : <b>' . $strRxBytes . '</b><br /><br />
Transferred Packets : <b>' . $strTxPackets . '</b><br />
Transferred Bytes : <b>' . $strTxBytes . '</b><br />
</div>
<div id="wifiinfo">
<div class="intheader">Wireless Information</div>
Connected To : <b>' . $strSSID . '</b><br />
AP Mac Address : <b>' . $strBSSID . '</b><br />
Bitrate : <b>' . $strBitrate . '</b><br />
Link Quality : <b>' . $strLinkQuality . '</b><br />
Signal Level : <b>' . $strSignalLevel . '</b><br />

</div>
</div>
<div class="intfooter">Information provided by ifconfig and iwconfig</div><br style="clear:both;">';
	break;

	case "wpa_conf":
		exec('sudo cat /etc/wpa_supplicant/wpa_supplicant.conf',$return);
		$ssid = array();
		$psk = array();
		foreach($return as $a) {
			if(preg_match('/SSID/i',$a)) {
				$arrssid = explode("=",$a);
				$ssid[] = str_replace('"','',$arrssid[1]);
			}
			if(preg_match('/\#psk/i',$a)) {
				$arrpsk = explode("=",$a);
				$psk[] = str_replace('"','',$arrpsk[1]);
			}
		}
		$numSSIDs = count($ssid);
		$output = '<form name="wpa_conf_form" method="POST" action="?page=wpa_conf" id="wpa_conf_form"><input type="hidden" id="Networks" name="Networks" /><div class="network" id="networkbox">';
		for($ssids = 0; $ssids < $numSSIDs; $ssids++) {
			$output .= '<div id="Networkbox'.$ssids.'" class="NetworkBoxes">Network '.$ssids.' <input type="button" value="Delete" onClick="DeleteNetwork('.$ssids.');" /></span><br />
<span class="tableft" id="lssid0">SSID :</span><input type="text" id="ssid0" name="ssid'.$ssids.'" value="'.$ssid[$ssids].'" onkeyup="CheckSSID(this)" /><br />
<span class="tableft" id="lpsk0">PSK :</span><input type="password" id="psk0" name="psk'.$ssids.'" value="'.$psk[$ssids].'" onkeyup="CheckPSK(this)" /></div>';
		}
		$output .= '</div><input type="submit" value="Scan for Networks" name="Scan" /><input type="button" value="Add Network" onClick="AddNetwork();" />';

	echo $output;
	echo "<p><input type=\"submit\" value=\"Save\" name=\"SaveWPAPSKSettings\" onmouseover=\"UpdateNetworks(this)\" id=\"Save\" disabled /><input type=\"button\" onClick=\"document.location='?page=wpa_conf'\" value=\"Cancel\" id=\"Cancel\" disabled /></p></form>";
	echo '<script type="text/Javascript">UpdateNetworks()</script>';

	if(isset($_POST['SaveWPAPSKSettings'])) {
		$config = 'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

	';
		$networks = $_POST['Networks'];
		for($x = 0; $x <= $networks; $x++) {
			$network = '';
			$ssid = escapeshellarg($_POST['ssid'.$x]);
			$psk = escapeshellarg($_POST['psk'.$x]);
			echo "wpa_passphrase ".$ssid." ".$psk.",".$network."<br>";
			exec('wpa_passphrase '.$ssid. ' ' . $psk,$network);
			echo "network: ".$network[0]."<br>";			
			if ($network[0] <> "Passphrase must be 8..63 characters"){
				foreach($network as $b) {
					$config .= "$b
	";
				}
			}
		}
		exec("echo '$config' > /tmp/wifidata",$return);
		system('sudo cp /tmp/wifidata /etc/wpa_supplicant/wpa_supplicant.conf',$returnval);
		if($returnval == 0) {
			echo "Wifi Settings Updated Successfully";
		} else {
			echo "Wifi settings failed to be updated";
		}
		echo '<script type="text/Javascript">document.location="?page=wpa_conf"</script>';
	} elseif(isset($_POST['Scan'])) {
		$return = '';
		exec('sudo wpa_cli scan',$return);
		sleep(5);
		exec('sudo wpa_cli scan_results',$return);
		for($shift = 0; $shift < 4; $shift++ ) {
			array_shift($return);
		}
		echo "Networks found : <br />";
		
		foreach($return as $network) {
			$arrNetwork = preg_split("/[\t]+/",$network);
			$bssid = $arrNetwork[0];
			$channel = ConvertToChannel($arrNetwork[1]);
			$signal = $arrNetwork[2] . " dBm";
			$security = $arrNetwork[3];
			if(isset($arrNetwork[4])) { 
				$ssid = $arrNetwork[4];
				echo '<input type="button" value="Connect to This network" onClick="AddScanned(\''.$ssid.'\')" />' . $ssid . " on channel " . $channel . " with " . $signal . "(".ConvertToSecurity($security)." Security)<br />";
			}
		}
	}

	break;
}
?>

</div>
</div>
<?php
include("../footer.php");
?>
