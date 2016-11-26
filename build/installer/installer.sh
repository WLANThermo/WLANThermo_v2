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


echo "Fixing broken installation (fix for broken installation in 2.5.0)"
dpkg --configure -a

echo "Install depencies:"
sudo apt-get update
aptitude --safe-resolver -y install gnuplot-nox lighttpd apache2-utils python-dev python-serial php5-cgi php5-gd php5-intl python-pyinotify sudo python-psutil vim htop php5-curl iftop iotop python-urllib3 fswebcam imagemagick pigpio python-pigpio python3 python3-serial ntpstat

echo "Extract the package"
tail -n +$startline $0 > /tmp/${program}.deb
sleep 2
echo 'install /tmp/${programm}.deb'
dpkg -i /tmp/${program}.deb

echo "Trying dependencies again... (fix for broken installation in 2.5.0)"
aptitude --safe-resolver -y install gnuplot-nox lighttpd apache2-utils python-dev python-serial php5-cgi php5-gd php5-intl python-pyinotify sudo python-psutil vim htop php5-curl iftop iotop python-urllib3 fswebcam imagemagick pigpio python-pigpio python3 python3-serial ntpstat

url=$(cat /etc/hostname)
echo " "
echo "========***********WLANThermo installed completely open http://$url in a browser! ***********==========="
echo " "

exit 0
# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----
