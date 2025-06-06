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

def build_paths_links(topo, paths):
    as_ifid = {}
    brs = {}
    for as_ in topo['ASes']:
        asn = as_['asn']
        brs[asn] = "as{}brd-br0-10.{}.0.254".format(asn, asn)

    for asn, container_name in brs.items():
        topology = get_topology(container_name)
        if topology is None:
            print("Failed to get topology")
            exit(1)
        else:
            topology = topology['border_routers']['br0']['interfaces']
        as_ifid[str(asn)] = {}
        for id, interface in topology.items():
            ip = interface['underlay']['local'].split(":")[0]
            iface_name = 'ix{}'.format(ip.split(".")[1])
            as_ifid[str(asn)][id] = iface_name

    paths_links = {}
    path_id = 0
    for path in paths:
        links = []
        ases = []
        i = 1
        for hop in path['hops']:
            if i % 2 == 0:
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
    return paths_links


if __name__ == "__main__":
    topo = json.load(open("../topo/topo.json"))
    client2_asn = topo['client2_asn']
    client2_isd = get_isd(client2_asn, topo)
    client1_asn = topo['client1_asn']
    client1_isd = get_isd(client1_asn, topo)
    server_asn = topo['dashboard_asn']
    server_isd = get_isd(server_asn, topo)

    paths1 = get_paths_from_host(client2_isd, client2_asn, "as{}h-h1-10.{}.0.71".format(server_asn, server_asn))
    if paths1 is None:
        print("Failed to get paths")
        exit(1)
    else:
        paths1 = paths1['paths']

    paths2 = get_paths_from_host(client1_isd, client1_asn, "as{}h-h1-10.{}.0.71".format(server_asn, server_asn))
    if paths2 is None:
        print("Failed to get paths")
        exit(1)
    else:
        paths2 = paths2['paths']

    paths1_links = build_paths_links(topo, paths1)
    paths2_links = build_paths_links(topo, paths2)

    # save to json file
    with open('../topo/paths1.json', 'w') as f:
        json.dump(paths1_links, f, indent=4)
    with open('../topo/paths2.json', 'w') as f:
        json.dump(paths2_links, f, indent=4)

# docker exec as101h-h1-10.101.0.71 /bin/zsh -c "scion showpaths 1-106 --format json -m 100"