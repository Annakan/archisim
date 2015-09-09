#!/usr/bin/env python
 # -*- coding: utf-8 -*-

import sys
from jinja2 import Environment, FileSystemLoader
from sh import lxc, sudo, ssh_keygen
import time
import os.path

import argparse


TEMPLATE_DIR = ""
UID = GUID = 10000
PRIVATE_NETWORK = "192.168.0.0"

parser = argparse.ArgumentParser(description='Create LXD VM and register them dynamically')
parser.add_argument("vm_names", help="name of  VMs to create (hostname)", type=basestring, nargs='+' )
os_group = parser.add_argument_group("OS params", "parameters for OS type, versions and architecture")
os_group.add_argument("--os", help="OS version", type=basestring, default='centos')
os_group.add_argument("--release", help="OS release", type=basestring, default='7')
os_group.add_argument("--arch", help="OS architecture", type=basestring, default='amd64')

salt_group = parser.add_argument_group("salt params", "parameters for salt configuration of VMs")
salt_group.add_argument("--salty", help="Make it a salt minion for the given master", type=basestring)
salt_group.add_argument("--sal_id", help="salt id, if not present the machine hostname is used", type=basestring)
salt_group.add_argument("--grain", help="register the given grain for that minion (require --salty)", type=basestring,
                        action='append')

parser.add_argument("--template", help="use the given file template to get options, "
                                       "command line arguments will override template values", type=basestring,
                    action='append')


def list_vm():
    blob = lxc.list().split('\n')[3:-2]
    blob = [[a.strip() for a in line.split('|')[1:-1]]
            for line in blob]
    blob = dict([(c[0], tuple(c[1:])) for c in blob])
    return blob

vms = list_vm()


def remove_grains(vm):
    # check salt
    # get true id
    # remove grains
    pass


def register_in_salt_master():
    pass


def make_salt_master():
    pass


for vm in sys.argv[1:]:
    if vm in vms:
        remove_grains(vm)
        lxc.delete(vm)

    if os.path.exists('home/vagrant/.ssh/known_hosts'):
        ssh_keygen('-f', "/home/vagrant/.ssh/known_hosts", '-R', vm)
    lxc.launch('images:debian/wheezy/amd64', vm, '-p', 'twoNets')

time.sleep(10)
print list_vm()

env = Environment(loader=FileSystemLoader('.'))

names = []

for vm, info in list_vm().items():
    print info
    id = info[1].split('.')[-1]
    tpl = env.get_template('interfaces.j2')
    tpl.stream(id=id).dump(open('interfaces.tmp', 'w'))
    lxc.file.push('--uid=100000', '--gid=100000', 'interfaces.tmp',
                  '%s/etc/network/interfaces' % vm)
    lxc('exec', vm, 'ifup', 'eth1')
    lxc.file.push('bootstrap.sh', '%s/tmp/bootstrap.sh' % vm)
    lxc('exec', vm, '/bin/sh', '/tmp/bootstrap.sh')
    names.append(dict(ip=info[1], names=["%s.public.lan" % vm, vm]))
    names.append(dict(ip="192.168.99.%s" % id,
                      names=["%s.private.lan" % vm]))
    lxc.file.push('--uid=100000', '--gid=100000', '/home/vagrant/.ssh/id_ecdsa.pub',
                  '%s/root/.ssh/authorized_keys' % vm)

tpl = env.get_template('hosts.j2')
tpl.stream(names=names).dump(open('hosts.tmp', 'w'))
sudo.mv('hosts.tmp', '/etc/hosts')

print list_vm()
