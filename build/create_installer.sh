#!/bin/bash

cd "${BASH_SOURCE%/*}" || exit

echo Kopiere Software in das Buildverzeichniss...
cp -r ../software/* ./build/
echo Kopiere Paketdaten in das Buildverzeichniss...
cp -r ../DEBIAN ./build/
echo Kopiere Changelog in das Buildverzeichniss...
cp -r ../changelog ./build/DEBIAN/changelog

echo Suche Versionsnummer...
PKG_VERSION=`dpkg-parsechangelog -lbuild/DEBIAN/changelog --show-field Version`
echo Paketversion: $PKG_VERSION
echo Setze Version in den Paketdaten...
echo Version: $PKG_VERSION >> ./build/DEBIAN/control

[[ $PKG_VERSION =~ ^(.*)(-[[:digit:]]+)$ ]]
VERSION=${BASH_REMATCH[1]}
echo Setze Version in der header.php...
sed -i -e "s/XXX_VERSION_XXX/V${VERSION}/g" ./build/var/www/header.php

# PEP 440 kennt kein "~": 2.8.3~beta1 -> 2.8.3beta1 (pip normalisiert zu 2.8.3b1)
PY_VERSION=${VERSION//\~/}
echo Baue Python-Paket $PY_VERSION...
rm -rf ./pysrc
mkdir ./pysrc
cp -r ../pyproject.toml ../README.md ../src ./pysrc/
sed -i -e "s/^__version__ = .*/__version__ = '${PY_VERSION}'/" \
       -e "s/XXX_VERSION_XXX/V${VERSION}/g" ./pysrc/src/wlanthermo/__init__.py
mkdir -p ./build/usr/share/WLANThermo/python
python3 -m pip wheel --no-deps --wheel-dir ./build/usr/share/WLANThermo/python ./pysrc || exit 1
rm -rf ./pysrc

PKG_FILE=./package/wlanthermo-$PKG_VERSION.deb
INSTALLER=./run/WLANThermo_install-$PKG_VERSION.run
echo Baue Paket...
dpkg -b ./build $PKG_FILE

echo Baue Installer...
cat ./installer/installer.sh $PKG_FILE > $INSTALLER
chmod +x $INSTALLER

echo Lösche Buildverzeichniss...
rm -r ./build/*
