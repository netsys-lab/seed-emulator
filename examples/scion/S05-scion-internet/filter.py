#!/usr/bin/env python3
"""
Usage:
cd scion
docker exec -it <container> /usr/bin/scion showpaths <destination> -m 5000 --json | ../filter.py
"""

import json
import sys

data = json.load(sys.stdin)

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


valid = list(filter(check_path, data['paths']))

for i, path in enumerate(valid):
    print("[{:3}] ".format(i), end="")
    for i, hop in enumerate(path['hops']):
        if i == 0 or i % 2 == 1:
            print(hop['isd_as'], end=" ")
    print("")

print("Paths:", len(valid))
