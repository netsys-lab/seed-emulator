#!/usr/bin/env python3

import json
import sys

data = json.load(sys.stdin)

tier1_core = ["1-50", "1-60", "1-70"]
ixp_core = ["1-100", "1-101", "1-102", "1-103", "1-110", "1-111"]
cdn_core = ["1-200", "1-201"]


def check_path(path):
    # Note: Transit ASes appear twice in hop list, as ingress and as egress hop
    tier1_hops = len([hop['isd_as'] for hop in path['hops'] if hop['isd_as'] in tier1_core]) // 2
    ixp_hops = len([hop['isd_as'] for hop in path['hops'] if hop['isd_as'] in ixp_core]) // 2
    cdn_hops = len([hop['isd_as'] for hop in path['hops'] if hop['isd_as'] in cdn_core]) // 2

    # No paths through the core of the content provider
    if cdn_hops > 0:
        return False

    # No more than one IXP core AS on the path
    if ixp_hops > 1:
        return False

    # Don't use links between IXP and Tier-1 core
    if tier1_hops > 0 and ixp_hops > 0:
        return False

    # Don't use core AS of large access network
    for hop in path['hops']:
        if hop['isd_as'] == "1-180":
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
