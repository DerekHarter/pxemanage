# PXE Linux Boot Autoinstall Cluster Node Manager

This project contains scripts and data for setting up a PXE Linux
netboot to manage a cluster of bare-metal hardware nodes.  The system
maintains a database of registered cluster nodes, along with profiles
and information assigned to the nodes, like hostname and static ip
assignments.  The manager supports three basic tasks at the moment,
register new nodes into the cluster, reinstall existing cluster nodes,
and unregister nodes.

This system uses 3 linux services to manage the PXE Linux netboot and
cloud-init auto installation.  The dhcpd service is controlled to be
able to monitor when new nodes attempt a network boot, and to start
the boot and install over the network.  The tftpd (trivial file
transfer protocol) serves initial files for a pxe boot/autoinstall,
including the os images.  We also manage apache2 (or other web
service) which is used to serve the cloud-init kickstarter files and
the install image used for the autoinstall.
