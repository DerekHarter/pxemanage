import pxemanage as pm

host = pm.Host('host01', '11:22:33:44:55:66', '192.168.0.1', 'profile')

def test_host_attributes():
    assert host.hostname == 'host01'
    assert host.macaddress == '11:22:33:44:55:66'
    assert host.ipaddress == '192.168.0.1'
    assert host.profile == 'profile'
    assert host.status == pm.status.RUNNING

expected_host_str = """
Host: host01
      macaddress: 11:22:33:44:55:66
      static ip : 192.168.0.1
      profile   : profile
      status    : status.RUNNING
"""

def test_host_str():
    host_str = f"{host}"
    assert host_str == expected_host_str


def test_macaddress_file():
    assert host.macaddress_file() == '01-11-22-33-44-55-66'

# construct a host database with a few more hosts
pm.hosts['host01'] = host

host02 = pm.Host('host02', '66:55:44:33:22:11', '192.168.0.2', 'otherprofile')
pm.hosts['host02'] = host02

host03 = pm.Host('host03', '18:03:73:c5:91:89', '192.168.0.3', 'manager', pm.status.INSTALLING)
pm.hosts['host03'] = host03


def test_is_registered():
    assert pm.is_registered('11:22:33:44:55:66')
    assert pm.is_registered('18:03:73:c5:91:89')
    assert not pm.is_registered('12:34:56:78:90:12')
    

def test_lookup_mac():
    assert pm.lookup_host_by_mac('11:22:33:44:55:66') == 'host01'
    assert pm.lookup_host_by_mac('11:22:33:44:55:77') is None

def test_lookup_host_by_ip():
    assert pm.lookup_host_by_ipaddress('192.168.0.2') == 'host02'
    assert pm.lookup_host_by_ipaddress('192.168.0.9') is None
