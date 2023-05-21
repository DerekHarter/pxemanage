"""pxemanage module

kickstart submodule

Contents
--------

The ks, or kickstart files, are served by the apache web server (for
some reason, I wonder why original design just didn't use tftp for
serving all files for the boot?)

This submodule contains functions for creating and maintaining the
kickstart files.

The main file is a file named 'user-data'.  We are using cloud-init
autoinstall user data files for our pxelinux boots.  Basically the
user-data file can be set up with all the information to install a
nodes operating system without intervention.  Some cluster nodes
basically have the same hardware/os configuration, and they can all
share a profile.  For example, usually all compute nodes in a cluster
have the same hardware profile.  The only difference in the
'user-data' file for these machines is the hostname and ip address.
But there are usually a set of 3 or 4 basic hardware profiles.  We
maintain a separate directory of profiles, which are used as jinga
templates to create the specific 'user-data' file for a new host,
filling in any parameter specific to the host.

"""
import subprocess
import pxemanage as pm


def create_kickstart_file(hostname):
    """Create a host kickstart file from the profile registered for
    this host.  Given the name of the host, we lookup the host
    in our hosts database.  We use the hosts profile to 
    fill in the template for hosts of this given hardware
    configuration, to create the user-data (and other) files
    that will be served to this host when it pxe boots.

    Parameters
    ----------
    hostname - We are given the name of the new host that needs 
      a new kickstart file for it.  
    """
    # lookup host in registration database
    host = pm.hosts[hostname]
    ks_config = f"{pm.settings['ks_config_dir']}/{host.hostname}"
    
    print("======== Create kickstart files ========")
    print(f"    ----- creating kickstart files for : {host.hostname}")
    print(f"    -----                 using profile: {host.profile}")
    print(f"    -----                kickstart name: {ks_config}")
    print("")
    
    # create new subdirectory in ks hierarchy to hold this hosts kickstart file
    command = f"mkdir -p {ks_config}"
    subprocess.run(command, shell=True)

    # get user-data template and render it contents
    # TODO: we should probably render the gateway and name servers
    #   into the user-data here as well.
    management_key = open(pm.settings['ansible_manager_key']).readlines()[0].strip()
    management_key = f'"{management_key}"'
    template = pm.j2.get_template(f"profiles/{host.profile}/user-data.j2")
    content = template.render(hostname = host.hostname,
                              ipaddress = host.ipaddress,
                              management_key = management_key)
    file = open(f"{ks_config}/user-data", mode="w")
    file.write(content)
    file.close()
        
    # copy the meta-data file from profile, these currently don't
    # have any templates to render, but we'll keep in just in case
    template = pm.j2.get_template(f"profiles/{host.profile}/meta-data.j2")
    content = template.render()
    file = open(f"{ks_config}/meta-data", mode="w")
    file.write(content)
    file.close()

    # TODO: this is getting kludgy, as a result of trying to move
    #    location of served files to own directory, need to have permissions
    #    exactly correct.  This needs to be run after the sed updates?
    command = f"sudo chown -R dash:www-data {ks_config}"
    subprocess.run(command, shell=True)
