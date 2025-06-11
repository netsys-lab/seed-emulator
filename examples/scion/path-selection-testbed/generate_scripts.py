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
    client1_asn = topo["client1_asn"]
    client2_asn = topo["client2_asn"]
    server_isd = get_isd(topo["dashboard_asn"], topo)
    server_asn = topo["dashboard_asn"]
    dashboard_asn = topo["dashboard_asn"]
    dashboard_url= f"http://localhost:8050"
    get_detailed_paths_url = f"http://localhost:8050/get_paths"

    create_directory("helper_scripts")

    bash_script = '''#!/bin/bash

    echo "starting mosquitto"
    docker exec -d as{}h-h1-10.{}.0.71 /bin/zsh -c "mosquitto > /dev/null 2>&1 &"

    sleep 1

    brs=("as{}brd-br0-10.{}.0.254")'''.format(topo["dashboard_asn"], topo["dashboard_asn"], topo["ASes"][0]["asn"], topo["ASes"][0]["asn"])

    # Loop through the ASes and add to the brs array
    for i in range(1, len(topo["ASes"])):
        bash_script += '''
    brs+=("as{}brd-br0-10.{}.0.254")'''.format(topo["ASes"][i]["asn"], topo["ASes"][i]["asn"])
        

    bash_script += '''
    echo "getting paths"
    python3 ../get_paths.py
    '''

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

    bash_script += '''
    echo -e "\\033[1mLink Properties\\033[0m"
    echo -e "\\n\\033[1mSet Link Properties: POST http://localhost:8050/set_link\\033[0m"
    echo -e "Example Request:"
    echo -e "  curl -X POST \\"http://localhost:8050/set_link\\" -H 'Content-Type: application/json' -d '{{\\"link\\": "ix201", \\"bw\\": 30, \\"latency\\": 10, \\"loss\\": 5}}'\\n"
    echo -e "Response: OK"
    echo "----------------"
    '''

    # Write the bash script to a file
    with open('helper_scripts/start_nodes.sh', 'w') as f:
        f.write(bash_script)

    print("Bash script generated: start_nodes.sh")

    # scripts to enter access server, client1 and client2
    bash_script = '''#!/bin/bash
    docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh
    '''.format(client1_asn, client1_asn)
    with open('helper_scripts/access_client1.sh', 'w') as f:
        f.write(bash_script)
    print("Bash script generated: access_client1.sh")

    bash_script = '''#!/bin/bash
    docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh
    '''.format(client2_asn, client2_asn)
    with open('helper_scripts/access_client2.sh', 'w') as f:
        f.write(bash_script)
    print("Bash script generated: access_client2.sh")

    bash_script = '''#!/bin/bash
    docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh
    '''.format(server_asn, server_asn)
    with open('helper_scripts/access_server.sh', 'w') as f:
        f.write(bash_script)
    print("Bash script generated: access_server.sh")


# script to start wireguard on the server, client1 and client2

    bash_script = '''#!/bin/bash

    paths1=$(docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh -c "scion showpaths {}-{}")

    echo "$paths1" | grep -q "no path found"

    # If grep found the string, it will return 0, so we check if the exit code ($?) is 0
    if [ $? -eq 0 ]
    then
    echo "Error: no path found"
    exit 1
    fi
    '''.format(client1_asn, client1_asn, server_isd, server_asn)

    bash_script += '''paths2=$(docker exec -it as{}h-h1-10.{}.0.71 /bin/zsh -c "scion showpaths {}-{}")

    echo "$paths2" | grep -q "no path found"

    if [ $? -eq 0 ]
    then
    echo "Error: no path found"
    exit 1
    fi
    '''.format(client2_asn, client2_asn, server_isd, server_asn)

    server_cont = 'as{}h-h1-10.{}.0.71'.format(server_asn, server_asn)
    client1_cont = 'as{}h-h1-10.{}.0.71'.format(client1_asn, client1_asn)
    client2_cont = 'as{}h-h1-10.{}.0.71'.format(client2_asn, client2_asn)

    bash_script += '''echo "starting wireguard server"
    docker exec -d {} /bin/zsh -c "cd /wireguard && ./server.sh > /dev/null 2>&1 &"

    sleep 1

    echo "starting wireguard client1"
    docker exec -d {} /bin/zsh -c "cd /wireguard && ./client1.sh > /dev/null 2>&1 &"

    sleep 1

    echo "starting wireguard client2"
    docker exec -d {} /bin/zsh -c "cd /wireguard && ./client2.sh > /dev/null 2>&1 &"

    sleep 1

    docker exec -it {} /bin/zsh -c "ping 10.78.0.1 -c 1"
    docker exec -it {} /bin/zsh -c "ping 10.78.0.1 -c 1"

    echo "Paths API:\n"
    echo "Get all paths: curl -X GET \\"http://localhost:<port>/paths?ia=<ia>\\"\n"

    echo "Set path:\n"
    echo "curl -X POST -H \"Content-Type: application/json\" \
    -d '{{\\"ia\\": \\"<ia>\\", \\"path_index\\": <path_index>}}' \
    \\"http://localhost:28015/path\\""

    echo "Ports: Server: 28015, Client1: 28016, Client2: 28017"
    
    '''.format(server_cont, client1_cont, client2_cont, client1_cont, client2_cont)
    # Write the bash script to a file
    with open('helper_scripts/start_wireguard.sh', 'w') as f:
        f.write(bash_script)

    bash_script = '''#!/bin/bash
    docker exec -d {} /bin/zsh -c "./src/stk-code/cmake_build/bin/supertuxkart --server-config=/server/stk_config.xml --lan-server=scion_supertuxkart --network-demo-mode --track=scotland > /dev/null 2>&1 &"
    '''.format(server_cont)
    # Write the bash script to a file
    with open('helper_scripts/start_stk_server.sh', 'w') as f:
        f.write(bash_script)

    print("Bash script generated: start_wireguard.sh")
    make_files_executable("helper_scripts")
    make_files_executable("server")
    make_files_executable("client1")
    make_files_executable("client2")
    make_files_executable("wireguard")

if __name__ == "__main__":
    topo = json.load(open("topo/topo.json"))
    generate_scripts(topo)