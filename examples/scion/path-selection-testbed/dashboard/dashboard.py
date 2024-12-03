import dash
import dash_cytoscape as cyto
from dash import html, dcc
import dash_daq as daq
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State, ALL
import paho.mqtt.client as mqtt
from threading import Thread
import json
import requests
import subprocess
from flask import request, jsonify

# Define constants
MIN_BW = 5
MAX_BW = 50
BW_STEP = 1

MIN_LATENCY = 5
MAX_LATENCY = 500
LATENCY_STEP = 5

MIN_LOSS = 0
MAX_LOSS = 10
LOSS_STEP = 0.2

MIN_JITTER = 0
MAX_JITTER = 30
JITTER_STEP = 1

api_changes_enabled = False

# Load topology data
topo = json.load(open('/topo/topo.json'))
sender_ip = f"10.{topo['sender_asn']}.0.71"
receiver_ip = f"10.{topo['receiver_asn']}.0.71"

try:
    with open('/topo/paths.json', 'r') as f:
        paths_data = json.load(f)
except FileNotFoundError:
    paths_data = {}

# Get broker IP
def exec_command(command):
    process = subprocess.run(command, stdout=subprocess.PIPE, shell=True, text=True)
    return process.stdout.strip()

command = "ip route | grep net0 | awk '/src/ {print $9}'"
broker_ip = exec_command(command)
parts = broker_ip.split(".")
parts[-1] = "1"
broker_ip = ".".join(parts)
if not broker_ip:
    print("IP find failed")
    exit(1)
else:
    print("Broker IP:", broker_ip)

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
server = app.server

sender_asn = topo['sender_asn']
receiver_asn = topo['receiver_asn']
network = []

# Create network elements
for as_ in topo["ASes"]:
    label = f"{as_['isd']}-{as_['label']}"
    if as_['asn'] == sender_asn:
        label = "Sender"
    elif as_['asn'] == receiver_asn:
        label = "Receiver"
    network.append({'data': {'id': f"{as_['asn']}", 'label': label}})

for link in topo['links']:
    link_id = f"ix{link['id']}"
    network.append({
        'data': {
            'id': link_id,
            'source': f"{link['source_asn']}",
            'target': f"{link['dest_asn']}",
            'label': link_id,
            'bandwidth': 5
        }
    })

print(json.dumps(network, indent=4))

# Initialize link parameters
links = {
    f"ix{link['id']}": {
        'bw': 50, 'latency': 5, 'loss': 0.0, 'jitter': 0,
        'ases': [link['source_asn'], link['dest_asn']]
    } for link in topo['links']
}

links_graph = {
    f"ix{link['id']}": {
        'bw': 50, 'ases': [link['source_asn'], link['dest_asn']]
    } for link in topo['links']
}

slider_links = list(links.keys())

# Define sliders using pattern-matching IDs
def create_sliders(metric, min_val, max_val, step):
    return [
        dbc.Row([
            dbc.Col(html.Label(link), md=1),
            dbc.Col(
                dcc.Slider(
                    id={'type': 'slider', 'metric': metric, 'link': link},
                    min=min_val,
                    max=max_val,
                    step=step,
                    value=links[link][metric],
                    marks={
                        min_val: {'label': f'{min_val}'},
                        max_val: {'label': f'{max_val}'}
                    },
                    tooltip={"placement": "left", 'always_visible': True}
                ),
            ),
        ]) for link in slider_links
    ]

bw_sliders = create_sliders('bw', MIN_BW, MAX_BW, BW_STEP)
latency_sliders = create_sliders('latency', MIN_LATENCY, MAX_LATENCY, LATENCY_STEP)
jitter_sliders = create_sliders('jitter', MIN_JITTER, MAX_JITTER, JITTER_STEP)
loss_sliders = create_sliders('loss', MIN_LOSS, MAX_LOSS, LOSS_STEP)



# Define callbacks for sliders
@app.callback(
    Output('dummy-output', 'children'),
    Input({'type': 'slider', 'metric': ALL, 'link': ALL}, 'value'),
    State({'type': 'slider', 'metric': ALL, 'link': ALL}, 'id'),
)
def update_link_parameters(values, ids):
    if api_changes_enabled:
        return ''
    for value, id_ in zip(values, ids):
        link = id_['link']
        metric = id_['metric']
        if links[link][metric] == value:
            continue
        else:
            print(f"Link: {link}, Metric: {metric}, Value: {value}")
            links[link][metric] = value
            unit = {'bw': 'Mbit', 'latency': 'ms', 'jitter': 'ms', 'loss': '%'}
            for as_ in links[link]['ases']:
                mqtt_client.publish(f"AS{as_}/control/{link}/{metric}", f"{value}{unit[metric]}")
    return ''

# Callback for mode toggle switch
@app.callback(
    Output('mode-label', 'children'),
    Input('mode-toggle-switch', 'value')
)
def send_mqtt_message_toggle(value):
    print(f"Toggle Switch Value: {value}")
    url1 = f'http://{sender_ip}:8010/'
    url2 = f'http://{receiver_ip}:8010/'
    mode = 'BGP'
    try:
        if value:
            mode = 'SCION'
            requests.get(url1 + 'scion')
            requests.get(url2 + 'scion')
        else:
            requests.get(url1 + 'bgp')
            requests.get(url2 + 'bgp')
    except Exception as e:
        print(e)
    return f"DMTP Mode: {mode}"

# Update Cytoscape graph
@app.callback(
    Output('cytoscape', 'elements'),
    Input('interval-component', 'n_intervals'),
    State('cytoscape', 'elements')
)
def update_graph(_, elements):
    for edge in elements:
        id = edge['data']['id']
        # check if string
        if isinstance(id, str):
            if 'ix' in edge['data']['id']:
                ix = edge['data']['id']
                bw = links_graph[ix]['bw']
                edge['data']['bandwidth'] = bw
    return elements

# Update slider values based on external changes
@app.callback(
    Output({'type': 'slider', 'metric': ALL, 'link': ALL}, 'value'),
    Input('interval-component', 'n_intervals'),
    State({'type': 'slider', 'metric': ALL, 'link': ALL}, 'id')
)
def update_slider_values(_, ids):
    if not api_changes_enabled:
        return [dash.no_update] * len(ids)
    values = []
    for id_ in ids:
        link = id_['link']
        metric = id_['metric']
        value = links[link][metric]
        values.append(value)
    return values

@app.callback(
    Output('dummy-output-toggle', 'children'),
    Input('api-changes-toggle', 'value')
)
def api_changes_enabled_toggle(value):
    global api_changes_enabled
    api_changes_enabled = value
    return ''

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
                                        'width': 'mapData(bandwidth, 2000, 7000000, 1, 10)',
                                        'line-color': 'mapData(bandwidth, 2000, 7000000, blue, red)',
                                        'text-outline-color': '#FFFFFF',
                                        'text-outline-width': '2px',
                                        'text-background-color': '#FFFFFF',
                                        'text-background-opacity': '0.6',
                                    }
                                },
                            ],
                            layout={'name': 'cose', 'idealEdgeLength': 90},
                        ),
                    ),
                    # md=8,
                    style={'display': 'flex', 'justifyContent': 'center'},
                ),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col(html.H5('DMTP Mode', id='mode-label')),
                dbc.Col(
                    daq.ToggleSwitch(
                        id='mode-toggle-switch',
                        label='Turn ON SCION',
                        value=False
                    ),                    
                ),
                dbc.Col(
                    daq.ToggleSwitch(
                        id='api-changes-toggle',
                        label='Enable Changes via API',
                        value=False
                    ),
                ),

            ],
            align="left",
            justify="center",
            style={'padding': 10},
        ),
        dbc.Row(
            [
                dbc.Col(html.H5('Bandwidth (Mbps)'), md=3),
                dbc.Col(html.H5('Latency (ms)'), md=3),
                dbc.Col(html.H5('Jitter (ms)'), md=3),
                dbc.Col(html.H5('Loss (%)'), md=3),
            ],
            align="center",
        ),
        dbc.Row(
            [
                dbc.Col(bw_sliders, md=3),
                dbc.Col(latency_sliders, md=3),
                dbc.Col(jitter_sliders, md=3),
                dbc.Col(loss_sliders, md=3),
            ],
            align="center",
        ),
        dbc.Row(
            [
                html.Div(id='dummy-output', style={'display': 'none'}),
                html.Div(id='dummy-output-toggle', style={'display': 'none'}),
                dcc.Interval(
                    id='interval-component',
                    interval=1*1000,  # in milliseconds
                    n_intervals=0
                ),
            ]
        ),
    ],
    style={'padding': 20},
)

# Define Flask routes
@server.route('/get_paths', methods=['GET'])
def get_paths_detailed():
    global paths_data, links
    for path_id, path in paths_data.items():
        _links = path['links']
        bw = float('inf')
        latency = 0
        jitter = 0.0
        loss = 0.0
        for link in _links:
            if link in links:
                link_data = links[link]
                bw = min(bw, link_data['bw'])
                latency += link_data['latency']
                jitter += link_data['jitter']
                loss += link_data['loss']
        path['bandwidth_mbps'] = bw
        path['latency_ms'] = latency
        path['jitter_ms'] = jitter
        path['loss_percent'] = loss
    return jsonify(paths_data)

@server.route('/set_link', methods=['POST'])
def set_link():
    global links
    data = request.get_json()
    link = data.get('link')
    if link not in links:
        return 'Link not found', 404
    if not api_changes_enabled:
        return 'API changes disabled', 403

    for metric in ['bw', 'latency', 'jitter', 'loss']:
        if metric in data:
            links[link][metric] = data[metric]
            unit = {'bw': 'Mbit', 'latency': 'ms', 'jitter': 'ms', 'loss': '%'}
            for as_ in links[link]['ases']:
                mqtt_client.publish(f"AS{as_}/control/{link}/{metric}", f"{data[metric]}{unit[metric]}")

    return 'OK', 200

# MQTT message handler
def on_mqtt_message(client, userdata, msg):
    global links_graph
    if 'bandwidth' in msg.topic:
        link = msg.topic.split('/')[3]
        if link in links_graph:
            new_bw = int(msg.payload.decode('utf-8').replace('Mbit', ''))
            links_graph[link]['bw'] = new_bw   

# MQTT client setup
mqtt_client = mqtt.Client()
mqtt_client.connect(broker_ip, 1883, 60)
mqtt_client.on_message = on_mqtt_message
mqtt_client.subscribe("node/#")

mqtt_thread = Thread(target=mqtt_client.loop_forever)
mqtt_thread.start()

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)
