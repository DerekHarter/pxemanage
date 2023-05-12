#!/bin/bash
#
# This script can be run on a cloudstack management node that has
# cloud monkey command line tool (cmk) installed and configured with
# authroization information.  We may/could move this into
# an ansible script in future.


# create zone using settings
zone_name="Zone1"
dns1="8.8.8.8"
dns2="8.8.4.4"
internaldns1="8.8.8.8"
internaldns2="8.8.4.4"
networktype="Advanced"
guestcidraddress="10.1.1.0/24"

cmk create zone \
    name=${zone_name} \
    dns1=${dns1} \
    dns2=${dns2} \
    internaldns1=${internaldns1} \
    internaldns2=${internaldns2} \
    networktype=${networktype} \
    guestcidraddress=${guestcidraddress}
zone_id=`cmk list zones name="${zone_name}" filter=id | grep "id" | awk '{print $2}'`
echo "Created zone name: ${zone_name}  id: ${zone_id}"


# create physical network using settings
phy_name="Physical Network 1"
vlan="100-200"
isolationmethods="VLAN"

cmk create physicalnetwork \
    name="${phy_name}" \
    zoneid=${zone_id} \
    vlan=${vlan} \
    isolationmethods=${isolationmethods}
phy_id=`cmk list physicalnetworks name="${phy_name}" filter=id | grep "id" | awk '{print $2}'`
echo "Created physical network name: ${phy_name} id: ${phy_id}"

# specify traffic types for this new physical network
cmk add traffictype traffictype=Guest physicalnetworkid=${phy_id}
cmk add traffictype traffictype=Management physicalnetworkid=${phy_id}
cmk add traffictype traffictype=Public physicalnetworkid=${phy_id}
cmk add traffictype traffictype=Storage physicalnetworkid=${phy_id}
echo "Added Guest, Management, Public and Storage traffic types to physical network name: ${phy_name}"

# can enable physical network now, though we don't enable the zone until after
# all infrastructure is created
cmk update physicalnetwork state=Enabled id=${phy_id}

# when the physical network was created and enabled, a VirtualRouter system vm? should
# have been created for it.  We need its id to enable
nsp_id=`cmk list networkserviceproviders name=VirtualRouter physicalnetworkid=${phy_id} | grep "\"id\":" | awk '{print $2}' | tr -d ,`
vre_id=`cmk list virtualrouterelements nspid=${nsp_id} | grep "\"id\":" | awk '{print $2}' | tr -d ,`
cmk configureVirtualRouterElement enabled=true id=${vre_id}
cmk update networkserviceprovider state=Enabled id=${nsp_id}
echo "Enabled virtual router element and network service provider"


# we didn't enable security groups following quick install, but if need to then do the following
#nsp_sg_id=`cmk list networkserviceproviders name=SecurityGroupProvider physicalnetworkid=${phy_id} | grep "\"id\":" | awk '{print $2}' | tr -d ,`
#cmk update networkserviceprovider state=Enabled id=${nsp_sg_id}
#echo "Enabled security group provider"


# create a network, actually this is not done in the setup wizard, should we do it here?
net1_name="HarterHouseNet"
net1_display_text="Harter Household Cloud Network"
net1_cidr="10.1.1.0/24"
net1_gateway="10.1.1.1"
net1_netmask="255.255.255.0"

netoff_id=`cmk list networkofferings name="DefaultIsolatedNetworkOfferingWithSourceNatService" | grep "\"id\":" | awk '{print $2}' | tr -d ,`
cmk create network \
    zoneid=${zone_id} \
    name=${net1_name} \
    displaytext="${net1_display_text}" \
    networkofferingid=${netoff_id} \
    cidr=${net1_cidr} \
    dns1=${dns1} \
    dns2=${dns2} \
    gateway=${net1_gateway} \
    netmask=${net1_netmask}
net_id=`cmk list networks name="${net1_name} | grep "\"id\":" | awk '{print $2}' | tr -d ,`
echo "Created network name: ${net1_name} id: ${net_id} for zone: ${zone_id}"


# create a pod
pod_name="Pod-Zone1"
pod_gateway="192.168.0.1"
pod_netmask="255.255.255.0"
pod_start="192.168.0.201"
pod_end="192.168.0.254"
vlan_start="192.168.0.154"
vlan_end="192.168.0.200"

cmk create pod \
    name="${pod_name}" \
    zoneid=${zone_id} \
    gateway=${pod_gateway} \
    netmask=${pod_netmask} \
    startip=${pod_start} \
    endip=${pod_end}
pod_id=`cmk list pods name="${pod_name}" |  grep "\"id\":" | awk '{print $2}' | tr -d ,`

cmk create vlaniprange \
    podid=${pod_id} \
    physicalnetworkid=${phy_id} \
    networkid=${net_id} \
    gateway=${pod_gateway} \
    netmask=${pod_netmask} \
    startip=${vlan_start} \
    endip=${vlan_end} \
    forvirtualnetwork=true
echo "Created pod and ip ranges pod name: ${pod_name} id: ${pod_id}"

# create a cluster
cluster_name="Cluster-Zone1"
hypervisor="KVM"
cluster_type="CloudManaged"

cmk add cluster \
    clustername="${cluster_name}" \
    zoneid=${zone_id} \
    hypervisor=${hypervisor} \
    clustertype=${cluster_type} \
    podid=${pod_id} 
cluster_id=`cmk list clusters name=${cluster_name} | grep "\"id\":" | awk '{print $2}' | tr -d ,`
echo "Created cluster name: ${cluster_name} id: ${cluster_id}"


# add hosts to the cluster
host_names="cloud02"
host_user=root
host_password="enabling ssh key access should allow this to work without password"

# getting an error here currently
# Error: (HTTP 530, error code 9999) Could not add host at [http://cloud02]
#   with zone [1], pod [1] and cluster [1] due to:
#   [ can't setup agent, due to com.cloud.utils.exception.CloudRuntimeException:
#   Unable to persist the host_details key: password for host id: 2 -
#   Unable to persist the host_details key: password for host id: 2].


for host_name in ${host_names}
do
    cmk add host \
	zoneid=${zone_id} \
	podid=${pod_id} \
	clusterid=${cluster_id} \
	hypervisor=${hypervisor} \
	url="http://${host_name}" \
	username=${host_user}
	# need username and key auth method?
	
    echo "Added host name: ${host_name}"
done

# create storage pools
primary_name="Primary1"
primary_ip=192.168.0.2
primary_path=/export/primary
primary_url="nfs://${primary_ip}${primary_path}"

cmk create storagepool \
    zoneid=${zone_id} \
    podid=${pod_id} \
    clusterid=${cluster_id} \
    name="${primary_name}" \
    url="${primary_url}"
echo "Added primary storage name: ${primary_name}"

secondary_name="Secondary1"
secondary_ip=192.168.0.2
secondary_path=/export/secondary
secondary_url="nfs://${secondary_ip}${secondary_path}"
secondary_scope="ZONE"
secondary_provider="NFS"

cmk add secondarystorage \
    zoneid=${zone_id} \
    scope=${zone_scope} \
    url="${secondary_url}" \
    providername=${secondary_provider} \
    name="${secondary_name}"
echo "Added secondary storage name: ${secondary_name}"

# finally can deploy the zone
cmk update zone allocationstate=Enabled id=${zone_id}
echo "Basic zone deployment completed!"
