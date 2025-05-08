from __future__ import annotations
from seedemu.core import Node, Service, Server, CAServerBase
from typing import Dict, List
import os
from enum import Enum
from seedemu.utilities.BuildtimeDocker import BuildtimeDockerFile, BuildtimeDockerImage

WebServerFileTemplates: Dict[str, str] = {}

WebServerFileTemplates['seed_logo'] = '''\
   SSSSSSSSSSSSSSS EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEDDDDDDDDDDDDD
 SS:::::::::::::::SE::::::::::::::::::::EE::::::::::::::::::::ED::::::::::::DDD
S:::::SSSSSS::::::SE::::::::::::::::::::EE::::::::::::::::::::ED:::::::::::::::DD
S:::::S     SSSSSSSEE::::::EEEEEEEEE::::EEE::::::EEEEEEEEE::::EDDD:::::DDDDD:::::D
S:::::S              E:::::E       EEEEEE  E:::::E       EEEEEE  D:::::D    D:::::D     eeeeeeeeeeee       mmmmmmm    mmmmmmm   uuuuuu    uuuuuu
S:::::S              E:::::E               E:::::E               D:::::D     D:::::D  ee::::::::::::ee   mm:::::::m  m:::::::mm u::::u    u::::u
 S::::SSSS           E::::::EEEEEEEEEE     E::::::EEEEEEEEEE     D:::::D     D:::::D e::::::eeeee:::::eem::::::::::mm::::::::::mu::::u    u::::u
  SS::::::SSSSS      E:::::::::::::::E     E:::::::::::::::E     D:::::D     D:::::De::::::e     e:::::em::::::::::::::::::::::mu::::u    u::::u
    SSS::::::::SS    E:::::::::::::::E     E:::::::::::::::E     D:::::D     D:::::De:::::::eeeee::::::em:::::mmm::::::mmm:::::mu::::u    u::::u
       SSSSSS::::S   E::::::EEEEEEEEEE     E::::::EEEEEEEEEE     D:::::D     D:::::De:::::::::::::::::e m::::m   m::::m   m::::mu::::u    u::::u
            S:::::S  E:::::E               E:::::E               D:::::D     D:::::De::::::eeeeeeeeeee  m::::m   m::::m   m::::mu::::u    u::::u
            S:::::S  E:::::E       EEEEEE  E:::::E       EEEEEE  D:::::D    D:::::D e:::::::e           m::::m   m::::m   m::::mu:::::uuuu:::::u
SSSSSSS     S:::::SEE::::::EEEEEEEE:::::EEE::::::EEEEEEEE:::::EDDD:::::DDDDD:::::D  e::::::::e          m::::m   m::::m   m::::mu:::::::::::::::uu
S::::::SSSSSS:::::SE::::::::::::::::::::EE::::::::::::::::::::ED:::::::::::::::DD    e::::::::eeeeeeee  m::::m   m::::m   m::::m u:::::::::::::::u
S:::::::::::::::SS E::::::::::::::::::::EE::::::::::::::::::::ED::::::::::::DDD       ee:::::::::::::e  m::::m   m::::m   m::::m  uu::::::::uu:::u
 SSSSSSSSSSSSSSS   EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEDDDDDDDDDDDDD            eeeeeeeeeeeeee  mmmmmm   mmmmmm   mmmmmm    uuuuuuuu  uuuu
'''

WebServerFileTemplates['nginx_site'] = '''\
server {{
    {listen_http}
    listen {port};
    {ssl_cert}
    {ssl_proto}
    {ssl_key}
    root /var/www/html;
    index index.html;
    server_name {serverName};
    location / {{
        try_files $uri $uri/ =404;
    }}
}}
'''

WebServerFileTemplates['caddyfile_server_block'] = {
    'listen': [] , # list of ports
    'routes': [] # list of route-objects
    # 'tls_connection_policies'
}

# a route block for 'caddyfile_server_block'
WebServerFileTemplates['caddy_route'] = {
    'match': [],
    'handle': []
}

WebServerFileTemplates['caddyfile_template'] = {'apps': {
    'http':{
        'servers': {
            # list of 'server' objects -> keys are arbitrary i.e. 'www_example_com'
        }
    }
}
}

# 'tls' app block that can be added to 'caddyfile_template'
# when using minica
WebServerFileTemplates['caddy_tls'] = {
    'certificates': {
        'load_files': {
            'certificate': '/path/to/certificates/certs',
            'key': '/path/to/certificates/keys'
        }
    }
}

# 'tls' app block that can be added to 'caddyfile_template'
# when using smallstep ca for automatic cert renewal
WebServerFileTemplates['caddy_tls_automation'] = {
 "automation": {
                "policies": [
                    {
                        "subjects": ["www.example.com"],
                        "issuers": [
                            {
                                "module": "acme",
                                "email": "your-email@example.com"
                            }
                        ],
                        "key_type": "rsa2048",
                        "storage": {
                            "module": "file_system",
                            "keys": "/path/to/certificates/keys",
                            "certificates": "/path/to/certificates/certs"
                        }
                    }
                ]
            }
}

# FIXME: for all this we could just use a dict and them json.dump it ..
WebServerFileTemplates['caddy_file_server'] = '''\
{{
    "apps": {{
        "scion": {{}},
        "http": {{
            "servers": {{
                "{server_block_name}": {{
                    "listen": [{ports}],
                    "routes": [
                        {{
                            "match": [
                                {{
                                    "host": [{domain_names}]
                                }}
                            ],
                            "handle": [
                                {{
                                    "handler": "file_server",
                                    "root": "{path_to_index}",
                                    "index_names": ["index.html"]
                                }}
                            ]
                        }}
                    ]
                }}
            }}
        }}
    }}
}}
'''



# FIXME: for all this we could just use a dict and them json.dump it ..
WebServerFileTemplates['caddy_file_server_https'] = '''\
{{
    "apps": {{
        "scion": {{}},
        "http": {{
            "servers": {{
                "{server_block_name}": {{
                    "listen": [{ports}],
                    "routes": [
                        {{
                            "match": [
                            ],
                            "handle": [
                                {{
                                    "handler": "file_server",
                                    "root": "{path_to_index}",
                                    "index_names": ["index.html"]
                                }}
                            ]
                        }}
                    ],
                    "tls_connection_policies": [
                        {{
                            "certificate_selection": {{
                                "any_tag": ["cert0"]
                            }}
                        }}
                    ]
                }}
            }}
        }},
        "tls": {{
            "certificates": {{
                "load_files": [
                    {{
                        "certificate": "{cert_path}",
                        "key": "{key_path}",
                         "tags": [
                            "cert0"
                        ]
                    }}
                ]
            }}
        }}
    }},
    "logging": {{
        "logs": {{
            "default": {{
                "level": "{loglevel}"
            }}
        }}
    }}
}}
'''

WebServerFileTemplates['caddy_reverse'] = '''\
{{
    "admin": {{
        "disabled": false,
        "listen": "localhost:2020",
        "config": {{
            "persist": false
        }}
    }},
    "apps": {{
        "scion": {{}},
        "http": {{
            "http_port": 7080,
            "https_port": 7443,
            "servers": {{
                "proxy": {{
                    "logs": {{}},
                    "metrics": {{}},
                    "listen": [
                        "scion+single-stream/[{scion_listen_addr}]:7080",
                        "scion+single-stream/[{scion_listen_addr}]:7443",
                        "scion/[{scion_listen_addr}]:8443"
                    ],
                    "automatic_https": {{
                        "disable_redirects": true
                    }},
                    "routes": [
                        {{
                            "match": [
                                {{
                                    "host": [
                                        "localhost",
                                        "whoami.local",
                                        "scion.local",
                                        "ip.local"
                                    ]
                                }}
                            ],
                            "handle": [
                                {{
                                    "handler": "detect_scion"
                                }},
                                {{
                                    "handler": "reverse_proxy",
                                    "upstreams": [
                                        {{
                                            "dial": "localhost:8081"
                                        }}
                                    ],
                                    "handle_response": [
                                        {{
                                            "routes": [
                                                {{
                                                    "handle": [
                                                        {{
                                                            "handler": "copy_response_headers"
                                                        }},
                                                        {{
                                                            "handler": "advertise_scion",
                                                            "Strict-SCION": "17-ffaa:1:1103,192.168.56.1:7443"
                                                        }},
                                                        {{
                                                            "handler": "copy_response"
                                                        }}
                                                    ]
                                                }}
                                            ]
                                        }}
                                    ]
                                }}
                            ]
                        }}
                    ],
                    "listen_protocols": [
                        ["h1", "h2"],
                        ["h1", "h2"],
                        ["h3"]
                    ]
                }}
            }}
        }},
        "pki": {{
            "certificate_authorities": {{
                "local": {{
                    "install_trust": false
                }}
            }}
        }}
    }},
    "logging": {{
        "logs": {{
            "default": {{
                "level": "DEBUG"
            }}
        }}
    }}
}}
'''

WebServerFileTemplates['caddy_reverse_native'] = '''\
{{
    "admin": {{
        "disabled": false,
        "listen": "localhost:2020",
        "config": {{
            "persist": false
        }}
    }},
    "apps": {{
        "scion": {{}},
        "http": {{
            "http_port": 8080,
            "https_port": 8443,
            "servers": {{
                "proxy": {{
                    "logs": {{}},
                    "metrics": {{}},
                    "listen": [
                        "scion/[{scion_listen_addr}]:8443"
                    ],
                    "automatic_https": {{
                        "disable_redirects": true
                    }},
                    "routes": [
                        {{
                            "match": [
                                {{
                                    "host": [
                                        "localhost",
                                        "whoami.local",
                                        "scion.local",
                                        "ip.local"
                                    ]
                                }}
                            ],
                            "handle": [
                                {{
                                    "handler": "detect_scion"
                                }},
                                {{
                                    "handler": "reverse_proxy",
                                    "upstreams": [
                                        {{
                                            "dial": "localhost:8081"
                                        }}
                                    ],
                                    "handle_response": [
                                        {{
                                            "routes": [
                                                {{
                                                    "handle": [
                                                        {{
                                                            "handler": "copy_response_headers"
                                                        }},
                                                        {{
                                                            "handler": "advertise_scion",
                                                            "Strict-SCION": "17-ffaa:1:1103,192.168.56.1:7443"
                                                        }},
                                                        {{
                                                            "handler": "copy_response"
                                                        }}
                                                    ]
                                                }}
                                            ]
                                        }}
                                    ]
                                }}
                            ]
                        }}
                    ],
                    "Protocols": ["h3"]
                }}
            }}
        }},
        "pki": {{
            "certificate_authorities": {{
                "local": {{
                    "install_trust": false
                }}
            }}
        }}
    }},
    "logging": {{
        "logs": {{
            "default": {{
                "level": "DEBUG"
            }}
        }}
    }}
}}
'''

WebServerFileTemplates['caddy_forward'] = '''\
{{
    "admin": {{
        "disabled": true,
        "config": {{
            "persist": false
        }}
    }},
    "apps": {{
        "http": {{
            "http_port": 9080,
            "https_port": 9443,
            "servers": {{
                "forward": {{
                    "logs": {{}},
                    "metrics": {{}},
                    "listen": [
                        ":9080",
                        ":9443"
                    ],
                    "automatic_https": {{
                        "disable_redirects": true
                    }},
                    "routes": [
                        {{
                            "handle": [
                                {
                                    "handler": "forward_proxy",
                                    "hosts": [
                                        "localhost",
                                        "forward-proxy.scion"
                                    ]
                                }
                            ]
                        }}
                    ],
                    "tls_connection_policies": [
                        {{}}
                    ]
                }}
            }}
        }},
        "pki": {{
            "certificate_authorities": {{
                "local": {{
                    "install_trust": false,
                    "storage": {{
                        "module": "file_system",
                        "root": "/usr/share/scion/caddy-scion"
                    }}
                }}
            }}
        }},
        "tls": {{
            "certificates": {{
                "automate": [
                    "localhost",
                    "forward-proxy.scion"
                ]
            }},
            "automation": {{
                "policies": [
                    {{
                        "issuers": [
                            {{
                                "module": "internal"
                            }}
                        ],
                        "storage": {{
                            "module": "file_system",
                            "root": "/usr/share/scion/caddy-scion"
                        }}
                    }}
                ]
            }}
        }}
    }},
    "logging": {{
        "logs": {{
            "default": {{
                "level": "DEBUG"
            }}
        }}
    }}
}}
'''


class CAServerKind(Enum):
    NONE = 0
    MINICA = 1
    SMALLSTEP = 2


    @staticmethod
    def fromCAServer(server: CAServerBase):
        if 'MinicaCertificateAuthority' in server.getClassNames():
            return CAServerKind.MINICA
        elif 'SmallstepCertificateAuthority' in server.getClassNames():
            return CAServerKind.SMALLSTEP
        else:
            raise Exception('unsupported CA service ')


class WebServerKind(Enum):
    NGINX = 0
    CADDY = 1

class WebServerBase(Server):
    """!
    @brief The WebServer class.
    """

    __port: int
    __index: str

    def __init__(self):
        """!
        @brief WebServer constructor.
        """
        super().__init__()
        self.__port = 80
        self._server_name = ['_']
        self.__body = '<pre>{seedlogo}</pre>'.format(seedlogo=WebServerFileTemplates['seed_logo'])
        self.__index = '<h1>{nodeName} at {asn}</h1>{body}'
        self.__enable_https = False
        self.__enable_https_func = None
        self.__ca_server_kind = CAServerKind.NONE

    def _getCAServerKind(self) -> CAServerKind:
        return self.__ca_server_kind

    def getPort(self) -> int:
        return self.__port

    def setPort(self, port: int) -> WebServerBase:
        """!
        @brief Set HTTP port.

        @param port port.

        @returns self, for chaining API calls.
        """
        self.__port = port

        return self

    def getIndexContent(self) -> str:
        return self.__index

    def setIndexContent(self, content: str) -> WebServerBase:
        """!
        @brief Set content of index.html.

        @param content content. {nodeName} and {asn} are available and will be
        filled in.

        @returns self, for chaining API calls.
        """
        self.__index = content

        return self

    def _getRoot(self) -> str:
        """!@brief get path to web root (containing index.html)
        """
        return '/var/www/html/'

    def _installContents(self, node: Node):
        """! installs the static web page contents/files onto the given node
        """
        node.setFile( f'{self._getRoot()}index.html', self.getIndexContent().format(asn = node.getAsn(),
                                                                                    nodeName = node.getName(),
                                                                                    body = self.__body))

    def getServerNames(self) -> List[str]:
        return self._server_name

    def setServerNames(self, serverNames: List[str]) -> WebServerBase:
        """!
        @brief Set server names.

        @param serverNames list of server names.

        @returns self, for chaining API calls.
        """
        self._server_name = serverNames

        return self

    def setCAServer(self, ca: CAServerBase) -> WebServerBase:
        """!
        @brief Get certificates from a particular CA server.

        @param ca CA server.

        @returns self, for chaining API calls.
        """
        self.__enable_https_func = ca.enableHTTPSFunc

        self.__ca_server_kind = CAServerKind.fromCAServer(ca)
        return self

    def enableHTTPS(self) -> WebServerBase:
        """!
        @brief Enable TLS.

        @returns self, for chaining API calls.
        """
        self.__enable_https = True
        return self

    def getHTTPSEnabled(self) -> bool:
        return self.__enable_https

    def _getHTTPSFunc(self):
        return self.__enable_https_func

    def install(self, node: Node, web: WebService):
        """!
        @brief Install the service.
        """
        raise NotImplementedError

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'Web server object.\n'

        return out

class WebService(Service):
    """!
    @brief The WebService class.
    """

    _helper: InstallHelperBase = None

    def __init__(self, kind: WebServerKind = WebServerKind.NGINX):
        """!
        @brief WebService constructor.
        """
        self._kind = kind
        if kind == WebServerKind.CADDY:
            WebService._helper = CaddyHelper()
        super().__init__()
        self.addDependency('Base', False, False)
        self.addDependency('Routing', False, False)

    def getHelper(self) -> InstallHelperBase:
        return self._helper

    def _createServer(self) -> WebServerBase:
        match self._kind:
            case WebServerKind.NGINX:
                return NginxWebServer()
            case WebServerKind.CADDY:
                return CaddyWebServer()

    def getName(self) -> str:
        return 'WebService'

    def _doInstall(self, node: Node, server: WebServerBase):
        server.install(node, self)

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'WebServiceLayer\n'

        return out

class InstallHelperBase:
    def install(self, node: Node, context: str):
        pass

class CaddyHelper(InstallHelperBase):
    """!@brief installs caddy web server with SCION plugin
        @note if you don't want to listen on SCION addresses,
            just don't load the '"scion": {}' app in your caddy config.
    """
    dockerfile: BuildtimeDockerFile
    # container: Container
    out_dir: str = None
    build_path: str
    __seen_nodes: List[Node] = []
    # target-name, url, branch, checkout-dir, do-build
    __dns_urls = [('scion-caddy', 'https://github.com/scionproto-contrib/caddy-scion.git', 'main', '/repos/scion-caddy', True)]

    def getGoBuildImage(self):
        return 'golang:1.24-alpine'

    def __init__(self):
        # create buildtime docker container

        CaddyHelper.build_path = ".caddy_build_output"
        current_dir = os.getcwd()
        output_dir = os.path.join(current_dir, CaddyHelper.build_path)
        CaddyHelper.out_dir = output_dir

        if not os.path.isdir(CaddyHelper.build_path):

            _BUILD_TEMPLATE = f"""FROM {self.getGoBuildImage()}
            RUN apk add --no-cache git
            """

            for target in CaddyHelper.__dns_urls:
                _BUILD_TEMPLATE += f'RUN git clone --branch {target[2]} {target[1]} {target[3]}\n'
                if target[4]:
                    _BUILD_TEMPLATE += f'RUN cd {target[3]} && go mod tidy && CGO_ENABLED=0 go build -a -o bin/ ./cmd/scion-caddy ./cmd/scion-caddy-native ./cmd/scion-caddy-forward ./cmd/scion-caddy-reverse\n'


            CaddyHelper.dockerfile = BuildtimeDockerFile(_BUILD_TEMPLATE)
            CaddyHelper.container = BuildtimeDockerImage(f"caddy-build-container").build(CaddyHelper.dockerfile).container()

            # copy from build container to docker host
            copy_command = []
            for target in CaddyHelper.__dns_urls:
                if target[4]:
                    copy_command.append(f"cp -r {target[3]}/bin/* /build")

            full_cp_cmd = f"-c \"{' && '.join(copy_command)}\""
            CaddyHelper.container.entrypoint("sh").mountVolume(output_dir, "/build").run(
               full_cp_cmd
            )

    def install(self, node: Node, context: str):
        """
        @param context what should be installed on 'node' e.g. 'caddy'

        """
        # mount shared folder with  binaries from docker host to node's container
        if node not in CaddyHelper.__seen_nodes:
            CaddyHelper.__seen_nodes.append(node)
            path_to_binaries = "/bin/caddy"
            node.addSharedFolder(path_to_binaries, CaddyHelper.out_dir)
            node.addDockerCommand(f'ENV PATH={path_to_binaries}:$PATH ')

class CaddyWebServer(WebServerBase):

    def install(self, node: Node, web: WebService):
        """!@brief install and configure caddy web server on the given node
            @details if node is found to be a SCION Node
                    the server will also listen on its SCION address (HTTP/3:8443)
        """
        wh = web.getHelper()
        wh.install(node, 'scion-caddy')


        '''
        CONFIGURATION

        #add the following to /etc/hosts
            1-ff00:0:112,[127.0.0.1] scion.local   # for local setup

            17-ffaa:1:1103,[192.168.56.1] whoami   # for SCIONLab setup
            127.0.0.1 whoami

        # run the backend service
        docker run -p 8081:80 --name whoami --rm --detach traefik/whoami -verbose
        curl localhost:8081 # whoami response over IP

        # run skip-proxy (forward proxy)
        export SCION_DAEMON_ADDRESS="127.0.0.19:30255"; go run ./cmd/scion-caddy run --config ./_examples/forward.json --watch

        # run web-gateway (reverse proxy)
        export SCION_DAEMON_ADDRESS="127.0.0.27:30255"; go run ./cmd/scion-caddy run --config ./_examples/reverse.json --watch



        # test the local setup
        curl -v "http://scion.local:7080" --proxy "https://localhost:9443" --proxy-insecure --proxy-header "Proxy-Authorization: Basic $(echo -n \"policy:\" | base64)"
        curl -v "https://scion.local:7443" --insecure --proxy "https://localhost:9443" --proxy-insecure --proxy-header "Proxy-Authorization: Basic $(echo -n \"policy:\" | base64)"

        # test SCIONLab setup
        curl "http://localhost:8081" -v --insecure --proxy "http://localhost:8890" # HTTP over IP (skip-whoami)

        curl "http://localhost:8080" -v --insecure --proxy "http://localhost:8890" # HTTP over IP (skip-web-whoami)
        curl "https://localhost:8443" -v --insecure --proxy "http://localhost:8890" # HTTPS over IP (skip-web-whoami)

        curl "http://whoami.dev:8080" -v --insecure --proxy "http://localhost:8890" # HTTPS over SCION (skip-web-whoami)
        curl "https://whoami.dev:8443" -v --insecure --proxy "http://localhost:8890" # HTTPS over SCION (skip-web-whoami)
        '''

        # https://caddyserver.com/docs/json/apps/http/

        # https://caddyserver.com/docs/json/apps/http/servers/routes/handle/reverse_proxy/

        # https://caddyserver.com/docs/json/apps/pki/

        # https://caddyserver.com/docs/json/apps/tls/


        path_to_content = self._getRoot()
        config_path = '/etc/caddy/config.json'

        super()._installContents(node)

        shortname = self.getServerNames()[0].replace('.','_') # www.example.com -> www_example_com
        dname = ', '.join( [ f'"{s}"' for s in self.getServerNames()] )


        if self.getHTTPSEnabled():
            key_path = '/etc/ssl/private/caddy.key'
            cert_path = '/etc/ssl/certs/caddy.crt'
            assert (self._getCAServerKind() != CAServerKind.NONE
                    and self._getHTTPSFunc() != None), 'set a CAServer in order to use HTTPS'
            self._getHTTPSFunc()(node = node,
                                 context = 'caddy',
                                 server_names = self.getServerNames(),
                                 dst_cert_path = cert_path,
                                 dst_key_path = key_path)

            match self._getCAServerKind():
                case CAServerKind.MINICA:
                    # ports = f"scion/[{scion_listen_addr}]:8443"
                    node.setFile(config_path, WebServerFileTemplates['caddy_file_server_https'].format(ports=f'":{self.getPort()}", ":443"',
                                                                                     path_to_index=path_to_content,
                                                                                     server_block_name=shortname,
                                                                                     domain_names=dname,
                                                                                     loglevel='DEBUG',
                                                                                     key_path=key_path,
                                                                                     cert_path=cert_path) )
                case CAServerKind.SMALLSTEP:
                    #TODO use caddy tls automation ACME
                    raise NotImplementedError
        else:
            node.setFile(config_path, WebServerFileTemplates['caddy_file_server'].format(ports=f":{self.getPort()}",
                                                                                     path_to_index=path_to_content,
                                                                                     server_block_name=shortname,
                                                                                     domain_names=dname) )

        node.addSoftware('apache2-utils')
        node.appendStartCommand(f'scion-caddy run --config {config_path} 2>&1 | rotatelogs -n 2 /var/log/caddy.log 1M', fork=True)
        node.appendClassName("WebService")


class NginxWebServer(WebServerBase):
    """
    an instance of a nginx web server
    hosting a static web page
    @note currently it is not SCION capable.
        For NextGen Future SCION Internet
        use the Caddy web server instead.
    """

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'Nginx Web server object.\n'

        return out

    def install(self, node: Node, web: WebService):
        """!
        @brief Install the service.
        """
        nginx_conf = '/etc/nginx/sites-available/default'
        key_path = '/etc/ssl/private/nginx.key'
        cert_path = '/etc/ssl/certs/nginx.crt'
        node.addSoftware('nginx-light')
        self._installContents(node)
        node.appendStartCommand('service nginx start')
        node.appendClassName("WebService")
        if self.getHTTPSEnabled():
            assert (self._getCAServerKind() != CAServerKind.NONE
                    and self._getHTTPSFunc() != None), 'set a CAServer in order to use HTTPS'
            self._getHTTPSFunc()(node = node,
                                 context = 'nginx',
                                 server_names = self.getServerNames(),
                                 dst_cert_path = cert_path,
                                 dst_key_path = key_path)
            match self._getCAServerKind():
                case CAServerKind.MINICA:
                    # change nginx config file to use the cert
                    node.setFile(nginx_conf,
                     WebServerFileTemplates['nginx_site'].format(port = f'{self.getPort() if self.getPort() != 80 else 443} ssl',
                                                                 listen_http = f'listen {self.getPort()};',
                                                                 ssl_cert = f'ssl_certificate {cert_path};',
                                                                 ssl_key = f'ssl_certificate_key {key_path};',
                                                                 ssl_proto = 'ssl_protocols TLSv1.2 TLSv1.3;',
                                                                 serverName = ' '.join(self.getServerNames())
                                                                 ))
                case CAServerKind.SMALLSTEP:
                # 'ssl_*' fields are set by certbot with --nginx flag
                    node.setFile(nginx_conf,
                     WebServerFileTemplates['nginx_site'].format(port = self.getPort(),
                                                                 ssl_cert = '',
                                                                 listen_http = '',
                                                                 ssl_proto = '',
                                                                 ssl_key = '',
                                                                 serverName = ' '.join(self.getServerNames())))
        else:
            node.setFile(nginx_conf,
                     WebServerFileTemplates['nginx_site'].format(port = self.getPort(),
                                                                 ssl_cert = '',
                                                                 listen_http = '',
                                                                 ssl_proto = '',
                                                                 ssl_key = '',
                                                                 serverName = ' '.join(self.getServerNames())))
