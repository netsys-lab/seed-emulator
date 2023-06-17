#!/usr/bin/env python3
from collections import defaultdict
import concurrent.futures
import json
import sys
import os
from time import strftime
from os.path import join

import docker
import python_on_whales

# Number of worker threads
# Progress output is interleaved and can be misleading if more than one thread is used
threads = 4

# Whether to output full paths or just a histogram of path lengths
histogram = False

tier1_core = ["1-50", "1-60", "1-70"]
ixp_core = ["1-100", "1-101", "1-102", "1-103", "1-110", "1-111"]
cdn_core = ["1-200", "1-201"]
cdn = cdn_core + ["1-202", "1-203" "1-204" "1-205"]

leaf_ases  = [150, 151, 152, 160, 161, 162, 163, 171, 187, 188, 189, 190, 191]
cdn_ases   = [202, 203, 204, 205] # core ASes are just for the backbone
tier1_ases = [50, 51, 52, 53, 60, 70, 71, 72, 73]
sources = leaf_ases + tier1_ases
destinations = leaf_ases + cdn_ases + tier1_ases

this_run = strftime("%Y-%m-%d-%H-%M-%S")
os.mkdir(this_run)

def map_as2addr(ases):
    as2addr = {}
    for as_, ctr in ases.items():
        ec, output = ctr.exec_run("scion address")
        if ec != 0:
            print(f"Error for {as_}", file=sys.stderr)
            for line in output.decode('utf8').splitlines():
                print("  " + line, file=sys.stderr)
            continue
        as2addr[as_]=output.decode("utf8").strip()
    return as2addr

def experiment(source, target, ctr):
    cmd = f"capacityseeker -remote {target}:1337"
    ec, (stdout, stderr) = ctr.exec_run(cmd, demux=True)
    if ec != 0:
            print(f"Error for {source}", file=sys.stderr)
            for line in stderr.decode('utf8').splitlines():
                print("  " + line, file=sys.stderr)
    if stdout:
        result = stdout.decode('utf8').splitlines()
    else:
        result = ["empty"]
    print(f"stderr of {source}", stderr.decode('utf8').splitlines()[-3:])
    print(f"stdout of {source}", result[-3:])
    return source, target, result


# Connect to docker daemon
whales = python_on_whales.DockerClient(compose_files=["./scion/docker-compose.yml"])
client: docker.DockerClient = docker.from_env()
ctrs = {ctr.name: client.containers.get(ctr.id) for ctr in whales.compose.ps()}

print("ctrs", ctrs.keys())
# Create ASN to CS container map
ases = {}
for name, ctr in ctrs.items():
    labels = ctr.attrs['Config']['Labels']
    asn = labels.get('org.seedsecuritylabs.seedemu.meta.asn')
    role = labels.get('org.seedsecuritylabs.seedemu.meta.role')
    if role == "SCION Control Service" and asn is not None:
        ases[int(asn)] = ctr
print("ases", ases.keys())
as2addr = map_as2addr(ases)
print("as2addr", as2addr)
targets = cdn_ases
#targets = list(ases.keys())
#sources = targets
sources = leaf_ases
arguments = []
for source in sources:
    targets = targets[-1:]+targets[:-1]
    while targets[0] == source:
        targets = targets[-1:]+targets[:-1]
    arguments.append((as2addr[source], as2addr[targets[0]], ases[source]))
for arg in arguments:
    print("running", arg)
results = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=len(arguments)) as executor:
    futures = {executor.submit(experiment, source, target, ctr) for source, target, ctr in arguments}
    print("futures", futures)
    for future in concurrent.futures.as_completed(futures):
        source, target, rs = future.result()
        with open(join(this_run, f"{source}->{target}.csv"), 'w') as file:
            file.writelines(rs)

# TODO: dump results to csv files
# try this in the large topology

sys.exit(0)

# Get valid paths
#valid_paths = {}
try:
    if threads < 2:
        for src in sources:
            valid_paths[src] = get_valid_paths(src, destinations, ases)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {executor.submit(get_valid_paths, src, destinations, ases) for src in sources}
            for future in concurrent.futures.as_completed(futures):
                src, paths = future.result()
                valid_paths[src] = paths
except KeyboardInterrupt:
    pass

# Output result
print(json.dumps(valid_paths, indent=output_indent))
