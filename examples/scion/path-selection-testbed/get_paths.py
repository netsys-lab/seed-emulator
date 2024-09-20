import json
import os
import subprocess

def execute_command(command):
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output, error = process.communicate()
        return output, error, process.returncode
    except Exception as e:
        return None, str(e), -1

def get_isd(asn, topo):
    for as_ in topo['ASes']:
        if as_['asn'] == asn:
            return as_['isd']
    return None

def get_topology(container_name):
    command = 'docker exec {} /bin/zsh -c "cat /etc/scion/topology.json"'.format(container_name)
    output, error, return_code = execute_command(command)

    if return_code == 0:
        try:
            result_dict = json.loads(output)
            # print("Loaded JSON to dict")
        except json.JSONDecodeError:
            print("Failed to decode JSON:", output)
            return None
    else:
        print("Failed to execute command. Error:", error)
        return None
    return result_dict

def get_paths_from_host(dst_isd, dst_asn, container_name):
    command = 'docker exec {} /bin/zsh -c "scion showpaths {}-{} --format json -m 100"'.format(container_name, dst_isd, dst_asn)
    output, error, return_code = execute_command(command)

    if return_code == 0:
        try:
            result_dict = json.loads(output)
            print("Loaded JSON to dict")
        except json.JSONDecodeError:
            print("Failed to decode JSON:", output)
            return None
    else:
        print("Failed to execute command. Error:", error)
        return None
    return result_dict


if __name__ == "__main__":
    topo = json.load(open("./topo/topo.json"))
    receiver_asn = topo['receiver_asn']
    receiver_isd = get_isd(receiver_asn, topo)
    sender_asn = topo['sender_asn']
    sender_isd = get_isd(sender_asn, topo)

    paths = get_paths_from_host(receiver_isd, receiver_asn, "as{}h-h1-10.{}.0.71".format(sender_asn, sender_asn))
    if paths is None:
        print("Failed to get paths")
        exit(1)
    else:
        paths = paths['paths']

    as_ifid = {}
    brs = {}
    for as_ in topo['ASes']:
        asn = as_['asn']
        brs[asn] = "as{}r-br0-10.{}.0.254".format(asn, asn)

    for asn, container_name in brs.items():
        topology = get_topology(container_name)
        if topology is None:
            print("Failed to get topology")
            exit(1)
        else:
            topology = topology['border_routers']['br0']['interfaces']
        as_ifid[str(asn)] = {}
        for id, interface in topology.items():
            ip = interface['underlay']['public'].split(":")[0]
            iface_name = 'ix{}'.format(ip.split(".")[1])
            as_ifid[str(asn)][id] = iface_name

    paths_links = {}
    path_id = 0
    for path in paths:
        links = []
        ases = []
        i = 1
        for hop in path['hops']:
            if i%2 == 0:
                i = i + 1
                continue
            i = i + 1
            asn = hop['isd_as'].split("-")[1]
            ifid = hop['ifid']
            link_name = as_ifid[asn][str(ifid)]
            links.append(link_name)
            ases.append(asn)
        final_asn = path['hops'][-1]['isd_as'].split("-")[1]
        ases.append(final_asn)
        paths_links[path_id] = {
            "links": links,
            "ases": ases,
            "hops": path['hops'],
            "fingerprint": path['fingerprint']
        }
        path_id = path_id + 1

    # save to json file
    with open('./topo/paths.json', 'w') as f:
        json.dump(paths_links, f, indent=4)

