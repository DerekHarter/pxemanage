"""pxemanage module

bootconfig submodule

Contents
--------

Functions relating to the managing the pxeboot boot configuration
(bootconfig) files.  The pxeboot starts the boot process by loading a
file in the 'tftpboot/pxelinux.cfg/' directory.  It can look up this
file in several ways.  We use the hardware mac address, so there are
files named '01-11-22-33-44-55-66' where the last 6 digits are the mac
address of the host NIC card that has been served dhcpd and is
performint a netboot.  This module maintains and creates these files
for the hosts under management in the cluster.

"""
import subprocess
import pxemanage as pm


def create_bootconfig_file(hostname):
    """A new host has been registered for this cluster.  Create the
    host pxelinux boot configuration file using the information 
    gathered for this host.

    Parameters
    ----------
    hostname - The new host name to create a boot configuration file for.
    """
    # lookup host in registration database
    host = pm.hosts[hostname]
    bootconfig_file = f"{pm.settings['pxelinux_config_dir']}/{host.macaddress_file()}"
    
    print("======== Create pxeboot configuration file ========")
    print(f"    ----- creating boot configuration for mac: {host.macaddress}")
    print(f"    -----                            hostname: {host.hostname}")
    print(f"    -----                            filename: {bootconfig_file}")
    print("")

    # get template and render
    template = pm.j2.get_template("pxeboot.cfg.j2")
    content = template.render(hostname = hostname,
                              apache_server_ip = pm.settings['apache_server_ip'],
                              iso_image_name = pm.settings['iso_image_name'])
    file = open(bootconfig_file, mode="w")
    file.write(content)
    file.close()
    
    # make a symbolic link to this file but using the host name, which
    # makes it much easier for humans to find the bootconfig
    bootconfig_link = f"{pm.settings['pxelinux_config_dir']}/{host.hostname}"
    command = f"ln -rs {bootconfig_file} {bootconfig_link}"
    subprocess.run(command, shell=True)


def set_host_local_boot(hostname):
    """Configure the given pm.hosts pxeboot config file to default to
    a local disk boot on its next network boot.

    Parameters
    ----------
    hostname - The name of the configured host whose bootconfig file
      should be modified to perform a local disk boot on the next
      reboot.
    """
    # lookup host in registration database
    host = pm.hosts[hostname]

    print(f"    -------- setting host {host.hostname} to perform local boot on reboot")
    print("")
    
    # determine boot configuration file name
    bootconfig_file = f"{pm.settings['pxelinux_config_dir']}/{host.macaddress_file()}"

    # we will use a simple bash sed replace line infile, switching
    # to sudo authority for the command
    command = f"sed -i 's/ONTIMEOUT.*/ONTIMEOUT local/g' {bootconfig_file}"
    subprocess.run(command, shell=True)


def set_host_install_boot(hostname):
    """Configure the given pm.hosts pxeboot config file to default to
    a autoinstall disk boot on its next network boot.

    Parameters
    ----------
    hostname - The name of the configured host whose bootconfig file
      should be modified to perform a reinstall autoinstall  boot on the next
      reboot.
    """
    # lookup host in registration database
    host = pm.hosts[hostname]

    print(f"    -------- setting host {host.hostname} to perform reinstall auto installation on reboot")
    
    # determine boot configuration file name
    bootconfig_file = f"{pm.settings['pxelinux_config_dir']}/{host.macaddress_file()}"

    # we will use a simple bash sed replace line infile, switching
    # to sudo authority for the command
    command = f"sed -i 's/ONTIMEOUT.*/ONTIMEOUT install/g' {bootconfig_file}"
    subprocess.run(command, shell=True)
