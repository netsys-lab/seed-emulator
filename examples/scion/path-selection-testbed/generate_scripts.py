import json
import os 

def get_isd(asn, topo):
    for as_ in topo['ASes']:
        if as_['asn'] == asn:
            return as_['isd']
    return None

def create_directory(directory_name):
    # Check if the directory exists
    if not os.path.exists(directory_name):
        # Create the directory
        try:
            os.makedirs(directory_name)
            print(f"Directory '{directory_name}' created.")
        except OSError as error:
            print(f"Creation of the directory '{directory_name}' failed. Error: {error}")
    else:
        print(f"Directory '{directory_name}' already exists.")

def make_files_executable(directory_path):
    try:
        # List files in the given directory
        files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
        
        # Loop over each file and change permissions to make it executable
        for file in files:
            if file.endswith(".sh") or file == "dmtp":
                file_path = os.path.join(directory_path, file)
                # Add execute and read write permissions for the owner, group, and others
                os.chmod(file_path, 0o777)
                print(f"Made {file_path} executable.")

    except Exception as e:
        print(f"An error occurred: {e}")


def generate_scripts(topo):
    sender_asn = topo["sender_asn"]
    sender_isd = get_isd(sender_asn, topo)
    receiver_asn = topo["receiver_asn"]
    receiver_isd = get_isd(receiver_asn, topo)
    dashboard_asn = topo["dashboard_asn"]
    dashboard_url= f"http://10.{dashboard_asn}.0.71:8050"
    get_detailed_paths_url = f"http://10.{dashboard_asn}.0.71:8050/get_paths"
    path_selection_url = f"http://10.{sender_asn}.0.71:8010/paths/"
    get_paths_url = f"http://10.{sender_asn}.0.71:8010/get_paths"

    create_directory("helper_scripts")

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
    echo "get detailed path information: {}"   
    '''.format(topo["dashboard_asn"], topo["dashboard_asn"], dashboard_url, get_detailed_paths_url)

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
    
    echo -e "\\033[1mGateway API\\033[0m"
    echo -e "\\033[1mPath selection: GET {}\\033[0m"
    echo -e "Example: curl -X GET \\"{}0_1\\" selects paths 0 and 1\\n"
    echo -e "\\033[1mGet Paths: GET {}\\033[0m\\n"
    '''.format(sender_cont, sender_cont, receiver_cont, receiver_cont, receiver_cont, path_selection_url, path_selection_url, get_detailed_paths_url)

    # start sender and receiver apps
    bash_script += '''
    echo "starting sender app"
    docker exec -d {} /bin/zsh -c "cd /sender && python3 sender.py > /dev/null 2>&1 &"
    echo "starting receiver app"
    docker exec -d {} /bin/zsh -c "cd /receiver && python3 receiver.py > /dev/null 2>&1 &"
    '''.format(sender_cont, receiver_cont)

    bash_script += '''
    echo -e "\\033[1mSender App API\\033[0m"
    echo -e "\\n\\033[1mPOST http://10.{sender_asn}.0.71:5000/send\\033[0m"
    echo "------------------"
    echo -e "Start sending packets to the receiver.\\n"
    echo -e "- Parameters:"
    echo -e "  - rate (float): The rate at which to send packets, in Mbps."
    echo -e "  - duration (int, optional): The duration for which to send packets, in seconds."
    echo -e "  - size (int, optional): The size of data to send, in bytes.\\n"
    echo -e "Example Request:"
    echo -e "  curl -X POST \\"http://10.{sender_asn}.0.71:5000/send\\" -H 'Content-Type: application/json' -d '{{\\"rate\\": 10, \\"duration\\": 3}}'\\n"
    echo -e "Response:"
    echo -e "  {{\\n    \\"status\\": \\"started\\",\\n    \\"rate\\": 10,\\n    \\"duration\\": 30\\n}}"
    echo -e "\\n\\033[1mGET http://10.{sender_asn}.0.71:5000/stats\\033[0m"
    echo "----------------"
    echo -e "Get statistics about the sent packets.\\n"
    echo -e "Example Request:"
    echo -e "  curl -X GET \\"http://10.{sender_asn}.0.71:5000/stats\\"\\n"
    echo -e "Response:"
    echo -e "  {{\\n    \\"bytes_sent\\": 5000000,\\n    \\"elapsed_time\\": 1.2,\\n    \\"goodput_mbps\\": 31,\\n }}"
    echo -e "\\n\\033[1mReceiver App API\\033[0m"
    echo -e "\\n\\033[1mGET http://10.{receiver_asn}.0.71:5002/stats\\033[0m"
    echo "----------------"
    echo -e "Get statistics about the received packets.\\n"
    echo -e "Example Request:"
    echo -e "  curl -X GET \\"http://10.{receiver_asn}.0.71:5002/stats\\"\\n"
    echo -e "Response:"
    echo -e "  {{\\n    \\"goodput_mbps\\": 9.5,\\n    \\"avg_delay_ms\\": 10.5,\\n    \\"median_delay_ms\\": 9.0,\\n    \\"std_dev_delay_ms\\": 2.5,\\n    \\"packet_loss\\": 0.01,\\n    \\"received_packets\\": 300,\\n    \\"received_bytes\\": 3000,\\n    \\"duration\\": 30\\n  }}"
    '''.format(sender_asn=sender_asn, receiver_asn=receiver_asn)


    # Write the bash script to a file
    with open('helper_scripts/start_gateway.sh', 'w') as f:
        f.write(bash_script)

    print("Bash script generated: start_gateway.sh")
    make_files_executable("helper_scripts")
    make_files_executable("sender")
    make_files_executable("receiver")