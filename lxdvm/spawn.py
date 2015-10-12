#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import jinja2
from sh import lxc, sudo, ssh_keygen, dig
# import dns.resolver
import socket
import time
import os.path as path
from os.path import join
from os import remove as remove_file
from copy import copy
import shutil
import subprocess
from argparse import Namespace, ArgumentParser
from tempfile import NamedTemporaryFile
from collections import namedtuple

LXC_DNSMASQ_CONF = '/etc/lxc/dnsmasq.conf'

ConInfo = namedtuple('ConInfo', ['name', 'state', 'IPV4s', 'IPV6s', 'ephemeral', 'snapshots', 'mainIPV4', 'mainIPV6'])
DistInfo = namedtuple('DistInfo', ['os_kind', 'arch', 'init_system'])

LOCALDIRNAME, SCRIPTNAME = path.split(path.abspath(sys.argv[0]))

CON_TEMPLATE_DIR = ""
UID = GUID = 10000
PRIVATE_NETWORK = "192.168.0."

CNR_CONSUL_PATH = '/opt/consul/'
CNR_CONSUL_BINARY = join(CNR_CONSUL_PATH, 'bin/consul')

WAIT_NETWORK_STATE = 10

# dl_consul = Command(os.path.join(LOCALDIRNAME, 'dl_consul.sh'))

jj_env = jinja2.Environment(loader=jinja2.FileSystemLoader('./templates'))


class StaticIPGen:
    def __init__(self, base_ip, reservation=10, containers=None):
        self.base_ip = base_ip
        self.reservation = reservation
        self.con_ips = {}
        self.con_names = {}
        self.ip_rank = 0
        if containers:
            self.regenerate_ips(containers)

    def get_next_ip(self, name):
        self.ip_rank += 1
        new_ip = self.base_ip + str(self.ip_rank)
        self.con_ips[name] = new_ip
        self.con_names[new_ip] = name
        return new_ip

    def ip_list(self):
        return copy(self.con_ips)

    def regenerate_ips(self, cont_list):
        for con in cont_list.itervalues():
            assert isinstance(con, ConInfo)
            con_ip = con.mainIPV4
            if con_ip.split('.')[-1] < self.reservation:
                self.con_ips[con.name] = con_ip
                self.con_names[con_ip] = con.name


def make_arg_parser():
    parser = ArgumentParser(description='Create LXD VM and register them dynamically')
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
    consul_group.add_argument('--install_consul_server', type=int,
                              help="install Consul as server with given number of server total expected ")
    parser.add_argument('--join_nodes', help="list of nodes to join as a server or client",
                        nargs='*', default=None)

    os_group = parser.add_argument_group("OS params", "parameters for OS type, versions and architecture")
    os_group.add_argument("--os", help="OS version", default='centos')  # Done
    os_group.add_argument("--release", help="OS release", default='7')  # Done
    os_group.add_argument("--arch", help="OS architecture", default='amd64')  # Done

    salt_group = parser.add_argument_group("salt params", "parameters for salt configuration of VMs")
    salt_group.add_argument("--salty", help="Make it a salt minion for the given master")
    salt_group.add_argument("--sal_id", help="salt con_id, if not present the machine hostname is used")
    salt_group.add_argument("--grain", help="Set the given grains for the minion(s) (require --salty)", action='append')

    parser.add_argument("--template", help="Use the given file template to get options, "
                                           "command line arguments will override template values", action='append')

    return parser


def list_vm(con_filter=''):
    """
    :return: a list of ConInfo (info on container) namedtuple representing the container known by the lxd daemon on the
    system.
    """
    blob = lxc.list(con_filter).split('\n')[3:-2]
    blob = [[a.strip() for a in line.split('|')[1:-1]]
            for line in blob]
    result = dict([(c[0], ConInfo(*(tuple(c) + (c[2].split(',')[0], c[3].split(',')[0])))) for c in blob])
    return result


def remove_grains(vm):
    # check salt
    # get true secondary_ip
    # remove grains
    pass


def register_in_salt_master():
    pass


def make_salt_master():
    pass


def wait_for_vms(vmnames, maxwait=30 * 1000):
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
            if time.time() - start > maxwait:
                print '/'
                return False
    print '+'
    return True


def update_dhcpd_fixed_ip(names_and_IPs):
    with NamedTemporaryFile(mode='w', delete=False) as tempfile:
        tpl = jj_env.get_template('fixed_ip_by_name.j2')
        tpl.stream(containers=names_and_IPs).dump(tempfile)
        tempfile.flush()
        tempfile.close()
        try:
            if path.exists(LXC_DNSMASQ_CONF + '.old'):
                subprocess.check_output(['/usr/bin/sudo', '/bin/rm', '-f', LXC_DNSMASQ_CONF+'.old'])
            mv_cmd = "/bin/mv"
            if path.exists(LXC_DNSMASQ_CONF ):
                subprocess.check_output(["/usr/bin/sudo", mv_cmd, LXC_DNSMASQ_CONF, LXC_DNSMASQ_CONF + '.old'])
            subprocess.check_output(["/usr/bin/sudo", mv_cmd, tempfile.name, LXC_DNSMASQ_CONF])
        except subprocess.CalledProcessError as err:
            print "error code", err.returncode, err.output

        # restart dhcpd / dnsmaq ?


def discover_and_setup_base_config(ipgen):
    """
    Create the base infrastructure of the containers :
    - 3 consul servers
    - a freeIPA server (or two ?)
    - a salt master (or two)
    The idea is that this is the correct structure than can then be exported (migrated) to other LXD servers.

    The infrastructure containers are "fixed" ip containers under centos7 (could be unbuntu)

    :return:  list of ConInfo(s) about the created containers
    """
    assert isinstance(ipgen, StaticIPGen)
    # container_names = ('consul1', 'consul2', 'consul3', 'saltmaster', 'FreeIPA')
    container_names = ('consul1', 'consul2')
    # let's discover what we have and don't have
    existing = dict()
    to_build = dict()
    for name in container_names:
        try:
            ip = socket.gethostbyname(name)
            existing[name] = ip
            print "Already existing {} {}".format(name, ip)
        except socket.gaierror:
            print "tobuild {}".format(name)
            to_build[name] = ipgen.get_next_ip(name)

    update_dhcpd_fixed_ip(to_build)

    for name in to_build.keys():
        print "creating {}".format(name)
        create_container(name, 'centos', '7', 'amd64', 'twoNets')
    dist_info = decribe_os('centos', '7', 'amd64')

    wait_for_vms(to_build.keys())
    vms = list_vm()
    building = dict((con_name, info) for con_name, info in vms.items() if con_name in to_build.keys())

    # now we need to configure the service containers we just created
    # base the service / role on the name
    # @TODO ...
    consul_svrs = dict((con_name, info) for con_name, info in building.items() if "consul" in con_name)
    consul_ips = set(con.mainIPV4 for con in consul_svrs.values())
    for name, cnt in consul_svrs.iteritems():
        print "consul container : " + name
        join_nodes = consul_ips - set([cnt.mainIPV4])
        toolset = Namespace(install_consul_server=True, join_nodes=join_nodes)
        setup_container(cnt, cnt, dist_info, toolset=toolset)


def render_and_push(template, data, vm, target_file_path):
    with NamedTemporaryFile(mode='w', delete=False) as tempfile:
        tpl = jj_env.get_template(template)
        tpl.stream(data).dump(tempfile)
        tempfile.flush()
        tempfile.close()
        if target_file_path[:-1] == path.sep:
            if path.splitext(template)[1] == '.j2':
                target_file_path = path.join(target_file_path, path.splitext(template)[0])
            else:
                raise ValueError(
                    "can't determine the full target filename from {} and {}".format(template, target_file_path))
        lxc.file.push(tempfile.name, "{}/{}".format(vm, target_file_path))
        lxc('exec', vm, 'sync')
        remove_file(tempfile.name)


def decribe_os(os, release, arch):
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
        if os_kind == 'debian':
            init_system = 'systemd' if release > 7 else 'init'
        else:
            init_system = None
    return DistInfo(os_kind, arch, init_system)


def setup_container(vm, con_info, dist_info, toolset):
    print "Configuring VM [{}] ({})".format(vm, con_info)
    install_consul = toolset.install_consul_server or toolset.install_consul
    # 'secondary_ip' is the final part of the assignated IP, we will build the private network IP based on it
    # At that point of the (re-)creation process the containers have only one IP, the bridged assigned one.
    con_id = con_info.mainIPV4.split('.')[-1]  # Should we use the 6 last digits to widen our range of addresses?
    secondary_ip = PRIVATE_NETWORK + ".%s" % con_id
    print "secondary_ip [{}]".format(con_id)
    print "preparing the VM network interfaces"
    render_and_push('interfaces.j2', {'con_id': con_id}, vm, '/etc/network/interfaces')
    lxc('exec', vm, 'sync')
    time.sleep(5)
    print "Starting the newly added private interface"
    lxc('exec', vm, 'ifup', 'eth1')
    #  Bootstrap.sh contains code executed once for initializations. By default install the openSSH package.
    print "bootstrap"
    lxc.file.push('bootstrap.sh', '%s/tmp/bootstrap.sh' % vm)
    lxc('exec', vm, '/bin/sh', '/tmp/bootstrap.sh')
    #  And we push a default ssh key on the root of the VM
    print "ssh auth installation"
    lxc.file.push('--uid=100000', '--gid=100000', '/home/vagrant/.ssh/id_ecdsa.pub',
                  '%s/root/.ssh/authorized_keys' % vm)
    # installing consul
    if install_consul:
        print "installing consul"
        # @todo check consul is downloaded
        consul_service_params = {
            'consul_bin_path': CNR_CONSUL_BINARY,
            'consul_conf_dir': '/opt/consul/etc/',
            'consul_service_dir': '/opt/consul/etc/consul.d/',
            'main_config_file': '/opt/consul/etc/base_consul.json',
        }
        # join_nodes = toolset.join_nodes.split()
        consul_params = {
            'node_name': vm,
            'datacenter': 'AnSSI',
            'bind': con_info.mainIPV4,  # @todo better to use the secondary network probably here
            'consul_data_dir': '/opt/consul/data',
            'retry_join': toolset.join_nodes if toolset.join_nodes else None,
        }

        if toolset.install_consul_server:
            consul_params.update(
                {
                    'server_mode': True,
                    'bootstrap_expect_value': toolset.install_consul_server,
                }
            )
        consul_bin = 'consul64' if dist_info.arch == 'amd64' else 'consul32'
        lxc('exec', vm, '--', 'mkdir', '-p', join(CNR_CONSUL_PATH, 'bin'))
        lxc('exec', vm, '--', 'mkdir', '-p', join(CNR_CONSUL_PATH, 'etc'))
        lxc('exec', vm, '--', 'mkdir', '-p', join(CNR_CONSUL_PATH, 'data'))
        lxc('exec', vm, '--', 'mkdir', '-p', consul_params['consul_data_dir'])
        lxc('exec', vm, '--', 'mkdir', '-p', consul_service_params['consul_service_dir'])
        local_consul_bin_path = path.join(LOCALDIRNAME, '..', 'consul', consul_bin)
        # lxc('exec', vm, 'sync')
        time.sleep(5)
        lxc.file.push(local_consul_bin_path, '{}/{}'.format(vm, CNR_CONSUL_BINARY))
        lxc('exec', vm, '--', '/bin/bash', '-c', '/bin/chmod +x %s' % CNR_CONSUL_BINARY)
        render_and_push('consul_params.json.j2', consul_params,
                        vm, consul_service_params['main_config_file'])
        print "starting consul"
        if dist_info.init_system == "systemd":
            render_and_push('consul.service.j2', consul_service_params, vm,
                            '/etc/systemd/system/consul.service')
            lxc('exec', vm, 'systemctl', 'start', 'consul')
        if toolset.os == "ubuntu":
            dnsmasq_config = '''echo "server=/consul/127.0.0.1#8600" > /etc/dnsmasq.d/10-consul.conf'''
            lxc('exec', vm, '--', '/bin/bash', '-c', dnsmasq_config)

        return secondary_ip


def create_container(vm_name, os, release, arch, config_name):
    if path.exists('home/vagrant/.ssh/known_hosts'):
        ssh_keygen('-f', "/home/vagrant/.ssh/known_hosts", '-R', vm_name)
    image_uri = "images:{os}/{release}/{arch}".format(**vars(args))
    lxc.launch(image_uri, vm_name, '-p', config_name)


if __name__ == "__main__":

    args = make_arg_parser().parse_args()
    distrib_info = decribe_os(args.os, args.release, args.arch)  # (os_kind, arch, init_system)

    current_vms = list_vm()
    ip_gen = StaticIPGen(PRIVATE_NETWORK, 10, current_vms)

    print "Setting up infrastructure"
    discover_and_setup_base_config(ip_gen)
    print "End Setting up infrasctucture"


    # print "OS: {} arch: {} init system: {}".format(os_kind, arch, init_system)
    #
    # for vm in args.vm_names:
    #     #  If a container mentioned in args already exist we destroy it first and later rebuild it in full
    #     if vm in current_vms:
    #         print "cleaning [{}]".format(vm)
    #         remove_grains(vm)
    #         lxc.delete(vm)
    #     print "Instantiating core [{}]".format(vm)
    #     create_container(vm, os, args.release, arch, 'twoNets')
    #     print "Done for core  [{}]".format(vm)
    #
    # print "waiting for network state stabilization for {} seconds".format(WAIT_NETWORK_STATE)
    # wait_for_vms(list_vm().keys(), WAIT_NETWORK_STATE)
    #
    # time.sleep(WAIT_NETWORK_STATE)
    # print "--" * 100
    # print list_vm()
    # print "--" * 100
    #
    # names = []
    #
    # for vm, info in list_vm().items():
    #     if not args.rebuild_all and vm not in args.vm_names:
    #         print "skipping configuration of Container [{}] because rebuild_all=False".format(vm)
    #         try:
    #             secondary_ip = info.IPV4s.split(',')[1]
    #         except IndexError:
    #             secondary_ip = None
    #     else:
    #         if info.state != 'RUNNING':
    #             print "not Configuring VM [{}] ({}) because it is stopped and not in the list".format(vm, info)
    #             try:
    #                 secondary_ip = info.IPV4s.split(',')[1]
    #             except IndexError:
    #                 secondary_ip = None
    #         else:
    #             secondary_ip = setup_container(vm, distrib_info, vars(args))
    #             # Now we prepare the rewrite of the /etc/hosts file on the host to know the VMs.
    #     names.append(dict(ip=info.mainIPV4, names=["%s.public.lan" % vm, vm]))
    #     if secondary_ip:
    #         names.append(dict(ip=secondary_ip, names=["%s.private.lan" % vm]))
    #
    # # Rewriting the /etc/hosts file on the HOST (where the lxd daemon sits)
    # # @TODO update hostfile and not full rewrite, we can share ;)
    # tpl = jj_env.get_template('hosts.j2')
    # tpl.stream(names=names).dump(open('hosts.tmp', 'w'))
    # sudo.mv('hosts.tmp', '/etc/hosts')

    print "*" * 100
    print "{}, Done".format(SCRIPTNAME)
    print "*" * 100
