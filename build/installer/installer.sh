#!/bin/bash
set -e

if [ `whoami` != root ]; then
    echo "Please run this script as root or using sudo!"
    exit
fi

grep 'VERSION_ID="8"' /etc/os-release &> /dev/null
if [ $? -ne 0 ]; then
  echo "This installer need Raspbian Jessie!"
  exit
fi

lines=`grep --max-count 1 --line-regexp --line-number --text '# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----' $0 | cut -d: -f 1`
startline=$((lines + 1))


if command -v systemctl > /dev/null && systemctl | grep -q '\-\.mount'; then
  SYSTEMD=1
elif [ -f /etc/init.d/cron ] && [ ! -h /etc/init.d/cron ]; then
  SYSTEMD=0
else
  echo "Unrecognised init system"
  return 1
fi

echo "Disable shell and kernel messages on the serial connection"
if [ $SYSTEMD -eq 0 ]; then
  sed -i /etc/inittab -e "s|^.*:.*:respawn:.*ttyAMA0|#&|"
fi
sed -i /boot/cmdline.txt -e "s/console=ttyAMA0,[0-9]\+ //"

program=wlanthermo

echo "Check Ramdrive and create it if it doesn't exist"
RD=$(cat /etc/fstab|grep /var/www/tmp|grep -v grep|wc -l)

if  [ $RD == 0 ]; then
  mkdir /var/www/tmp -p
  mount -t tmpfs -o size=16M,mode=770,uid=www-data,gid=www-data tmpfs /var/www/tmp
  echo "tmpfs           /var/www/tmp    tmpfs   size=16M,mode=770,uid=www-data,gid=www-data     0       0" >> /etc/fstab
  echo -e "[\033[42m\033[30m OK \033[0m] RAM Drive created!"
fi
if  [ $RD != 0 ]; then
  echo -e "[\033[42m\033[30m OK \033[0m] RAM Drive already exists"
fi

echo "Install depencies:"
sudo apt-get update
aptitude --safe-resolver install gnuplot-nox lighttpd apache2-utils python-dev python-serial php5-cgi php5-gd python-pyinotify sudo python-psutil vim htop php5-curl iftop iotop python-urllib3 fswebcam imagemagick -y
echo "Install PIGPIO"
wget -N --directory-prefix=/tmp abyz.co.uk/rpi/pigpio/pigpio.zip && unzip -o /tmp/pigpio.zip -d /tmp/  && make -C /tmp/PIGPIO/ && make install -C /tmp/PIGPIO/
echo "add / modify sudoers entrys"
SU=$(cat /etc/sudoers|grep 'www-data ALL='|wc -l)
sud="www-data ALL=(ALL) NOPASSWD:/sbin/ifdown wlan0,/sbin/ifup wlan0,/bin/cat /etc/wpa_supplicant/wpa_supplicant.conf,/bin/cp /tmp/wifidata /etc/wpa_supplicant/wpa_supplicant.conf,/sbin/wpa_cli scan_results,/sbin/wpa_cli scan,/bin/cp,/bin/sleep,/bin/ps,/usr/bin/fswebcam,/usr/bin/raspi_webcam.sh,/tmp/WLANThermo_install.run,/opt/vc/bin/vcgencmd measure_temp,/usr/sbin/wlt_2_updatenextion.sh"
if [ $SU == 0 ];then
    echo $sud >> /etc/sudoers
else
    sed -i -e "s|www-data ALL=.*|${sud}|g" /etc/sudoers
fi
service sudo restart
echo "Extract the package"
tail -n +$startline $0 > /tmp/${program}.deb
sleep 2
echo 'install /tmp/${programm}.deb'
dpkg -i /tmp/${program}.deb

url=$(cat /etc/hostname)
echo " "
echo "========***********WLANThermo installed completely open http://$url in a browser! ***********==========="
echo " "

exit 0
# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----
