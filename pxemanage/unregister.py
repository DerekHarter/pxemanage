"""
pxemanage module

unregister submodule

Contents
--------

Functions used for unregistering hosts from the
database of hosts being managed.
"""
import subprocess
import pxemanage as pm


def unregister_hosts(unregister_all, hostnames):
    """Unregister the hosts asked for from management in
    this cluster.

    If we are asked to unregister all hosts, then the hostnames
    parameter is ignored.

    We perform the following steps:

    1. determine list of hosts and check that hosts are registered
    2. give final warning of hosts to be effected before unregistering
    3. remove host pxeboot configuraiton files from files/tftp/pxeboot.cfg
    4. remove host kickstarter files from files/html/ks
    5. remove hosts from the hosts management database
    6. update the management configuration flat file (dhcpd.conf)
    """
    # 1. verify list of hosts
    if unregister_all:
        print("---- Asked to unregister all hosts, ignoring any hostnames specified on command line")
        hostnames = []
        for hostname in pm.hosts:
            hostnames.append(hostname)

    verified_hosts = []
    for hostname in hostnames:
        if not hostname in pm.hosts:
            print(f"---- Warning: host {hostname} given in list of hosts to unregister, but it is not a host currently in this cluster")
        else:
            verified_hosts.append(hostname)

    if len(verified_hosts) == 0:
        print("---- No valid hosts were specified to unregister")
        return
        
    # 2. warn and verify intent to continue
    print("---- The following are the list of hosts till will be removed from management:")
    print("")
    print("    ")
    for hostname in verified_hosts:
        print(f"{hostname} ", end='')
    print("")
    print("")
    
    yes_answers = ['y', 'Y', 'yes', 'Yes', 'YES']
    answer = input("Do you wish to unregister these hosts (y/n)? ")
    if not answer in yes_answers:
        print("aborting unregistration")
        return
    
    # 3. remove host pxeboot configuration files from pxeboot.cfg
    print("======== Deleteing host pxeboot configuration files ========")
    print("")
    for hostname in verified_hosts:
        pm.delete_bootconfig_file(hostname)
        
    # 4. remove host kickstart files from ks directory
    print("======== Deleteing host kickstarter configuration files ========")
    print("")
    for hostname in verified_hosts:
        pm.delete_kickstart_file(hostname)
    
    # 5. remove hosts from the management database
    print("======== Removing host registrations from Registration Database ========")
    print("")
    for hostname in verified_hosts:
        del pm.hosts[hostname]
    
    # 6. update management configuration flat file
    pm.update_host_registration() 
