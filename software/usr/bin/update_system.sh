#!/bin/bash
# Fix broken or aborted installations first
apt -y install --fix-broken
apt update

# Mark given packages in hold state
for package in "$@"
do
    apt-mark hold $package 
done

# Do full upgrade
apt -y dist-upgrade

# Remove given packages from hold state afterwards
for package in "$@"
do
    apt-mark unhold $package 
done

# Cleanup afterwards
apt -y autoremove
apt -y clean