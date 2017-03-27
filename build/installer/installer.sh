#!/bin/bash

echo "Starting WLANThermo installation"
echo "----------------------------------------------------------"

if [ `whoami` != root ]; then
    echo "Please run this script as root or using sudo!"
    exit
fi
  
grep 'VERSION_ID="8"' /etc/os-release &> /dev/null
if [ $? -ne 0 ]; then
  echo "This installer need Raspbian Jessie!"
  exit
fi

if [ "$1" == "--image-mode" ]; then
  IMAGE_MODE=TRUE
else
  IMAGE_MODE=FALSE
fi

#
# Stop processes to speed up installation
#
if [ "$IMAGE_MODE" == "FALSE" ]; then
  echo "Stopping WLANThermo processes"
  echo "----------------------------------------------------------"
  systemctl stop WLANThermo.service
  systemctl stop pigpiod.service
  if [ -f /var/run/wlt_2_nextion.pid ]; then
    kill $(cat /var/run/wlt_2_nextion.pid)
  fi
  pkill gnuplot
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
echo "----------------------------------------------------------"
if [ $SYSTEMD == 0 ]; then
  sed -i /etc/inittab -e "s|^.*:.*:respawn:.*ttyAMA0|#&|"
fi
sed -i /boot/cmdline.txt -e "s/console=ttyAMA0,[0-9]\+ //"
sed -i /boot/cmdline.txt -e "s/console=serial0,[0-9]\+ //"

echo "Enabling locales"
echo "----------------------------------------------------------"
sed -i.old /etc/locale.gen -re "s/^(\s*#\s*)(de_DE.UTF-8 UTF-8.*)$/\2/m"
sed -i.old /etc/locale.gen -re "s/^(\s*#\s*)(en_GB.UTF-8 UTF-8.*)$/\2/m"
sed -i.old /etc/locale.gen -re "s/^(\s*#\s*)(en_US.UTF-8 UTF-8.*)$/\2/m"
sed -i.old /etc/locale.gen -re "s/^(\s*#\s*)(fr_FR.UTF-8 UTF-8.*)$/\2/m"
/usr/sbin/locale-gen

program=wlanthermo

echo "Enable the serial connection"
echo "----------------------------------------------------------"
SERIAL=$(grep "^enable_uart=1" /boot/config.txt | wc -l)

if [ $SERIAL == 0 ]; then
  echo "enable_uart=1" >> /boot/config.txt
  echo "Serial Port is now enabled, please reboot!"
else
    echo "Serial Port was already enabled."
fi
  

echo "Check Ramdrive and create it if it doesn't exist"
echo "----------------------------------------------------------"
RD=$(cat /etc/fstab|grep /var/www/tmp|grep -v grep|wc -l)

if  [ $RD == 0 ]; then
  mkdir /var/www/tmp -p
  if [ "$IMAGE_MODE" == "FALSE" ]; then
    mount -t tmpfs -o size=16M,mode=770,uid=www-data,gid=www-data tmpfs /var/www/tmp
  fi
  echo "tmpfs           /var/www/tmp    tmpfs   size=16M,mode=770,uid=www-data,gid=www-data     0       0" >> /etc/fstab
  echo -e "[\033[42m\033[30m OK \033[0m] RAM Drive created!"
fi
if  [ $RD != 0 ]; then
  echo -e "[\033[42m\033[30m OK \033[0m] RAM Drive already exists"
fi

echo "Updating System:"
echo "----------------------------------------------------------"
apt-get update
apt-get upgrade -y
apt-get -y install raspberrypi-sys-mods

echo "Install depencies:"
echo "----------------------------------------------------------"
aptitude --safe-resolver -y install build-essential sudo vim htop iftop iotop gnuplot-nox lighttpd apache2-utils php5-cgi php5-gd php5-intl php5-curl fswebcam imagemagick pigpio python python-dev python-serial python-psutil python-pyinotify python-urllib3 python3 python3-dev python3-serial ntpstat python-pip python3-pip
aptitude --safe-resolver -y remove python-pigpio python3-pigpio

echo "Install additional Python packages"
echo "----------------------------------------------------------"
pip install bitstring

echo "Updating pigpiod"
echo "----------------------------------------------------------"
rm -f /tmp/pigpio.tar
rm -rf /tmp/PIGPIO
pushd /tmp
wget abyz.co.uk/rpi/pigpio/pigpio.tar
tar xf pigpio.tar
cd PIGPIO

echo "Removing old pigpiod:"
echo "----------------------------------------------------------"
make uninstall
make prefix=/usr uninstall

echo "Installing new pigpiod, this may take some time!"
echo "----------------------------------------------------------"
make -j4
make prefix=/usr install
popd

echo "Extract the package"
echo "----------------------------------------------------------"
tail -n +$startline $0 > /tmp/${program}.deb
sleep 2
echo "Install /tmp/${program}.deb"
dpkg -i /tmp/${program}.deb

url=$(cat /etc/hostname)
echo " "
echo "===================================================================================================="
echo "========*********************************************************************************==========="
echo "========***********    WLANThermo installed completely! Please reboot now!    ***********==========="
echo "========***********         Open http://$url in a browser afterwards!         ***********==========="
echo "========*********************************************************************************==========="
echo "===================================================================================================="
echo " "

exit 0
# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----
