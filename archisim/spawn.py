#!/usr/bin/env python

import sys
from jinja2 import Environment, FileSystemLoader
from sh import lxc, sudo
import time


def list_vm():
    blob = lxc.list().split('\n')[3:-2]
    blob = [[a.strip() for a in line.split('|')[1:-1]]
            for line in blob]
    blob = dict([(c[0], tuple(c[1:])) for c in blob])
    return blob

vms = list_vm()

for vm in sys.argv[1:]:
    if vm in vms:
        lxc.delete(vm)
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
    lxc.file.push('--uid=1', '--gid=1', 'interfaces.tmp',
                  '%s/etc/network/interfaces' % vm)
    lxc('exec', vm, 'ifup', 'eth1')
    lxc.file.push('bootstrap.sh', '%s/tmp/bootstrap.sh' % vm)
    lxc('exec', vm, '/bin/sh', '/tmp/bootstrap.sh')
    names.append(dict(ip=info[1], names=["%s.public.lan" % vm]))
    names.append(dict(ip="192.168.99.%s" % id,
                      names=[vm, "%s.private.lan" % vm]))

tpl = env.get_template('hosts.j2')
tpl.stream(names=names).dump(open('hosts.tmp', 'w'))
sudo.mv('hosts.tmp', '/etc/hosts')

print list_vm()
