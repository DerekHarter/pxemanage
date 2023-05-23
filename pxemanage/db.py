"""pxemanage module

db submodule

Contents
--------

Functions relating to the hosts database that we mainting to manage
pxeboot installs.  We are actually using the dhcpd.conf configuration
file of the dhcpd service as a flat file store.  We parse this file to
get the current host database under management when we begin.  And
whenever new hosts are registered we write out the database and
restart dhcpd service.

We are using a simple dictionary of Host classes as the database for
now.  The Host class is an extension of the system dictionary class,
so hosts can be accessed using key, or by using attributes.

"""
import re
import subprocess
from enum import Enum
#from pxemanage import settings, j2
import pxemanage as pm


# we will use a simple dictionary with hostname as key
# to manage our host database for now
hosts = {}


# define an enumerated type to keep track of the status
# of hosts being managed
class status(Enum):
    REGISTERED = 1
    DHCPOFFER = 2
    INSTALLING = 3
    REBOOTING = 4
    RUNNING = 5


class Host(dict):
    """Really just a structure that keeps track of all information about
    registered hosts we are managing.

    Actually this class is a dict so that we can easily pass into j2
    to render templates.  But it can act like a struct because we
    override the getattr method.

    """
    def __init__(self, hostname, macaddress="unknown",
                 ipaddress="unknown", profile="default",
                 status=status.RUNNING):
        """Define class constructor for our Host struct/dict

        Parameters
        ----------
        hostname - the name of the host as it is referred to in the cluster
        macaddress - the hardware mac address of the host.  Defaults to unknown.
        ipaddress - the ip (internet protocal) address assigned as a staic
          ip to this host in our cluster.
        profile - the hardware profile we use to perform initial install/os
          configuration for this host
        status - the current status of the host (registered, dhcpoffer, etc.)
        """
        self.hostname = hostname
        self.macaddress = macaddress
        self.ipaddress = ipaddress
        self.profile = profile
        self.status = status

    def __getattr__(self, name):
        """Overload member access (getting an attribute) so that we can
        perform, for example, host.ipaddress and have it lookup the
        value for the key for us.

        Parameters
        ----------
        name - the attribute/key name to look up / retrieve for this host.

        Returns
        -------
        value - returns the attribute value for the retrieved key.  An exception
           will be thrown if you try to retrieve an attribute that is not a valid
           key item currently for this host.
        """
        return self.__getitem__(name)

    def __str__(self):
        """Overload the string representation of this class to create and return
        a human readable representation of this hosts registered properties.  
        This method is used in logging output while running pxemanage 
        operations.

        Returns
        -------
        string - returns a python string object suitable for writing/display of
           this hosts attributes.
        """
        host_str = f"""
Host: {self.hostname}
      macaddress: {self.macaddress}
      static ip : {self.ipaddress}
      profile   : {self.profile}
      status    : {self.status}
"""
        return host_str

    def macaddress_file(self):
        """pxeboot needs a macaddress in this format:
                11:22:33:44:55:66
        to correspond to a file name like this:
             01-11-22-33-44-55-66
        (for some reason pxeboot prepends 01 on these file
        file names)

        Returns
        -------
        macaddress file name - returns the mac address in a format
          suitable for and expected by pxeboot when looking up the
          pxeboot file for a machine being boot installed.
        """
        macaddress_file = self.macaddress.replace(':', '-')
        macaddress_file = f"01-{macaddress_file}"
        return macaddress_file


def is_registered(macaddress):
    """Return true if we already have this macaddress registered as
    a cloudstack cluster host, false if not.

    Parameters
    ----------
    macaddress - The hardware mac address we want to look up in the
      hosts database

    Returns
    -------
    bool - true is returned if there is a host registered with this
      hardware address in our cluster, false if we do not manage 
      a host with this mac address.
    """
    hostname = lookup_host_by_mac(macaddress)

    if hostname:
        return True
    else:
        return False


def lookup_host_by_mac(macaddress):
    """Search registration database to see if the given
    macaddress is already registered or not.

    Parameters
    ----------
    macaddress - The hardware mac address we want to look up in the
      hosts database

    Returns
    -------
    host - Returns an instance of a Host object if we find a machine
      in the host database with that hardware mac address.  None is
      returned instead if no host is registered with that mac address.
    """
    # return first hostname found registered with that macaddress
    for hostname in hosts:
        if hosts[hostname].macaddress == macaddress:
            return hostname

    # indicate failure by returning None
    return None


def lookup_host_by_ipaddress(ipaddress):
    """Search registration database to see if the given
    ipaddress is already registered or not.

    Parameters
    ----------
    ipaddress - The ip (internet protocol) address we want to search 
      for in our hosts database we are managing.

    Returns
    -------
    host - Returns an instance of a Host object if we find a machine
      in the host database with that ip address.  None is
      returned instead if no host is registered as using that ip
      address.
    """
    # return first hostname found registered with that macaddress
    for hostname in hosts:
        if hosts[hostname].ipaddress == ipaddress:
            return hostname

    # indicate failure by returning None
    return None


def load_host_registration():
    """Parse the host registration file (dhcpd.conf).  This file keeps
    track of all host information for hosts being managed in our
    cloudstack (or other) cluster.

    We are currently using the dhcpd.conf file to keep track of
    managed host information.  This may be inadequate for more
    advanced needs.  We use simple regular expressions to parse, but
    this could be easily enhanced using a simple yaml parser or
    equivalent here.

    Returns
    -------
    No explicit values is returned, but implicitly the hosts
    management database is populated with all hosts being managed
    for dhcp/pxe boot for this cluster after this function
    finishes.
    """
    current_host = None
    for line in open(pm.settings['registration_file']).readlines():
        # search for a host block, all options read
        # from subsequent lines pertain to this host until
        # we see the next host block
        pattern = re.compile(r"^\s*host\s+(\w+).*$")
        match = pattern.match(line)
        if match:
            hostname = match.group(1)
            #print(f"Parsing host: {hostname}")
            current_host = Host(hostname)
            hosts[hostname] = current_host

        # search for hardware ethernet mac address
        mac_pattern = "..:..:..:..:..:.."
        pattern = re.compile(f"^\s*hardware\s+ethernet\s+({mac_pattern});.*$")
        match = pattern.match(line)
        if match:
            macaddress = match.group(1)
            #print(f"    matched mac address: {macaddress}" %)
            current_host.macaddress = macaddress

        # search for static ip address assignment
        ip_pattern = "\d+\.\d+\.\d+\.\d+"
        pattern = re.compile(f"^\s*fixed-address\s+({ip_pattern});.*$")
        match = pattern.match(line)
        if match:
            ipaddress = match.group(1)
            #print(f"    matched ip address: {ipaddress}")
            current_host.ipaddress = ipaddress

        # search for cloudstack profile assignment
        pattern = re.compile(r"^\s*\#*\s*cloudstack\s+profile\s+(\w+);.*$")
        match = pattern.match(line)
        if match:
            profile = match.group(1)
            #print(f"    matched profile: {profile}")
            current_host.profile = profile

    print("======== Read Host Registration ========")
    print("The list of registered hosts discovered")
    for hostname in hosts:
        print(hosts[hostname])
    print("")


def update_host_registration():
    """Write out a new registration database configuration to them
    dhcpd.conf file that we are using to maintain our cloudstack
    cluster host registration information in.

    We recreate the whole file with all registered hosts entered to
    make this routine simple.
    """
    print("======== Update dhcpd.conf registration file ========")
    print("")
    new_registration_file = "./dhcpd.conf"

    # get dhcpd.conf template and render its contents
    # TODO: should templatize the router and dns information
    #   in this template as well.
    template = pm.j2.get_template("dhcpd.conf.j2")
    content = template.render(hosts=hosts)
    file = open(f"{new_registration_file}", mode="w")
    file.write(content)
    file.close()
    
    # now use sudo root authentication to copy the updated
    # dhcpd.conf / registration to correct location
    command = f"sudo cp {new_registration_file} {pm.settings['registration_file']}"
    subprocess.run(command, shell=True)
