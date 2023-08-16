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


min_bw = 5
max_bw = 50
bw_step = 1

min_latency = 5
max_latency = 500
latency_step = 5

min_loss = 0
max_loss = 10
loss_step = 0.2

min_jitter = 0
max_jitter = 30
jitter_step = 1


# stream1_bw = 6
# stream2_bw = 3
# stream_latency = 95

topo = json.load(open('/topo/topo.json'))
sender_ip = '10.{}.0.71'.format(topo['sender_asn'])
receiver_ip = '10.{}.0.71'.format(topo['receiver_asn'])

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

stream1_time = []
stream1_latency = []
stream1_loss = []
stream1_jitter = []

stream2_time = []
stream2_latency = []
stream2_loss = []
stream2_jitter = []

sender_asn = topo['sender_asn']
receiver_asn = topo['receiver_asn']
network = []

for as_ in topo["ASes"]:
    label = '{}-{}'.format(as_['isd'],as_['label'])
    if as_['asn'] == sender_asn:
        label = "Sender"
    elif as_['asn'] == receiver_asn:
        label = "Receiver"
    data = {
        'data': {'id': as_['asn'], 'label': label}
    }
    network.append(data)

for link in topo['links']:
    id = 'ix{}'.format(link['id'])
    data = {
        'data': {'id': id, 'source': link['source_asn'], 
                 'target': link['dest_asn'], 'label': id, 'bandwidth': 5}
    }
    network.append(data)

links = {}
for link in topo['links']:
    links['ix{}'.format(link['id'])] = {
        'bw': 50, 'latency': 2, 'loss': 0.0, 
        'jitter': 0, 
        'ases': [link['source_asn'], link['dest_asn']]
    }
    
links_graph = {}
for link in topo['links']:
    links_graph['ix{}'.format(link['id'])] = {
        'bw': 50, 'ases': [link['source_asn'], link['dest_asn']]
    }

mqtt_data = ''

slider_links = [link for link in links.keys()]

bw_sliders = [
    # html.H3('Bandwidth (Mbps)'),
    dbc.Row([
        dbc.Col (html.Label(link), md=1),
        dbc.Col (
            dcc.Slider(
                id=f"{link}-bw",
                min=min_bw,
                max=max_bw,
                step=bw_step,
                value=links[link]['bw'],
                marks={min_bw:{'label':'{}'.format(min_bw),},
                        max_bw:{'label':'{}'.format(max_bw),}},
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
            min=min_latency,
            max=max_latency,
            step=latency_step,
            value=links[link]['latency'],
            marks={min_latency:{'label':'{}'.format(min_latency),},
                    max_latency:{'label':'{}'.format(max_latency),}},
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
            min=min_jitter,
            max=max_jitter,
            step=jitter_step,
            value=links[link]['jitter'],
            marks={min_jitter:{'label':'{}'.format(min_jitter),},
                    max_jitter:{'label':'{}'.format(max_jitter),}},
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
            min=min_loss,
            max=max_loss,
            step=loss_step,
            value=links[link]['loss'],
            marks={min_loss:{'label':'{}'.format(min_loss),},max_loss:{'label':'{}'.format(max_loss),}},
            tooltip={"placement": "left",'always_visible': True}
        ),
    ]) for link in slider_links
]



stream1_graphs = [
    dbc.Row(
        dcc.Graph(
            id='stream1-latency', 
            figure={'layout': {'height': 300},},
        )
    ),
    dbc.Row(
        dcc.Graph(
            id='stream1-loss', 
            figure={'layout': {'height': 300},},       
        )
    ),
    dbc.Row(
        dcc.Graph(
            id='stream1-jitter',  
            figure={'layout': {'height': 300},},      
        )
    ),    
]

stream2_graphs = [
    dbc.Row(
        dcc.Graph(
            id='stream2-latency', 
            figure={'layout': {'height': 300},},          
        )
    ),
    dbc.Row(
        dcc.Graph(
            id='stream2-loss',  
            figure={'layout': {'height': 300},},          
        )
    ),
    dbc.Row(
        dcc.Graph(
            id='stream2-jitter', 
            figure={'layout': {'height': 300},},           
        )
    ),    
]

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
        # trigger_path_selection()
        
    @app.callback(
        Output(f"{link}-latency-output", 'children'),
        [Input(f"{link}-latency", 'value')]
    )   
    def send_mqtt_message_latency(value, link=link):
        print(f"{link} {value}")
        links[link]['latency'] = value
        for as_ in links[link]['ases']:
            mqtt_client.publish(f"AS{as_}/control/{link}/latency", f"{value}ms")
        # trigger_path_selection()
    
    @app.callback(
        Output(f"{link}-jitter-output", 'children'),
        [Input(f"{link}-jitter", 'value')]
    )
    def send_mqtt_message_jitter(value, link=link):
        print(f"{link} {value}")
        links[link]['jitter'] = value
        for as_ in links[link]['ases']:
            mqtt_client.publish(f"AS{as_}/control/{link}/jitter", f"{value}ms")
        # trigger_path_selection()
    
    @app.callback(
        Output(f"{link}-loss-output", 'children'),
        [Input(f"{link}-loss", 'value')]
    )
    def send_mqtt_message_loss(value, link=link):
        print(f"{link} {value}")
        links[link]['loss'] = value
        for as_ in links[link]['ases']:
            mqtt_client.publish(f"AS{as_}/control/{link}/loss", f"{value}%")
        # trigger_path_selection()


@app.callback(
    Output('mode-label', 'children'),
    [Input('mode-toggle-switch', 'value')]
)
def send_mqtt_message_toggle(value):
    print(f"{value}")
    url1 = 'http://{}:8010/'.format(sender_ip)
    url2 = 'http://{}:8010/'.format(receiver_ip)
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
    return f"DMTP Mode: {mode}"
    
def trigger_path_selection():
    # best_paths = optimize_paths(paths, links)
    best_paths = [1, 2]
    print(best_paths)
    url1 = 'http://{}:8010/'.format(sender_ip)
    url2 = 'http://{}:8010/'.format(receiver_ip)
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
                                        'width': 'mapData(bandwidth, 2000, 600000, 1, 10)',
                                        'line-color': 'mapData(bandwidth, 2000, 600000, blue, red)',
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
                md=8,
                style={'display': 'flex', 'justifyContent': 'center'},
                ), 
                # dbc.Col(
                    
                #         # html.H3('Stream 1'),
                #         # html.Hr(),
                #         stream1_graphs,
                #         # html.H3('Stream 2'),
                #         # html.Hr(),
                #         # stream2_graphs                       
                # ),
                # dbc.Col(
                    
                #         # html.H3('Stream 1'),
                #         # html.Hr(),
                #         stream2_graphs,
                #         # html.H3('Stream 2'),
                #         # html.Hr(),
                #         # stream2_graphs                       
                # ),                                    
            ],
            align="center",            
        ),
        
                
        dbc.Row(
            [
                dbc.Col(
                    html.H5(
                        'DMTP Mode',
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
            if ix == "ix202":
                print(bw)
    return elements


# update stream graphs
@app.callback(
    Output('stream1-latency', 'figure'),
    Input('interval-component', 'n_intervals'),
)
def update_stream1_latency(val):
    return {
        'data': [
            {'x': stream1_time, 'y': stream1_latency, 'type': 'line', 'name': 'stream1'},
        ],
        'layout': {
            'title': 'Stream 1 Latency',
            'xaxis': {
                'title': 'Time (s)'
            },
            'yaxis': {
                'title': 'Latency (ms)'
            },
            'height' : 300,            
        }
    }

@app.callback(
    Output('stream1-loss', 'figure'),
    Input('interval-component', 'n_intervals'),
)
def update_stream1_loss(val):
    return {
        'data': [
            {'x': stream1_time, 'y': stream1_loss, 'type': 'line', 'name': 'stream1'},
        ],
        'layout': {
            'title': 'Stream 1 Loss',
            'xaxis': {
                'title': 'Time (s)'
            },
            'yaxis': {
                'title': 'Loss (%)'
            },
            'height' : 300,
        }
    }

@app.callback(
    Output('stream1-jitter', 'figure'),
    Input('interval-component', 'n_intervals'),
)
def update_stream1_jitter(val):
    return {
        'data': [
            {'x': stream1_time, 'y': stream1_jitter, 'type': 'line', 'name': 'stream1'},
        ],
        'layout': {
            'title': 'Stream 1 Jitter',
            'xaxis': {
                'title': 'Time (s)'
            },
            'yaxis': {
                'title': 'Jitter (ms)'
            },
            'height' : 300,
        }
    }

@app.callback(
    Output('stream2-latency', 'figure'),
    Input('interval-component', 'n_intervals'),
)
def update_stream2_latency(val):
    return {
        'data': [
            {'x': stream2_time, 'y': stream2_latency, 'type': 'line', 'name': 'stream2'},
        ],
        'layout': {
            'title': 'Stream 2 Latency',
            'xaxis': {
                'title': 'Time (s)'
            },
            'yaxis': {
                'title': 'Latency (ms)'
            },
            'height' : 300,
        }
    }

@app.callback(
    Output('stream2-loss', 'figure'),
    Input('interval-component', 'n_intervals'),
)
def update_stream2_loss(val):
    return {
        'data': [
            {'x': stream2_time, 'y': stream2_loss, 'type': 'line', 'name': 'stream2'},
        ],
        'layout': {
            'title': 'Stream 2 Loss',
            'xaxis': {
                'title': 'Time (s)'
            },
            'yaxis': {
                'title': 'Loss (%)'
            },
            'height' : 300,
        }
    }

@app.callback(
    Output('stream2-jitter', 'figure'),
    Input('interval-component', 'n_intervals'),
)
def update_stream2_jitter(val):
    return {
        'data': [
            {'x': stream2_time, 'y': stream2_jitter, 'type': 'line', 'name': 'stream2'},
        ],
        'layout': {
            'title': 'Stream 2 Jitter',
            'xaxis': {
                'title': 'Time (s)'
            },
            'yaxis': {
                'title': 'Jitter (ms)'
            },
            'height' : 300,
        }
        
    }

def on_mqtt_message(client, userdata, msg):
    global network
    if 'bandwidth' in msg.topic:
        link = msg.topic.split('/')[3]
        if link in links_graph.keys():
            new_bw = int(msg.payload.decode('utf-8'))
            links_graph[link]['bw'] = new_bw
    elif msg.topic == 'node/udp/stream1':
        data = json.loads(msg.payload.decode('utf-8'))
        stream1_time.append(data['time'])
        stream1_latency.append(data['latency']*1000)
        stream1_loss.append(data['loss'])
        stream1_jitter.append(data['jitter']*1000)
    elif msg.topic == 'node/udp/stream2':
        data = json.loads(msg.payload.decode('utf-8'))
        stream2_time.append(data['time'])
        stream2_latency.append(data['latency']*1000)
        stream2_loss.append(data['loss'])
        stream2_jitter.append(data['jitter']*1000)

mqtt_client = mqtt.Client()
mqtt_client.connect(broker_ip, 1883, 60)  

mqtt_client.on_message = on_mqtt_message
mqtt_client.subscribe("node/#")

mqtt_thread = Thread(target=mqtt_client.loop_forever)
mqtt_thread.start()

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)
