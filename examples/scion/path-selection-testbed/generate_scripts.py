import json

def get_isd(asn, topo):
    for as_ in topo['ASes']:
        if as_['asn'] == asn:
            return as_['isd']
    return None

def generate_scripts(topo):
    sender_asn = topo["sender_asn"]
    sender_isd = get_isd(sender_asn, topo)
    receiver_asn = topo["receiver_asn"]
    receiver_isd = get_isd(receiver_asn, topo)
    dashboard_asn = topo["dashboard_asn"]
    dashboard_url= f"http://10.{dashboard_asn}.0.71:8050"
    path_selection_url = f"http://10.{sender_asn}.0.71:8010/paths/1_2"
    get_paths_url = f"http://10.{sender_asn}.0.71:8010/get_paths"


    bash_script = '''#!/bin/bash

    echo "starting mosquitto"
    docker exec -d as{}h-h1-10.{}.0.71 /bin/zsh -c "mosquitto > /dev/null 2>&1 &"

    sleep 1

    brs=("as{}r-br0-10.{}.0.254")'''.format(topo["dashboard_asn"], topo["dashboard_asn"], topo["ASes"][0]["asn"], topo["ASes"][0]["asn"])

    # Loop through the ASes and add to the brs array
    for i in range(1, len(topo["ASes"])):
        bash_script += '''
    brs+=("as{}r-br0-10.{}.0.254")'''.format(topo["ASes"][i]["asn"], topo["ASes"][i]["asn"])

    # Add the for loop to start the brs
    bash_script += '''
    for br in "${{brs[@]}}"
    do
        echo "starting $br"
        docker exec -d $br /bin/zsh -c "cd /node && python3 node_control.py > /dev/null 2>&1 &"
    done

    echo "starting dashboard"

    docker exec -d as{}h-h1-10.{}.0.71 /bin/zsh -c "cd /dashboard && python3 dashboard.py > /dev/null 2>&1 &"
    echo "dashboard url: {}"
    '''.format(topo["dashboard_asn"], topo["dashboard_asn"], dashboard_url)

    # Write the bash script to a file
    with open('helper_scripts/start_nodes.sh', 'w') as f:
        f.write(bash_script)

    print("Bash script generated: start_nodes.sh")

    # scripts to enter access sender and receiver

    bash_script = '''#!/bin/bash

    docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh
    '''.format(sender_asn, sender_asn)
    with open('helper_scripts/access_sender.sh', 'w') as f:
        f.write(bash_script)
    print("Bash script generated: access_sender.sh")

    bash_script = '''#!/bin/bash

    docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh
    '''.format(receiver_asn, receiver_asn)
    with open('helper_scripts/access_receiver.sh', 'w') as f:
        f.write(bash_script)
    print("Bash script generated: access_receiver.sh")


# script to start dmtp on the sender and receiver

    bash_script = '''#!/bin/bash

    paths1=$(docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh -c "scion showpaths {}-{}")

    echo "$paths1" | grep -q "no path found"

    # If grep found the string, it will return 0, so we check if the exit code ($?) is 0
    if [ $? -eq 0 ]
    then
    echo "Error: no path found"
    exit 1
    fi
    '''.format(sender_asn, sender_asn, receiver_isd, receiver_asn)

    bash_script += '''paths2=$(docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh -c "scion showpaths {}-{}")

    echo "$paths2" | grep -q "no path found"

    if [ $? -eq 0 ]
    then
    echo "Error: no path found"
    exit 1
    fi
    '''.format(receiver_asn, receiver_asn, sender_isd, sender_asn)

    sender_cont = 'as{}h-h1-10.{}.0.71'.format(sender_asn, sender_asn)
    receiver_cont = 'as{}h-h1-10.{}.0.71'.format(receiver_asn, receiver_asn)

    bash_script += '''echo "starting dmtp server"
    docker exec -d {} /bin/zsh -c "cd /sender && python3 generate_config.py > /dev/null 2>&1 &"
    docker exec -d {} /bin/zsh -c "cd /sender && ./dmtp > /dev/null 2>&1 &"
    sleep 2
    echo "starting dmtp client"
    docker exec -d {} /bin/zsh -c "cd /receiver && python3 generate_config.py > /dev/null 2>&1 &"
    docker exec -d {} /bin/zsh -c "cd /receiver && ./dmtp > /dev/null 2>&1 &"


    sleep 10

    docker exec -it {} /bin/zsh -c "ping 10.72.0.1 -c 1"
    echo "path selection url: {}"
    echo "get paths url: {}"
    '''.format(sender_cont, sender_cont, receiver_cont, receiver_cont, receiver_cont, path_selection_url, get_paths_url)

    # Write the bash script to a file
    with open('helper_scripts/start_dmtp.sh', 'w') as f:
        f.write(bash_script)

    print("Bash script generated: start_dmtp.sh")