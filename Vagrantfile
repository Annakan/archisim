# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.
Vagrant.configure(2) do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.

  # Every Vagrant development environment requires a box. You can search for
  # boxes at https://atlas.hashicorp.com/search.
  #config.vm.box = "ubuntu/vivid64"
   config.vm.box = "boxcutter/ubuntu1504"

  # Disable automatic box update checking. If you disable this, then
  # boxes will only be checked for updates when the user runs
  # `vagrant box outdated`. This is not recommended.
  # config.vm.box_check_update = false

  # Create a forwarded port mapping which allows access to a specific port
  # within the machine from a port on the host machine. In the example below,
  # accessing "localhost:8080" will access port 80 on the guest machine.
  # config.vm.network "forwarded_port", guest: 80, host: 8080

  # Create a private network, which allows host-only access to the machine
  # using a specific IP.
  # config.vm.network "private_network", ip: "192.168.33.10"

  # Create a public network, which generally matched to bridged network.
  # Bridged networks make the machine appear as another physical device on
  # your network.
  # config.vm.network "public_network"

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  # config.vm.synced_folder "../data", "/vagrant_data"

  # Provider-specific configuration so you can fine-tune various
  # backing providers for Vagrant. These expose provider-specific options.
  # Example for VirtualBox:
  #
  # config.vm.provider "virtualbox" do |vb|
  #   # Display the VirtualBox GUI when booting the machine
  #   vb.gui = true
  #
  #   # Customize the amount of memory on the VM:
  #   vb.memory = "1024"
  # end
  config.vm.provider "virtualbox" do |vb|
    # Display the VirtualBox GUI when booting the machine
    #vb.gui = true

    # Customize the amount of memory on the VM:
    vb.memory = "2048"
    vb.cpus = 2
  end
  config.vm.provider "vmware_workstation" do |vmw|
    # Display the VirtualBox GUI when booting the machine
    #vmw.gui = true

    # Customize the amount of memory on the VM:
    vmw.memory = "2048"
    vmw.cpus = 2
  end
  #
  # View the documentation for the provider you are using for more
  # information on available options.

  # Define a Vagrant Push strategy for pushing to Atlas. Other push strategies
  # such as FTP and Heroku are also available. See the documentation at
  # https://docs.vagrantup.com/v2/push/atlas.html for more information.
  # config.push.define "atlas" do |push|
  #   push.app = "YOUR_ATLAS_USERNAME/YOUR_APPLICATION_NAME"
  # end


  # Enable provisioning with a shell script. Additional provisioners such as
  # Puppet, Chef, Ansible, Salt, and Docker are also available. Please see the
  # documentation for more information about their specific syntax and use.
  # config.vm.provision "shell", inline: <<-SHELL
  #   sudo apt-get update
  #   sudo apt-get install -y apache2
  # SHELL

  #  suppress not a stdin messages
  config.vm.provision "shell", inline: <<-SHELL
    # fix stdin: is not a tty
    sed -i 's/^mesg n$/tty -s \\&\\& mesg n/g' /root/.profile
    sed -i 's/^mesg n$/tty -s \\&\\& mesg n/g' /home/vagrant/.profile
    export DEBIAN_FRONTEND=noninteractive
  SHELL
  # Ensure that VMWare Tools recompiles kernel modules
  # when we update the linux images

  #auto update des vmwaretools  cf https://docs.vagrantup.com/v2/vmware/kernel-upgrade.html
  # Ensure that VMWare Tools recompiles kernel modules when we update the linux images
  $fix_vmware_tools_script = <<-SCRIPT
  com1="sed -i 's/answer AUTO_KMODS_ENABLED_ANSWER no/answer AUTO_KMODS_ENABLED_ANSWER yes/g' /etc/vmware-tools/locations ; true"
  com2="sed -i 's/answer AUTO_KMODS_ENABLED no/answer AUTO_KMODS_ENABLED yes/g' /etc/vmware-tools/locations ; true"
  su -c "$com1"
  su -c "$com2"
  SCRIPT
  config.vm.provision :shell, :inline =>  $fix_vmware_tools_script; 

  # Configuration of LXD

  config.vm.provision "shell", inline: <<-SHELL
    # fix stdin: is not a tty
    sed -i 's/^mesg n$/tty -s \\&\\& mesg n/g' /root/.profile
    sed -i 's/^mesg n$/tty -s \\&\\& mesg n/g' /home/vagrant/.profile
    export DEBIAN_FRONTEND=noninteractive
    timedatectl set-timezone Europe/Paris
    apt-get update
    apt-get upgrade -y
    apt-get install language-pack-fr
    apt-get install flip
    apt-get -y install software-properties-common
    apt-get -y install python-dev python-software-properties libyaml-dev unzip curl dnsutils
    add-apt-repository -y ppa:ubuntu-lxc/lxd-stable
    apt-get update
    apt-get install -y lxd
    service lxd start
    wget https://bootstrap.pypa.io/get-pip.py
    python get-pip.py --force-reinstall  --install-option="--install-scripts=/usr/bin"

    pip install virtualenv
    pip install sh
    pip install jinja2
    pip install pyaml
    pip install argparse
    pip install dnspython

    adduser vagrant lxd
    echo "root:1000000:65536" | sudo tee -a /etc/subuid /etc/subgid
    #
    # Chef is just boring
    sudo apt-get remove --purge -y chef

    # Just like puppet
    sudo apt-get remove --purge -y puppet

    sudo apt-get autoremove -y

    #make sure whatever the git checkout the file is in unix endings
    su -c 'cd /vagrant/lxdvm && flip -u *' vagrant

    su -c 'ssh-keygen -t ecdsa -N "" -f /home/vagrant/.ssh/id_ecdsa' vagrant
    sleep 10

    su -c 'lxc remote add images images.linuxcontainers.org' vagrant
    lxc profile create twoNets
    lxc profile device add twoNets eth0 nic parent=lxcbr0 nictype=bridged
    lxc profile device add twoNets eth1 nic parent=lxcbr0 nictype=bridged

    # Allowing name based ip configuration for LXC container
    # http://askubuntu.com/questions/446831/how-to-let-built-in-dhcp-assign-a-static-ip-to-lxc-container-based-on-name-not
    com3="sed -i 's/#LXC_DHCP_CONFILE=/LXC_DHCP_CONFILE=/'  /etc/default/lxc-net"
    su -c "$com3"
    sudo touch /etc/lxc/dnsmasq.conf
    sudo systemctl restart lxc-net

    #Fake private network
    route add -net 192.168.99.0 netmask 255.255.255.0 lxcbr0

    #sysdig
    curl -s https://s3.amazonaws.com/download.draios.com/DRAIOS-GPG-KEY.public | sudo apt-key add -
    curl -s -o /etc/apt/sources.list.d/draios.list http://download.draios.com/stable/deb/draios.list
    sudo apt-get update
    sudo apt-get -y install sysdig

  SHELL
end
