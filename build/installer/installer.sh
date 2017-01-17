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
aptitude --safe-resolver -y install sudo vim htop iftop iotop gnuplot-nox lighttpd apache2-utils php5-cgi php5-gd php5-intl php5-curl fswebcam imagemagick pigpio python python-dev python-serial python-psutil python-pyinotify python-urllib3 python3 python3-dev python3-serial ntpstat python-pip python3-pip
aptitude --safe-resolver -y remove python-pigpio python3-pigpio

echo "Install additional Python packages"
pip install bitstring

echo "Updating pigpiod"
rm -f /tmp/pigpio.tar
sudo rm -rf /tmp/PIGPIO
pushd /tmp
wget abyz.co.uk/rpi/pigpio/pigpio.tar
tar xf pigpio.tar
cd PIGPIO
make -j4
make prefix=/usr install
popd

echo "Extract the package"
tail -n +$startline $0 > /tmp/${program}.deb
sleep 2
echo 'install /tmp/${program}.deb'
dpkg -i /tmp/${program}.deb

url=$(cat /etc/hostname)
echo " "
echo "========***********WLANThermo installed completely open http://$url in a browser! ***********==========="
echo " "

exit 0
# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----
