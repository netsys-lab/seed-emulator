import dash
import dash_cytoscape as cyto
from dash import html
from dash import dcc
import dash_daq as daq
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import paho.mqtt.client as mqtt
from threading import Thread
import json
import requests
import subprocess
import random
from deap import base, creator, tools, algorithms
import numpy


stream1_bw = 16
stream2_bw = 7
stream_latency = 100

############################################################################################

def optimize_paths(paths, links):
    # Define the fitness class loss, jitter, latency, len(shared_links), penalty
    creator.create("FitnessMulti", base.Fitness, weights=(-2.0, -1.0, -1.5, -2.0, -1.0))
    creator.create("Individual", list, fitness=creator.FitnessMulti)

    # Initialize toolbox
    toolbox = base.Toolbox()
    toolbox.register("indices", random.sample, range(len(paths)), 2)
    toolbox.register("individual", tools.initIterate, creator.Individual, toolbox.indices)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    # Define the evaluation function
    def evalPaths(individual):
        path_1_links = paths[individual[0]]['links']
        path_2_links = paths[individual[1]]['links']

        # Calculate properties for path 1
        bw_1 = min([links[link]['bw'] for link in path_1_links])
        latency_1 = sum([links[link]['latency'] for link in path_1_links])
        loss_1 = sum([links[link]['loss'] for link in path_1_links])
        jitter_1 = max([links[link]['jitter'] for link in path_1_links])

        # Calculate properties for path 2
        bw_2 = min([links[link]['bw'] for link in path_2_links])
        latency_2 = sum([links[link]['latency'] for link in path_2_links])
        loss_2 = sum([links[link]['loss'] for link in path_2_links])
        jitter_2 = max([links[link]['jitter'] for link in path_2_links])

        # Calculate number of shared links
        shared_links = list(set(path_1_links) & set(path_2_links))

        # Calculate number of non-shared links
        non_shared_links_1 = list(set(path_1_links) - set(path_2_links))
        non_shared_links_2 = list(set(path_2_links) - set(path_1_links))

        # Define final properties
        loss = loss_1 + loss_2
        jitter = max(jitter_1, jitter_2)
        latency = max(latency_1, latency_2)

        # Calculate bandwidth taking into account the shared and non-shared links
        shared_links_bw = min([links[link]['bw'] for link in shared_links]) if shared_links else float('inf')
        non_shared_links_bw_1 = min([links[link]['bw'] for link in non_shared_links_1]) if non_shared_links_1 else float('inf')
        non_shared_links_bw_2 = min([links[link]['bw'] for link in non_shared_links_2]) if non_shared_links_2 else float('inf')
        bandwidth = min(shared_links_bw, bw_1, bw_2, non_shared_links_bw_1, non_shared_links_bw_2)
        
        # Penalty for not meeting the requirements
        penalty = 0
        if shared_links and shared_links_bw < (stream1_bw+stream2_bw):  # both streams' requirements
            penalty += ((stream1_bw+stream2_bw) - shared_links_bw) * 1000
        if non_shared_links_1 and non_shared_links_bw_1 < stream1_bw:  # stream1's requirement
            penalty += (stream1_bw - non_shared_links_bw_1) * 1000
        if non_shared_links_2 and non_shared_links_bw_2 < stream2_bw:  # stream2's requirement
            penalty += (stream2_bw - non_shared_links_bw_2) * 1000
        if latency > stream_latency:  # Both streams' requirement
            penalty += (latency - stream_latency) * 1000

        return loss, jitter, latency, len(shared_links), penalty

    # Continue with the rest of the toolbox setup
    toolbox.register("evaluate", evalPaths)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=len(paths)-1, indpb=0.1)
    toolbox.register("select", tools.selNSGA2)

    # Initialize population and hall of fame
    pop = toolbox.population(n=50)
    hof = tools.HallOfFame(1)

    # Collect statistics
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", numpy.mean, axis=0)
    stats.register("std", numpy.std, axis=0)
    stats.register("min", numpy.min, axis=0)
    stats.register("max", numpy.max, axis=0)

    # Run the algorithm
    algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=40, stats=stats, halloffame=hof)

    # Return the best pair of paths
    return hof[0]


###########################################################################################

def exec_command(command):
    process = subprocess.run(command, stdout=subprocess.PIPE, shell=True, text=True)
    output = process.stdout.strip()
    return output

command = "ip route | grep net0 | awk '/src/ {print $9}'"
broker_ip = exec_command(command)
parts = broker_ip.split(".")
parts[-1] = "1"
broker_ip = ".".join(parts)
if broker_ip == '':
    print("IP find failed") 
    exit(1)
else:
    print("Broker IP: ", broker_ip)
    
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])

BW_THRESHOLD = 25000

# Initialize the network
network = [
    {'data': {'id': '106', 'label': 'Machine'}, 'position': {'x': 0, 'y': 500}},
    {'data': {'id': '103', 'label': '103'}},
    {'data': {'id': '101', 'label': '101'}, 'position': {'x': 150, 'y': 0}}, 
    {'data': {'id': '102', 'label': '102'}, 'position': {'x': 350, 'y': 10}},
    {'data': {'id': '103', 'label': '103'}, 'position': {'x': 100, 'y': 300}},
    {'data': {'id': '104', 'label': '104'}},
    {'data': {'id': '105', 'label': 'Operator'}, 'position': {'x': 500, 'y': 10}},    
    {'data': {'id':'ix200','source': '101', 'target': '102', 'label': 'ix200', 'bandwidth': 5}}, 
    {'data': {'id':'ix201','source': '101', 'target': '104', 'label': 'ix201', 'bandwidth': 5}},
    {'data': {'id':'ix202','source': '102', 'target': '103', 'label': 'ix202', 'bandwidth': 5}},
    {'data': {'id':'ix203','source': '102', 'target': '104', 'label': 'ix203', 'bandwidth': 5}},
    {'data': {'id':'ix204','source': '101', 'target': '103', 'label': 'ix204', 'bandwidth': 5}},
    {'data': {'id':'ix205','source': '103', 'target': '104', 'label': 'ix205', 'bandwidth': 5}},
    {'data': {'id':'ix206','source': '104', 'target': '105', 'label': 'ix206', 'bandwidth': 5}},
    {'data': {'id':'ix207','source': '106', 'target': '101', 'label': 'ix207', 'bandwidth': 5}},
    {'data': {'id':'ix208','source': '106', 'target': '103', 'label': 'ix208', 'bandwidth': 5}},
    {'data': {'id':'ix209','source': '102', 'target': '105', 'label': 'ix209', 'bandwidth': 5}}, 
]



links = {
    'ix200': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [101, 102], 'paths': [0,4,5]},
    'ix201': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [101, 104], 'paths': [1.6]},
    'ix202': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [102, 103], 'paths': [2,7]},
    'ix203': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [102, 104], 'paths': [4,7,8]},
    'ix204': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [101, 103], 'paths': [5,6]},
    'ix205': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [103, 104], 'paths': [3,8]},
    'ix206': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [104, 105], 'paths': [1,3,4,6,7]},
    'ix207': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [106, 101], 'paths': [0,1,4]},
    'ix208': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [106, 103], 'paths': [2,3,5,6,7,8]},
    'ix209': {'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0, 'ases': [102, 105], 'paths': [0,2,5,8]},
} 

paths = {
    0: {'links': ['ix200', 'ix207', 'ix209'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    1: {'links': ['ix201', 'ix206', 'ix207'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    2: {'links': ['ix202', 'ix208', 'ix209'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    3: {'links': ['ix205', 'ix206', 'ix208'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    4: {'links': ['ix200', 'ix203', 'ix206', 'ix207'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    5: {'links': ['ix200', 'ix204', 'ix208', 'ix209'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    6: {'links': ['ix201', 'ix204', 'ix206', 'ix208'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    7: {'links': ['ix202', 'ix203', 'ix206', 'ix208'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
    8: {'links': ['ix203', 'ix205', 'ix208', 'ix209'], 'bw': 50, 'latency': 2, 'loss': 0.0, 'jitter': 0},
}

links_graph = {
    'ix200': {'bw': 50, 'latency': 2, 'ases': [101, 102]},
    'ix201': {'bw': 50, 'latency': 2, 'ases': [101, 104]},
    'ix202': {'bw': 50, 'latency': 2, 'ases': [102, 103]},
    'ix203': {'bw': 50, 'latency': 2, 'ases': [102, 104]},
    'ix204': {'bw': 50, 'latency': 2, 'ases': [101, 103]},
    'ix205': {'bw': 50, 'latency': 2, 'ases': [103, 104]},
    'ix206': {'bw': 50, 'latency': 2, 'ases': [104, 105]},
    'ix207': {'bw': 50, 'latency': 2, 'ases': [106, 101]},
    'ix208': {'bw': 50, 'latency': 2, 'ases': [106, 103]},
    'ix209': {'bw': 50, 'latency': 2, 'ases': [102, 105]},
}

def calc_path_metrics():
    for path in paths.keys():
        links = paths[path]['links']
        bw = 80000
        latency = 0
        jitter = 0
        loss = 0
        for link in links:
            bw = min(bw, links[link]['bw'])
            latency += links[link]['latency']
            jitter += links[link]['jitter']
            loss += links[link]['loss']
        paths[path]['bw'] = bw
        paths[path]['latency'] = latency
        paths[path]['jitter'] = jitter
        paths[path]['loss'] = loss

deadline = 80
bandwidth = 20

# select two paths that satisfy the deadline and bandwidth requirements with minimum loss and jitter
def get_two_optimal_paths():
    calc_path_metrics()
    optimal_paths = []
    for path in paths.keys():
        if paths[path]['bw'] >= bandwidth and paths[path]['latency'] <= deadline:
            optimal_paths.append(path)
    if len(optimal_paths) == 0:
        return None
    elif len(optimal_paths) == 1:
        return optimal_paths[0]
    else:
        optimal_paths.sort(key=lambda path: paths[path]['loss'])
        return optimal_paths[:2]



    

mqtt_data = ''

slider_links = [link for link in links.keys() if link not in ['ix206', 'ix207', 'ix208', 'ix209']]

bw_sliders = [
    # html.H3('Bandwidth (Mbps)'),
    dbc.Row([
        dbc.Col (html.Label(link), md=1),
        dbc.Col (
            dcc.Slider(
                id=f"{link}-bw",
                min=5,
                max=50,
                step=1,
                value=links[link]['bw'],
                marks={5:{'label':'5',},
                        50:{'label':'50',}},
                tooltip={"placement": "left",'always_visible': True}
            ),
        ),
    ]) for link in slider_links
]

latency_sliders = [
    # html.H3('Latency (ms)'),
    dbc.Row([
        # html.Label(link),
        dcc.Slider(
            id=f"{link}-latency",
            min=5,
            max=500,
            step=5,
            value=links[link]['latency'],
            marks={5:{'label':'5',},
                    500:{'label':'500',}},
            tooltip={"placement": "left",'always_visible': True}
        ),
    ]) for link in slider_links
]

jitter_sliders = [
    # html.H3('Jitter (ms)'),
    dbc.Row([
        # html.Label(link),
        dcc.Slider(
            id=f"{link}-jitter",
            min=0,
            max=30,
            step=1,
            value=links[link]['jitter'],
            marks={0:{'label':'0',},
                    30:{'label':'30',}},
            tooltip={"placement": "left",'always_visible': True}
        ),
    ]) for link in slider_links
]

loss_sliders = [
    # html.H3('Loss (%)'),
    dbc.Row([
        # html.Label(link),
        dcc.Slider(
            id=f"{link}-loss",
            min=0,
            max=10,
            step=0.2,
            value=links[link]['loss'],
            marks={0:{'label':'0',},10:{'label':'10',}},
            tooltip={"placement": "left",'always_visible': True}
        ),
    ]) for link in slider_links
]







# toggle_switch = dcc.Dropdown(
#     id='toggle-switch',
#     options=[
#         {'label': 'SCION', 'value': 'SCION'},
#         {'label': 'BGP', 'value': 'BGP'}
#     ],
#     value='SCION'
# )


for link in slider_links:
    @app.callback(
        Output(f"{link}-bw-output", 'children'),
        [Input(f"{link}-bw", 'value')]
    )
    def send_mqtt_message_bw(value, link=link):
        print(f"{link} {value}")
        links[link]['bw'] = value
        for as_ in links[link]['ases']:
            mqtt_client.publish(f"AS{as_}/control/{link}/bandwidth", f"{value}Mbit")
        trigger_path_selection()
        
    @app.callback(
        Output(f"{link}-latency-output", 'children'),
        [Input(f"{link}-latency", 'value')]
    )   
    def send_mqtt_message_latency(value, link=link):
        print(f"{link} {value}")
        links[link]['latency'] = value
        for as_ in links[link]['ases']:
            mqtt_client.publish(f"AS{as_}/control/{link}/latency", f"{value}ms")
        trigger_path_selection()
    
    @app.callback(
        Output(f"{link}-jitter-output", 'children'),
        [Input(f"{link}-jitter", 'value')]
    )
    def send_mqtt_message_jitter(value, link=link):
        print(f"{link} {value}")
        links[link]['jitter'] = value
        for as_ in links[link]['ases']:
            mqtt_client.publish(f"AS{as_}/control/{link}/jitter", f"{value}ms")
        trigger_path_selection()
    
    @app.callback(
        Output(f"{link}-loss-output", 'children'),
        [Input(f"{link}-loss", 'value')]
    )
    def send_mqtt_message_loss(value, link=link):
        print(f"{link} {value}")
        links[link]['loss'] = value
        for as_ in links[link]['ases']:
            mqtt_client.publish(f"AS{as_}/control/{link}/loss", f"{value}%")
        trigger_path_selection()


@app.callback(
    Output('mode-label', 'children'),
    [Input('mode-toggle-switch', 'value')]
)
def send_mqtt_message_toggle(value):
    print(f"{value}")
    url1 = 'http://10.106.0.71:8010/'
    url2 = 'http://10.105.0.71:8010/'
    mode = 'BGP'
    try:
        print(url1 + 'scion')
        if value == True:
            mode = 'SCION'
            response1 = requests.get(url1 + 'scion')
            response2 = requests.get(url2 + 'scion')
        else :
            response1 = requests.get(url1 + 'bgp')
            response2 = requests.get(url2 + 'bgp')
        print(response1.status_code)
    except Exception as e:
        print(e)
    return f"Mode: {mode}"
    
def trigger_path_selection():
    best_paths = optimize_paths(paths, links)
    print(best_paths)
    url1 = 'http://10.106.0.71:8010/paths/'
    url2 = 'http://10.105.0.71:8010/paths/'
    mode = 'BGP'
    try:        
        response1 = requests.get(url1 + f"{best_paths[0]}_{best_paths[1]}_{best_paths[0]}")
        response2 = requests.get(url2 + f"{best_paths[0]}_{best_paths[1]}_{best_paths[0]}")         
        print(response1.status_code)
    except Exception as e:
        print(e)


hidden_bw = [html.P(id=f"{link}-bw-output")  for link in links]
hidden_latency = [html.P(id=f"{link}-latency-output")  for link in links]
hidden_jitter = [html.P(id=f"{link}-jitter-output")  for link in links]
hidden_loss = [html.P(id=f"{link}-loss-output")  for link in links]
hidden_toggle = html.P(id='toggle-output')
# Dash app layout
app.layout = dbc.Container(
    [          
        html.H3("Network Visualization"),        
        html.Hr(),
        dbc.Row(
            [                
                dbc.Col(
                    html.Div(
                        cyto.Cytoscape(
                            id='cytoscape',
                            elements=network,                            
                            stylesheet=[
                                {
                                    'selector': 'node',
                                    'style': {
                                        'content': 'data(label)',
                                        'background-color': '#0074D9',
                                        'color': '#ffffff',
                                        'text-valign': 'center',
                                        'text-halign': 'center',
                                        'height': '65px',
                                        'width': '65px',
                                        'border-color': '#DDDDDD',
                                        'border-width': '2px'
                                    }
                                },
                                {
                                    'selector': 'edge',
                                    'style': {
                                        'label': 'data(label)',
                                        'width': 'mapData(bandwidth, 1500, 1800000, 1, 10)',
                                        'line-color': 'mapData(bandwidth, 1500, 1800000, blue, red)',
                                        # 'text-margin-y': '-10',  # adjust this value as needed
                                        # 'text-margin-x': '-10',
                                        'text-outline-color': '#FFFFFF',
                                        'text-outline-width': '2px',
                                        'text-background-color': '#FFFFFF',
                                        'text-background-opacity': '0.6',
                                    }
                                },
                                {
                                    'selector': '.red',
                                    'style': {
                                        'line-color': '#FF4136',
                                        'target-arrow-color': '#FF4136'
                                    }
                                },
                                {
                                    'selector': '.blue',
                                    'style': {
                                        'line-color': '#0074D9',
                                        'target-arrow-color': '#0074D9'
                                    }
                                },

                            ],                            
                            layout={
                                'name': 'cose',
                                'idealEdgeLength': 90, 
                            },
                            
                        ),
                    ),
                md=12,
                style={'display': 'flex', 'justifyContent': 'center'},
                ), 
            ],
            align="center",            
        ),
        
                
        dbc.Row(
            [
                dbc.Col(
                    html.H5(
                        'Mode',
                        id='mode-label',                    
                    ),
                ),
                dbc.Col(
                    daq.ToggleSwitch(
                            id='mode-toggle-switch',
                            label='Turn ON SCION',
                            value=False                            
                        ),
                ),
            ],
            align="left",
            justify="center",
            style={'padding': 10, 'flex': 1},
        ),
        
        dbc.Row(
            [
                dbc.Col( html.H5('Bandwidth (Mbps)'), md=3),
                dbc.Col( html.H5('Latency (ms)'),   md=3),
                dbc.Col( html.H5('Jitter (ms)'),    md=3),
                dbc.Col( html.H5('Loss (%)'),       md=3),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col(bw_sliders, md=3),
                # dbc.Col( style={'padding': 3, 'flex': 1}),
                dbc.Col(latency_sliders, md=3),
                # dbc.Col( style={'padding': 3, 'flex': 1}),
                dbc.Col(jitter_sliders, md=3),
                # dbc.Col( style={'padding': 3, 'flex': 1}),
                dbc.Col(loss_sliders, md=3),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col(hidden_toggle),
                dbc.Col(hidden_bw), 
                dbc.Col(hidden_latency),  
                dbc.Col(hidden_jitter),
                dbc.Col(hidden_loss), 
                dcc.Interval(
                    id='interval-component',
                    interval=1*1000,  # in milliseconds
                    n_intervals=0
                ),            
            ]
        ),
       

    ],
    # fluid=True,
    style={'padding': 20, 'flex': 1},
)

@app.callback(
    Output('cytoscape', 'elements'),
    Input('interval-component', 'n_intervals'),
    State('cytoscape', 'elements')
)
def update_graph(val, elements):
    for edge in elements:
        if 'ix' in edge['data']['id']:
            ix = edge['data']['id']
            bw = links_graph[ix]['bw']
            # if bw > BW_THRESHOLD:
            #     edge['classes'] = 'red'
            # else:
            #     edge['classes'] = 'blue'        
            edge['data']['bandwidth'] = bw
    return elements

# @app.callback(
#     Output('mqtt-update', 'children'),
#     [Input('interval-component', 'n_intervals')]
# )
# def update_mqtt_data(n):
#     # This function only exists to be triggered by the Interval component
#     # and cause update_graph to be called when a new MQTT message arrives
#     return mqtt_data


ix_as = {
    'ix207': 'AS106',
    'ix208': 'AS106',
    'ix200': 'AS101',
    'ix206': 'AS104',
    'ix209': 'AS102',
    'ix205': 'AS103',


}

def on_mqtt_message(client, userdata, msg):
    global network
    if 'bandwidth' in msg.topic:
        link = msg.topic.split('/')[3]
        if link in links_graph.keys():
            old_bw = links_graph[link]['bw']
            new_bw = int(msg.payload.decode('utf-8'))
            links_graph[link]['bw'] = new_bw*0.3 + old_bw*0.7

            for ixlink in network:
                if ixlink['data']['id'] == link:
                   ixlink['data']['bandwidth'] = (links_graph[link]['bw']/1000)
            # print(f"{link} {new_bw}")
            # links_graph[link]['bw'] = int(msg.payload.decode('utf-8'))
    


mqtt_client = mqtt.Client()
mqtt_client.connect(broker_ip, 1883, 60)  

mqtt_client.on_message = on_mqtt_message
mqtt_client.subscribe("node/#")

mqtt_thread = Thread(target=mqtt_client.loop_forever)
mqtt_thread.start()

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)
