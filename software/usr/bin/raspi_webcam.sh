#!/bin/bash

if [ ! -e /usr/bin/fswebcam ]
    then 
     echo 'fswebcam nicht installiert! Exiting ....'
     exit 0
fi

if [ ! -e /usr/bin/raspistill ]
    then 
     echo 'Raspitools nicht installiert! Exiting ....'
     exit 0
fi

 



if [ $1 == 'W' ] || [ $1 == 'R' ]
    then 
     Typ=$1
    else 
     Typ="Falscher Typ";
     echo $Typ;
     exit 0;
fi

if [ -z $2 ]
    then
    echo 'Kein Dateiname angegeben!'
    exit 0
fi

#Dateiname fuer Output
imk=$2



#Breite
breite=$3
#Höhe
hoehe=$4
#Position des Textes für Raspicam
anno=$((hoehe-8))

#Zeit eindeutig festlegen
imt=`date --rfc-2822`
imf=`date -d "$imt" +%Y%m%d%H%M%S`
irt=`date -d "$imt" +%e.' '%B' '%Y' | '%H:%M' Uhr'`

#Text im Webcambild

brand=$5 

pt=$brand' | '$irt

# exposure für Raspicam

exposure=$6

#Pfad 
imp=/var/www/tmp/

#Dateiname fuer Bild ohne Text 
img=webcam_ohne.jpg

#Pfad und Dateiname Input-Bild
impn=$imp$img

#Pfad und Dateiname Output-Bild
impk=$imp$imk

case "$Typ" in 

    'R')
	if [ -e /var/www/tmp/raspi.txt ] 
	    then
		echo '#Bild wird schon aufgenommen, beenden'
		exit 0
	    else
		#Test-Datei setzen
		touch /var/www/tmp/raspi.txt
		#Bild aufnehmen und speichern
		/usr/bin/raspistill -w $breite -h $hoehe -ex $exposure -q 75 -o $impn 2>/dev/null
		#Bild kleinrechnen und beschriften
                /usr/bin/convert $impn -font bookman-demi -fill white -pointsize 20 -annotate 0x0+20+$anno "$pt" $impk 2> /dev/null
		rm /var/www/tmp/raspi.txt
	    fi
	;;
    'W')
	if [ -e /var/www/tmp/webcam.txt ] 
	    then
		echo '#Bild wird schon aufgenommen, beenden'
		exit 0
	    else
		#Test-Datei setzen
		touch /var/www/tmp/webcam.txt
		echo '#Bild aufnehmen und speichern'
		/usr/bin/fswebcam -S 5 -r $breite'x'$hoehe --jpeg 95 --no-timestamp  --title "$pt" -d /dev/video0 $impk /dev/null 
		rm /var/www/tmp/webcam.txt
	    fi
	;;
esac

exit 0
