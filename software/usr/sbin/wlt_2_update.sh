#!/bin/bash

if [ -f /var/www/tmp/error_wget ]
    then
        rm /var/www/tmp/error_wget
fi

url_conf=`cat /var/www/conf/WLANThermo.conf | awk '/url = h/'`
url=${url_conf:5}
LANG=C wget -O  /tmp/WLANThermo_install.run $url -o /tmp/wgetOut
# sleep 3

_wgetHttpCode=`cat /tmp/wgetOut | awk '/response.../{ print $6 }'`
# echo "$_wgetHttpCode"

if [ "$_wgetHttpCode" != "200" ]; then
    echo "[Error] `cat /tmp/wgetOut`" >/var/www/tmp/error_wget
    cat /var/www/tmp/error_wget >/var/log/WLAN_Thermo/update.log
    echo 'Download fehlgeschlagen!' >>/var/log/WLAN_Thermo/update.log
    rm /var/www/tmp/update
    exit
fi
cat /tmp/wgetOut >/var/log/WLAN_Thermo/update.log

chmod +x /tmp/WLANThermo_install.run >>/var/log/WLAN_Thermo/update.log
sudo /tmp/WLANThermo_install.run >>/var/log/WLAN_Thermo/update.log










