# SCION Secure Backbone AS (SBAS)

This example shows how to create an SBAS instance in the SEED emulator, and connect Points-of-Presence (PoPs) and customers to it.

**Status Quo limitations**:
- At the moment only a single SBAS instance per emulation is supported.
- Only SEED's default addressing scheme is supported, this won't work when you specify own IP ranges.
- Also only a single customer per PoP is supported, and customers can only be added to the second border router of an AS (it relies on .254 address).
- The proper SBAS ASN (set via `sbas.setAsn`) is not announced yet to the customers. Anyway, connectivity works, so this status can be tested.
- The order of layers in the bottom of the `sbas.py` must not be changed yet. There are some dependencies that break when changing the order.

We are working on removing these limitations in upcoming versions.

## What is SBAS
There is a great explanation and guide on sbas on [github](https://github.com/scion-backbone/sbas), please refer to this for further details.


## General structure
Here you can find a picture of the configured topology. It consists of 4 SBAS PoP's and 4 customers. Inside the secure AS only SCION connectivity is configured, so there are no BGP sessions between the ASes. For these links, it does not matter if they are over an IX or cross connects. However, the links between SBAS customers and PoP's need to be always done over IXes. You can see that you need to pass the IX number in the `sbas.addCustomer` call.

At the moment the Secure AS works the following way: Each PoP has a SCION IP Gateway (SIG) configured on the CS node, all of these SIG's are connected to each other. They announce their own nets, and also those of all customers. The BorderRouter instances to the customers announce then all routes to all other customers over SBAS.

## Use SBAS Layer
Similar to all other layers, sbas can be imported from `seedemu.layers` and called via `ScionSbas`.

```python
# Import
from seedemu.layers import ScionSbas # ...

# Initiate
sbas = ScionSbas()

# Your code ...

# Add layer to compilation
emu.addLayer(sbas)
```

## Configure a PoP
A Pop is a regular SCION AS that connects to other Pops, either via cross connects or via IXes. Each pop needs to have a second router and IX to connect customers to. This a strict limitation at the moment.

```python
# Default SCION Setup
as150 = base.createAutonomousSystem(150)
scion_isd.addIsdAs(1, 150, is_core=True)
as150.createNetwork('net0')
cs1 = as150.createControlService('cs1').joinNetwork('net0')

# Create one Border Router that connects to other SCION ASes over an IX
as150_router = as150.createRouter('br0')
as150_router.joinNetwork('net0').joinNetwork('ix100')

# Create a second Border Router that connects to all customers of the PoP
as150_router2 = as150.createRouter('br1')
as150_router2.joinNetwork('net0').joinNetwork('ix101')
```

## Configure a Customer
Customer ASes are regular ASes that connect via dedicated IXes to one PoP. At the moment they need to have an ISDAS configured as seen below, otherwise it won't compile. Anyway, customer ASes do not have any kind of SCION connectivity in this context.

```python
# AS-151, customer of 150
as151 = base.createAutonomousSystem(151)
# TODO: Although this is a pure BGP AS, we still need to have this at the moment...
scion_isd.addIsdAs(1, 151, is_core=True)
as151.createNetwork('net0')

# Connect the Border Router to the IX that connects to the proper PoP
as151.createRouter('br0').joinNetwork('net0').joinNetwork('ix101')
```

## Configure inter-domain links
Next, links between customer-PoP and Pop-Pop need to be configured.

```python
# Links between PoPs
scion.addIxLink(100, (1, 150), (1, 152), ScLinkType.Core)
scion.addIxLink(100, (1, 150), (1, 154), ScLinkType.Core)
scion.addIxLink(100, (1, 150), (1, 160), ScLinkType.Core)

# Customer-PoP links
ebgp.addPrivatePeering(101, 150, 151, abRelationship=PeerRelationship.Peer)
ebgp.addPrivatePeering(102, 152, 153, abRelationship=PeerRelationship.Peer)
```

## Configure SBAS
Next, the configuration of SBAS itself needs to be done. At the moment it is designed to have a single SBAS instance per emulation, which has a dedicated ASN. This ASN is not yet announced properly everywhere, but this does not impact routing of subnets.

```python
# Will be supported soon...
sbas.setAsn(160)

# Add the pop configured before
sbas.addPop(150)

# Add customer 151 to 150 via IX 101
# First argument is the pop, second the customer and the last one the IX at which customer and pop connect
sbas.addCustomer(150, 151, 101)
```

## Start and run
To start und run the topology, do the following:

```sh
python3 sbas.py
cd output
docker compose build 
docker compose up -d
```

## Testing SBAS
Now that you have the setup running, you can test connectivity between the customers through SBAS. You can use SEED's webclient or just your local terminal to do so.

You can find all running containers via `docker ps` and the output should look like this:
```sh
➜  output git:(feature/scion-sbas) ✗ docker ps
CONTAINER ID   IMAGE                   COMMAND       CREATED      STATUS         PORTS     NAMES
008bd89c5ea9   output-csnode_160_cs1   "/start.sh"   4 days ago   Up 6 seconds             as160h-cs1-10.160.0.71
00d3854c26d8   output-csnode_154_cs1   "/start.sh"   4 days ago   Up 2 seconds             as154h-cs1-10.154.0.71
2b21841d49df   output-csnode_156_cs1   "/start.sh"   4 days ago   Up 5 seconds             as156h-cs1-10.156.0.71
c1aa41be4d46   output-csnode_152_cs1   "/start.sh"   4 days ago   Up 3 seconds             as152h-cs1-10.152.0.71
7baacdd55f08   output-csnode_150_cs1   "/start.sh"   4 days ago   Up 4 seconds             as150h-cs1-10.150.0.71
b614dad4c516   output-rnode_150_br0    "/start.sh"   4 days ago   Up 2 seconds             as150r-br0-10.150.0.254
778ea04a48b0   output-rnode_155_br0    "/start.sh"   4 days ago   Up 3 seconds             as155r-br0-10.155.0.254
cba0a12a2080   output-rs_ix_ix100      "/start.sh"   4 days ago   Up 5 seconds             as100rs-ix100-10.100.0.100
2dba160bb2ad   output-rnode_160_br0    "/start.sh"   4 days ago   Up 2 seconds             as160r-br0-10.160.0.254
341b2eba2cdd   output-rnode_141_br0    "/start.sh"   4 days ago   Up 3 seconds             as141r-br0-10.141.0.254
f97712b7d770   output-rs_ix_ix103      "/start.sh"   4 days ago   Up 5 seconds             as103rs-ix103-10.103.0.103
43dc7bc7d1fb   output-rnode_156_br0    "/start.sh"   4 days ago   Up 2 seconds             as156r-br0-10.156.0.254
a8dbaddca7f8   output-rnode_154_br0    "/start.sh"   4 days ago   Up 4 seconds             as154r-br0-10.154.0.254
1ce57bee0887   output-rnode_153_br0    "/start.sh"   4 days ago   Up 4 seconds             as153r-br0-10.153.0.254
828de4784dd4   output-rnode_157_br0    "/start.sh"   4 days ago   Up 3 seconds             as157r-br0-10.157.0.254
6e3b05e55fa2   output-rs_ix_ix104      "/start.sh"   4 days ago   Up 5 seconds             as104rs-ix104-10.104.0.104
3eb336dd7201   output-rnode_156_br1    "/start.sh"   4 days ago   Up 3 seconds             as156r-br1-10.156.0.253
ca239f36886d   output-rnode_150_br1    "/start.sh"   4 days ago   Up 2 seconds             as150r-br1-10.150.0.253
07c6d48fb9d3   output-rnode_154_br1    "/start.sh"   4 days ago   Up 2 seconds             as154r-br1-10.154.0.253
5c97e56f4ba7   output-rnode_152_br0    "/start.sh"   4 days ago   Up 3 seconds             as152r-br0-10.152.0.254
ff30c0b80fd0   output-rnode_151_br0    "/start.sh"   4 days ago   Up 2 seconds             as151r-br0-10.151.0.254
31f85d0166c8   output-rs_ix_ix102      "/start.sh"   4 days ago   Up 5 seconds             as102rs-ix102-10.102.0.102
fc80a3c19f55   output-rnode_152_br1    "/start.sh"   4 days ago   Up 2 seconds             as152r-br1-10.152.0.253
a1191880b8cc   output-rs_ix_ix101      "/start.sh"   4 days ago   Up 4 seconds             as101rs-ix101-10.101.0.101
```

Open a terminal in one of the customers containers (mainly `br-0` containers, since there are not yet any hosts in the ASes), one example is the Border Router of customers as `153`, namely `as153r-br0-10.153.0.254`. You can run `docker exec -it as153r-br0-10.153.0.254 /bin/bash` to open a terminal in this container.

**Note: It may take a while until all routes are setup and announced, so right after starting there may be routes missing in the containers, give it some time to warm up...** 

At first, it makes sense to check the routes that the container has, it should have routes to all other customer ASes, via `ip route`:

```sh
10.102.0.0/24 dev ix102 proto kernel scope link src 10.102.0.153 
10.150.0.0/24 via 10.102.0.152 dev ix102 proto bird metric 32 
10.151.0.0/24 via 10.102.0.152 dev ix102 proto bird metric 32 
10.152.0.0/24 via 10.102.0.152 dev ix102 proto bird metric 32 
10.153.0.0/24 dev net0 proto kernel scope link src 10.153.0.254 
10.153.0.0/24 dev net0 proto bird scope link metric 32 
10.154.0.0/24 via 10.102.0.152 dev ix102 proto bird metric 32 
10.155.0.0/24 via 10.102.0.152 dev ix102 proto bird metric 32 
10.156.0.0/24 via 10.102.0.152 dev ix102 proto bird metric 32 
10.157.0.0/24 via 10.102.0.152 dev ix102 proto bird metric 32
```

You can see the routes to all customers ASes (and also to the internal SBAS ASes, this is currently for testing purposes). In the case of this router, you can see that the other customer ASes are announced via bird through the connected IX 102. To test connectivity into other ASes, you can use ping, e.g. with:

```sh
root@d71b98f86f4d / # ping 10.157.0.1
PING 10.157.0.1 (10.157.0.1) 56(84) bytes of data.
64 bytes from 10.157.0.1: icmp_seq=1 ttl=64 time=1.24 ms
64 bytes from 10.157.0.1: icmp_seq=2 ttl=64 time=1.64 ms
64 bytes from 10.157.0.1: icmp_seq=3 ttl=64 time=0.604 ms
64 bytes from 10.157.0.1: icmp_seq=4 ttl=64 time=0.507 ms
64 bytes from 10.157.0.1: icmp_seq=5 ttl=64 time=0.494 ms
64 bytes from 10.157.0.1: icmp_seq=6 ttl=64 time=1.70 ms
64 bytes from 10.157.0.1: icmp_seq=7 ttl=64 time=0.959 ms
^C
--- 10.157.0.1 ping statistics ---
7 packets transmitted, 7 received, 0% packet loss, time 6053ms
rtt min/avg/max/mdev = 0.494/1.020/1.700/0.479 ms
```