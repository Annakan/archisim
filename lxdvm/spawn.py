#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from jinja2 import Environment, FileSystemLoader
from sh import lxc, sudo, ssh_keygen
from sh import Command
import time
import os.path

import argparse

from collections import namedtuple

WAIT_NETWORK_STATE = 10

ConInfo = namedtuple('ConInfo', ['name', 'state', 'IPV4s', 'IPV6s', 'ephemeral', 'snapshots', 'mainIPV4', 'mainIPV6'])

TEMPLATE_DIR = ""
UID = GUID = 10000
PRIVATE_NETWORK = "192.168.0.0"

LOCALDIRNAME, SCRIPTNAME = os.path.split(os.path.abspath(sys.argv[0]))

# dl_consul = Command(os.path.join(LOCALDIRNAME, 'dl_consul.sh'))

def make_arg_parser():

    parser = argparse.ArgumentParser(description='Create LXD VM and register them dynamically')
    parser.add_argument("vm_names", help="name of  VMs to create (hostname)", nargs='+')  # Done
    parser.add_argument("--private_network", help="IP address of the private network", default=PRIVATE_NETWORK)

    old_container_group = parser.add_mutually_exclusive_group()
    old_container_group.add_argument('--rebuild_all', dest='rebuild_all', action='store_true', default=True,
                                     help="rebuild previous existing containers too")  # Done
    old_container_group.add_argument('--keep_existing', dest='rebuild_all', action='store_false',
                                     help="don't touch existing container not named in this command run")

    consul_group = parser.add_mutually_exclusive_group()
    consul_group.add_argument('--install_consul', help="install Consul client", action='store_true', default=False)
    # @todo see if it is possible to automatically get the previous consul servers and join them (local db file)
    consul_group.add_argument('--install_consul_server', nargs='+',
                              help="install Consul as server with the node addresses supplied")

    os_group = parser.add_argument_group("OS params", "parameters for OS type, versions and architecture")
    os_group.add_argument("--os", help="OS version", default='centos')  # Done
    os_group.add_argument("--release", help="OS release", default='7')  # Done
    os_group.add_argument("--arch", help="OS architecture",  default='amd64')  # Done

    salt_group = parser.add_argument_group("salt params", "parameters for salt configuration of VMs")
    salt_group.add_argument("--salty", help="Make it a salt minion for the given master")
    salt_group.add_argument("--sal_id", help="salt id, if not present the machine hostname is used")
    salt_group.add_argument("--grain", help="Set the given grains for the minion(s) (require --salty)", action='append')

    parser.add_argument("--template", help="Use the given file template to get options, "
                                           "command line arguments will override template values",  action='append')

    return parser


def list_vm():
    """
    :return: a list of ConInfo (info on container) namedtuple representing the container known by the lxd daemon on the
    system.
    """
    blob = lxc.list().split('\n')[3:-2]
    blob = [[a.strip() for a in line.split('|')[1:-1]]
            for line in blob]
    result = dict([(c[0], ConInfo(*(tuple(c)+(c[2].split(',')[0], c[3].split(',')[0])))) for c in blob])
    return result


def remove_grains(vm):
    # check salt
    # get true id
    # remove grains
    pass


def register_in_salt_master():
    pass


def make_salt_master():
    pass


def wait_for_vms(vmnames, maxwait=30*1000):
    """
    Wait for one or more containers to be ready (Running state)
    :param vmnames: name of the container or list of name of containers to wait for their running state
    :param maxwait: Maximum time to wait for the containers to be running, default 30 seconds
    :return: True : containers have been started before the end of :maxwait, False : some containers have not
    started before the end of :maxwait
    """
    start = time.time()
    if vmnames is basestring:
        vmnames = list(vmnames)
    # it is the same to wait for one VM after one VM or all at once since the slowest to start will block us
    for vmname in vmnames:
        vmlist = list_vm()
        while vmname not in vmlist.keys() or not vmlist[vmname].state == "RUNNING" or len(vmlist[vmname].mainIPV4) == 0:
            print '.',
            vmlist = list_vm()
            time.sleep(1)
            if time.time()-start > maxwait:
                print '/'
                return False
    print '+'
    return True


def decribe_os (os, release, arch):
    arch = 'amd64' if args.arch in ['amd64', 'x64'] else 'i386'
    os = os.lower()
    if os in ('redhat', 'centos', 'fedora', 'rh'):
        os_kind = 'rh'
    else:
        if os in ('debian', 'ubuntu', 'mint'):
            os_kind = 'debian'
        else:
            if os in ('gentoo', 'arch'):
                os_kind = 'arch'
            else:
                os_kind = None
    if os_kind == 'rh':
        init_system = 'systemd' if release > 6 else 'initd'
    else:
        if os_kind =='debian':
            init_system = 'systemd' if release > 7 else 'init'
        else:
            init_system = None

    return os_kind, arch, init_system

if __name__ == "__main__":

    args = make_arg_parser().parse_args()
    (os_kind, arch, init_sytem) = decribe_os(args.os, args.release, args.arch)
    install_consul = args.install_consul or args.install_consul_server

    vms = list_vm()

    for vm in args.vm_names:
        #  If the container mentionned in args already exist we destroy it first and later rebuild it in full
        if vm in vms:
            print "cleaning [{}]".format(vm)
            remove_grains(vm)
            lxc.delete(vm)
        print "Instantiating core [{}]".format(vm)
        if os.path.exists('home/vagrant/.ssh/known_hosts'):
            ssh_keygen('-f', "/home/vagrant/.ssh/known_hosts", '-R', vm)
        image_uri = "images:{os}/{release}/{arch}".format(**vars(args))
        lxc.launch(image_uri, vm, '-p', 'twoNets')
        print "Done for core  [{}]".format(vm)

    print "waiting for network state stabilization for {} seconds".format(WAIT_NETWORK_STATE)
    wait_for_vms(list_vm().keys(), WAIT_NETWORK_STATE)

    time.sleep(WAIT_NETWORK_STATE)
    print "--"*100
    print list_vm()
    print "--"*100

    jj_env = Environment(loader=FileSystemLoader('.'))

    names = []

    for vm, info in list_vm().items():
        if not args.rebuild_all and vm not in args.vm_names:
            print "skipping configuration of Container [{}] because rebuild_all=False".format(vm)
        else:
            print "Configuring VM [{}] ({})".format(vm, info)
            # 'id' is the final part of the assignated IP, we will build the private network IP based on it
            # At that point of the (re-)creation process the containers have only one IP, the brdiged assigned one.
            id = info.mainIPV4.split('.')[-1]  # Should we use the 6 last digits to widen our range of adresses?
            print "id [{}]".format(id)
            print  "preparing the VM network interfaces"
            tpl = jj_env.get_template('interfaces.j2')
            tpl.stream(id=id).dump(open('interfaces.tmp', 'w'))
            lxc.file.push('--uid=100000', '--gid=100000', 'interfaces.tmp', '%s/etc/network/interfaces' % vm)
            print "Starting the newly added private interface"
            lxc('exec', vm, 'ifup', 'eth1')
            #  bootstrap.sh contains code executed once for initializations. By default install the openSSH package.
            print "bootstrap"
            lxc.file.push('bootstrap.sh', '%s/tmp/bootstrap.sh' % vm)
            lxc('exec', vm, '/bin/sh', '/tmp/bootstrap.sh')
            #  and we push a default ssh key on the root of the VM
            print "ssh auth installation"
            lxc.file.push('--uid=100000', '--gid=100000', '/home/vagrant/.ssh/id_ecdsa.pub',
                          '%s/root/.ssh/authorized_keys' % vm)
            # installing consul
            if install_consul:
                print "installing consul"
                # check consul is downloaded
                consul_bin = 'consul64' if arch =='amd64' else 'consul32'
                consul_bin_path = os.path.join(LOCALDIRNAME, '..', 'consul', consul_bin)
                lxc.file.push(consul_bin_path, '%s/root/consul' % vm)

        #  Now we prepare the rewrite of the /etc/hosts file on the host to know the VMs.
        names.append(dict(ip=info.mainIPV4, names=["%s.public.lan" % vm, vm]))
        names.append(dict(ip="192.168.99.%s" % id, names=["%s.private.lan" % vm]))

    # rewritting the /etc/hosts file on the HOST (where the lxd daemon sits)
    # @TODO update hostfile and not full rewrite, we can share ;)
    tpl = jj_env.get_template('hosts.j2')
    tpl.stream(names=names).dump(open('hosts.tmp', 'w'))
    sudo.mv('hosts.tmp', '/etc/hosts')

    print "*"*100
    print "{}, Done".format(SCRIPTNAME)
    print "*"*100