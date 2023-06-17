#!/usr/bin/env python3
"""
Get policy-conforming paths between interesting sources and destinations in partitioned topology.

Output is a nested JSON dictionary of either paths or a path length histogram.
dict[src][dst] = [paths] | {path length: path count}

Usage:
./get_part_paths.py > partitioned_paths.json
"""

from collections import defaultdict
import concurrent.futures
import json
import sys

import docker
import python_on_whales

# Number of worker threads calling "scion showpaths"
# Progress output is interleaved and can be misleading if more than one thread is used
threads = 4

# Whether to output full paths or just a histogram of path lengths
histogram = False

# Number of spaces to indent output JSON with or None for no whitespace
output_indent = None


tier1_core = ["1-50", "1-60", "1-70"]
ixp_core = ["1-100", "1-101", "1-102", "1-103", "1-110", "1-111"]
cdn_core = ["1-200", "1-201"]
cdn = cdn_core + ["1-202", "1-203" "1-204" "1-205"]


def check_path(path):
    # Note: Transit ASes appear twice in hop list, as ingress and as egress hop
    ixp_hops = len([hop['isd_as'] for hop in path['hops'] if hop['isd_as'] in ixp_core]) // 2
    cdn_hops = len([hop['isd_as'] for hop in path['hops'] if hop['isd_as'] in cdn_core]) // 2

    # No paths through the core of the content provider if the destination is not in the CDN
    if cdn_hops > 0 and path['hops'][-1]['isd_as'] not in cdn:
        return False

    # No more than one IXP core AS on the path
    if ixp_hops > 1:
        return False

    # Don't use links between IXP and Tier-1 core (not even if Tier-1 is the source or destination)
    tier1_hops = (len([hop['isd_as'] for hop in path['hops'] if hop['isd_as'] in tier1_core]) + 1) // 2
    if tier1_hops > 0 and ixp_hops > 0:
        return False

    return True


def path_to_simple_list(path):
    hops = []
    for i, hop in enumerate(path['hops']):
        if i == 0 or i % 2 == 1:
            hops.append(hop['isd_as'])
    return hops


def length_histogram(paths):
    hist = defaultdict(lambda: 0)
    for path in paths:
        length = len(path["hops"]) // 2
        hist[length] += 1
    return hist


def get_valid_paths(src, destinations, ases):
    valid_paths_from_src = {}
    print(f"AS{src} ", end="", flush=True, file=sys.stderr)
    for dest in destinations:
        if dest == src:
            continue
        cmd = f"/usr/bin/scion showpaths 1-{dest} --json -m 5000"
        ec, output = ases[src].exec_run(cmd)
        if ec != 0:
            print(f"Error for {src}->{dest}", file=sys.stderr)
            for line in output.decode('utf8').splitlines():
                print("  " + line, file=sys.stderr)
            valid_paths_from_src[dest] = {}
            continue
        data = json.loads(output)
        valid = list(filter(check_path, data.get('paths', [])))
        if not histogram:
            valid_paths_from_src[dest] = [path_to_simple_list(path) for path in valid]
        else:
            valid_paths_from_src[dest] = length_histogram(valid)
        print(".", end="", flush=True, file=sys.stderr)
    print("", file=sys.stderr)
    return src, valid_paths_from_src


# Connect to docker daemon
whales = python_on_whales.DockerClient(compose_files=["./scion/docker-compose.yml"])
client: docker.DockerClient = docker.from_env()
ctrs = {ctr.name: client.containers.get(ctr.id) for ctr in whales.compose.ps()}

# Create ASN to CS container map
ases = {}
for name, ctr in ctrs.items():
    labels = ctr.attrs['Config']['Labels']
    asn = labels.get('org.seedsecuritylabs.seedemu.meta.asn')
    role = labels.get('org.seedsecuritylabs.seedemu.meta.role')
    if role == "SCION Control Service" and asn is not None:
        ases[int(asn)] = ctr

# Get valid paths
valid_paths = {}
leaf_ases  = [150, 151, 152, 160, 161, 162, 163, 171, 187, 188, 189, 190, 191]
cdn_ases   = [202, 203, 204, 205] # core ASes are just for the backbone
tier1_ases = [50, 51, 52, 53, 60, 70, 71, 72, 73]
sources = leaf_ases + tier1_ases
destinations = leaf_ases + cdn_ases + tier1_ases
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
