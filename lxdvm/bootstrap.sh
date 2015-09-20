#!/bin/sh

apt-get update
apt-get install --yes openssh-server dnsmasq
mkdir -p /root/.ssh
