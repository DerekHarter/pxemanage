"""
pxemanage module

reinstall submodule

Contents
--------

Functions used for forced reboot and autoinstall of
hosts being managed.
"""
import re
import subprocess
import pxemanage as pm


def configure_hosts_for_reinstall(hostnames):
    """Given a list of host names, configure all of the managed hosts
    to perform a autoinstall reinstall on reboot.

    We check and only set hosts that are being managed to reinstall.
    Other hosts are just ignored with a warning.

    Parameters
    ----------
    hostnames - a list of hostname strings to be configured.

    Returns
    -------
    valid_hostnames - a list of hosts that were found to be in the 
       hosts database of managed systems is returned.

    Also all valid hosts under management will have their bootconfig file
    set to perform an install after this function finishes.

    """
    print("======== Configure Hosts to auto (re)install on next boot ========")
    valid_hostnames = []
    for hostname in hostnames:

        # check that the hostname is under cluster management
        if hostname not in pm.hosts:
            print(f"    -------- Warning: host {hostname} was not found in the current set")
            print("    -------- of managed hosts, it will be ignored for the rest of this script")
            print("")
        else:
            # host is under management, configure it for a reinstall on boot
            valid_hostnames.append(hostname)
            pm.set_host_install_boot(hostname)
    print("")
    
    # return list of valid hosts that are managed and we can proceed with
    return valid_hostnames


def reboot_hosts(hostnames):
    """Given a list of host names, attempt to perform ssh reboot of each host.
    We assume the list of hosts has already been validated before being
    passed into this function.

    We attempt to ssh in and perform reboot command using the configured
    username.  If we fail, we display warning but continue with the 
    machine, assuming that the operator will be performing a hand
    reboot or start of the machine.

    Parameters
    ----------
    hostnames - A list of hosts to be rebooted.  The list should all be hosts
      that are currently being managed, e.g. we expect this list to be
      validated before calling this function.

    """
    print("======== Reboot host to perform autoinstall  ========")

    for hostname in hostnames:
        host = pm.hosts[hostname]

        # attempt ssh reboot of the host, send it a reboot command
        # not using password here currently, so this assumes ssh key access is working
        key = pm.settings['identity']
        args = pm.settings['ssh_args']
        username = pm.settings['username']
        password = pm.settings['password']

        # we first detect if machine has working ssh communication with
        # the identity we are using
        command = f"ssh -i {key} {args} {username}@{host.ipaddress} 'sudo hostname'"
        try:
            output = subprocess.run(command, shell=True, check=True, capture_output=True)
            connected = True
        except subprocess.CalledProcessError as e:
            connected = False
            
        # if we were able to successfully connect, attempt the actual reboot
        # it is normal for this command to fail with a 255 returncode because we
        # will loose the connection
        if connected:
            command = f"ssh -i {key} {args} {username}@{host.ipaddress} 'sudo reboot'"
            rebooted = False
            try:
                print(f"    -------- running command <{command}>")
                output = subprocess.run(command, shell=True, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                # it is normal to get return error code 255 on reboot because the
                # ssh connection gets interrupted
                if e.returncode == 255:
                    rebooted = True

        # report what happened
        if rebooted:
            print(f"    -------- Successfully rebooted {hostname}")
            host.status = pm.status.REBOOTING
        else:
            if not connected:
                print(f"    -------- Error, could not connect to {hostname}, is identity correct?")
            print(f"    -------- Warning: host {hostname} could not be successfully rebooted")
            print("    -------- you will need to restart or reboot by hand to proceed with install")
            
    print("")


def monitor_host_reinstalls():
    """Begin monitoring system events (syslog) for tftp request
    events of initrd files.  These indicate that a pxeboot
    auto(re)install is beginning on a machine.  When we detect
    reinstall has begun, we need to set the default action back
    to a local hard drive boot, so that after machine finishes
    reinstallation and it automatically reboots, it will reboot
    into its newly installed hard drive configuration.
    """
    print("======== Monotor Syslog for Host Reinstallation Progress ========")
    systemevent = pm.follow_system_events_file()
    
    # iterate over the lines
    print("    -------- async monitor system events starting")
    print("")
    print("    use ctrl-c to end host reinstallations monitoring")
    print("")
    while not all_hosts_installed():
        # get next system event
        line = next(systemevent)

        # determine if registerd host install has begun
        ip_pattern = "\d+\.\d+\.\d+\.\d+"
        pattern = re.compile(f"^.*RRQ\s+from\s+({ip_pattern})\s+filename\s+initrd.*$")
        match = pattern.match(line)

        # if an initrd file was requested, the host is doing an autoinstall
        if match:
            ipaddress = match.group(1)
            print("")
            #print(f"    detected autoinstall in progress from ipaddress: <{ipaddress}>")
            pm.install_host(ipaddress)
        
    print("    -------- finished host reinstallations, all hosts appear to have started reinstall")
    print("    -------- You may stop the services we use for management once all files have downloaded to the hosts")
    print("")
    # TODO: whoops a timing bug/issue here.  When we detect last host has started
    # install, it still may be some time before it has finished getting files from
    # tftp, and especially from http.  For now we leave services running.
    #pm.stop_services()


def all_hosts_installed():
    """Look through all of our currently registered hosts and see if any of them
    are still in REBOOTING status.  If a host was set to be rebooting, but we never
    say it begin installing to set its status to INSTALLING then we are not done
    monitoring yet.  We want to keep monitoring untill all hosts get past their
    rebooting stage.
    """
    # search and if we find a host still rebooting, answer is False, need
    # to keep monitoring
    for hostname in pm.hosts:
        host = pm.hosts[hostname]
        if host.status == pm.status.REBOOTING:
            return False

    # didn't find any hosts still rebooting, so it is true that all hosts are installed
    # as far as we can tell
    return True
