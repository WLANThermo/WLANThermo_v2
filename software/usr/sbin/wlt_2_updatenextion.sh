#!/bin/bash
# Läuft per sudo als root, aufgerufen vom Webinterface:
# wlt_2_updatenextion.sh /usr/share/WLANThermo/nextion/ <Variante>
NEXTION_DIR=/usr/share/WLANThermo/nextion/
if [ "$1" != "$NEXTION_DIR" ] || ! [[ $2 =~ ^[A-Za-z0-9_]+$ ]]
then
    echo 'Ungültige Argumente!'
    exit 1
fi

echo 'Displaydienst wird beendet' > /var/www/tmp/nextionupdatelog
service WLANThermoWD stop
if [ -e '/var/run/wlt_2_nextion.pid' ]
then
   kill $(< /var/run/wlt_2_nextion.pid)
   sleep 5
fi
echo 'Upload wird gestartet' > /var/www/tmp/nextionupdatelog
sleep 1
/usr/local/bin/wlanthermo-nextion-upload "$NEXTION_DIR" "$2" >> /var/www/tmp/nextionupdatelog
RETVAL=$?
[ $RETVAL -eq 0 ] && echo 'Erfolgreich upgedatet!' && rm /var/www/tmp/nextionupdate
[ $RETVAL -ne 0 ] && echo 'Fehler beim Upload!'
sleep 1
echo 'WLANThermodienste werden neu gestartet' >> /var/www/tmp/nextionupdatelog
service WLANThermo restart
service WLANThermoWD start
mv /var/www/tmp/nextionupdatelog /var/www/tmp/nextionupdatelog.old
