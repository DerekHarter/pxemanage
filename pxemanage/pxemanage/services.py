"""
pxemanage module

services submodule

Contents
--------

Functions relating to stopping, starting, restarting and
managing system services are found here.  We need to
control dhcpd, tftpd and apache2 (or other web) services
to manage the pxeboot
"""
import subprocess
from pxemanage import settings


def restart_services():
    """(re)Start the services needed for cluster host registration.
    We usually need dhcpd, tftpd and apache2 services running.
    On the ansible management machine it is not normal to have these
    running continuously, only when we are registering or 
    reinstalling hosts.

    We restart in case somehow they are already running, to
    ensure that their config files are reloaded.

    NOTE: we use sudo root escalation here, so this requires
    that this script be run as root or as an sudo enabled user.
    """
    print("======== Start registration services ========")
    for service_name in settings['service_list']:
        print(f"    -------- starting service {service_name}")
        command = f"sudo systemctl restart {service_name}"
        subprocess.run(command, shell=True)
    print("")


def restart_dhcpd_service():
    """Retart the dhcpd service.  Ensure it is running on this machine.
    """
    print("======== Restart dhcpd service ========")
    print(f"    -------- restarting service {settings['dhcpd_service_name']}")
    command = f"sudo systemctl restart {settings['dhcpd_service_name']}"
    subprocess.run(command, shell=True)
    print("")


def stop_services():
    """Stop the services needed for cluster host registration.
    It is normal that we usually only have these running on
    the ansible management machine when we are doing
    registrations or reinstalls.

    NOTE: we use sudo root escalation here, so this requires
    that this script be run as root or as an sudo enabled user.
    """
    print("======== Stop registration services ========")
    for service_name in settings['service_list']:
        print(f"    -------- stopping service {service_name}")
        command = f"sudo systemctl stop {service_name}"
        subprocess.run(command, shell=True)
    print("")
