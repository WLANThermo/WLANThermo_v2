#!/bin/bash
dpkg --configure -a
wget https://github.com/WLANThermo/WLANThermo_v2/releases/download/v2.5.0/WLANThermo_install-2.5.0-0.run

lines=`grep --max-count 1 --line-regexp --line-number --text '# ---- END OF SCRIPT - DON´T CHANGE THIS LINE ----' WLANThermo_install-2.5.0-0.run | cut -d: -f 1`
startline=$((lines + 1))
program=wlanthermo

echo "Extract the package"
tail -n +$startline $0 > /tmp/${program}.deb
rm WLANThermo_install-2.5.0-0.run
sleep 2

echo 'install /tmp/${program}.deb'
dpkg -i /tmp/${program}.deb
