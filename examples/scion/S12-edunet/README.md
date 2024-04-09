# SCION Education Network Topology

## Topology
![education-isd-as-overview (5)](https://github.com/netsys-lab/seed-emulator/assets/32448709/5b551faa-ce1c-4a81-bb91-734972e892cd)


## Usage
SCION commands can be run from the CS nodes (`cs1`). There is a list of environment variables that store the ASes and the Host IPs to easily interact with other ASes:

SCION Showpaths:
`scion showpaths $UVA`

SCION Ping:
`scion ping $UVA_HOST`

```
root@a2207c275924 / # set | grep "71-"
BRIDGES=71-10
BRIDGES_HOST=71-10,10.10.0.71
CYBEXER=71-103
CYBEXER_HOST=71-103,10.103.0.71
DEMOKRITOS=71-106
DEMOKRITOS_HOST=71-106,10.106.0.71
EQUINIX=71-100
EQUINIX_HOST=71-100,10.100.0.71
GEANT=71-11
GEANT_HOST=71-11,10.11.0.71
KISTI_AMS=71-12
KISTI_AMS_HOST=71-12,10.12.0.71
KISTI_CHG=71-15
KISTI_CHG_HOST=71-15,10.15.0.71
KISTI_DJ=71-14
KISTI_DJ_HOST=71-14,10.14.0.71
KISTI_SG=71-13
KISTI_SG_HOST=71-13,10.13.0.71
OVGU=71-105
OVGU_HOST=71-105,10.105.0.71
PRINCETON=71-102
PRINCETON_HOST=71-102,10.102.0.71
SIDN=71-104
SIDN_HOST=71-104,10.104.0.71
UVA=71-101
UVA_HOST=71-101,10.101.0.71
```
