#!/bin/bash

service WLANThermoNEXTION stop
python /usr/sbin/nextionupload.py $1 >/var/www/tmp/nextionupdatelog
service WLANThermo restart
service WLANThermoWD restart
service WLANThermoNEXTION restart
rm /var/www/tmp/nextionupdatelog
 









