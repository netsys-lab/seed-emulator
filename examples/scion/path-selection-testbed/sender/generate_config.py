import subprocess
import json
import yaml

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

def main():
    # Replace with the actual command that outputs JSON
    topo = json.load(open("/topo/topo.json"))
    receiver_asn = topo['receiver_asn']
    receiver_isd = get_isd(receiver_asn, topo)
    sender_asn = topo['sender_asn']
    sender_isd = get_isd(sender_asn, topo)
    
    command = 'scion showpaths {}-{} -j -m 100'.format(receiver_isd, receiver_asn)
    output, error, return_code = execute_command(command)

    if return_code == 0:
        try:
            result_dict = json.loads(output)
            print("Loaded JSON to dict")
        except json.JSONDecodeError:
            print("Failed to decode JSON:", output)
    else:
        print("Failed to execute command. Error:", error)
        exit(1)

    paths = result_dict["paths"]
    pathFilters = []
    for path in paths:
        hops = path["hops"]
        prev_hop = ""
        path_seq = ""
        start = True
        for hop in hops:
            if hop["isd_as"] != prev_hop:
                path_seq += f"{hop['isd_as']}#{hop['ifid']}"
                if start:
                    path_seq += " "
                    start = False
                prev_hop = hop["isd_as"]
            elif hop["isd_as"] == prev_hop:
                path_seq += f",{hop['ifid']} "
        pathFilters.append(path_seq)

    config = {
        'scionaddress': '{}-{},[10.{}.0.71]:23000'.format(sender_isd, sender_asn, sender_asn),
        'remotescionaddress': '{}-{},[10.{}.0.71]:23000'.format(receiver_isd, receiver_asn, receiver_asn),
        'packetSize': 1410,
        'pathFilters': pathFilters,
        'mode': 'server',
        'ipaddr': '10.72.0.1/24',
        'remote_ip': '10.72.0.2',
        'tunName': 'dmtpif',
        'tunMTU': 1400,
        'cameraDstPorts': [9000,9002,9004],
        'rtcpDstPort': 8890,
        'deadline': 100,
        'timeOffset': 0,
        'codingRate': 0.2,
        'logLevelConsole': 'info',
        'logLevelFile': 'info',
        'adaptivebw': True,
        'useIP': True,
        'serverIPAddr': '10.{}.0.71:4242'.format(sender_asn),
        'clientIPAddr': '10.{}.0.71:4242'.format(receiver_asn),
        'ifacename1': 'net',
        'ifacename2': 'net',
    }

    with open('config.yaml', 'w') as outfile:
        yaml.dump(config, outfile, default_flow_style=False)
    

if __name__ == "__main__":
    main()


