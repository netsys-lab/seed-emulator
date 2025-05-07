from __future__ import annotations
from seedemu.core import Node, Service, Server, CAServerBase
from typing import Dict, List
from enum import Enum

WebServerFileTemplates: Dict[str, str] = {}

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

WebServerFileTemplates['caddy_reverse'] = '''\
{
    "admin": {
        "disabled": false,
        "listen": "localhost:2020",
        "config": {
            "persist": false
        }
    },
    "apps": {
        "scion": {},
        "http": {
            "http_port": 7080,
            "https_port": 7443,
            "servers": {
                "proxy": {
                    "logs": {},
                    "metrics": {},
                    "listen": [
                        "scion+single-stream/[1-ff00:0:112,127.0.0.1]:7080",
                        "scion+single-stream/[1-ff00:0:112,127.0.0.1]:7443",
                        "scion/[1-ff00:0:112,127.0.0.1]:8443"
                    ],
                    "automatic_https": {
                        "disable_redirects": true
                    },
                    "routes": [
                        {
                            "match": [
                                {
                                    "host": [
                                        "localhost",
                                        "whoami.local",
                                        "scion.local",
                                        "ip.local"
                                    ]
                                }
                            ],
                            "handle": [
                                {
                                    "handler": "detect_scion"
                                },
                                {
                                    "handler": "reverse_proxy",
                                    "upstreams": [
                                        {
                                            "dial": "localhost:8081"
                                        }
                                    ],
                                    "handle_response": [
                                        {
                                            "routes": [
                                                {
                                                    "handle": [
                                                        {
                                                            "handler": "copy_response_headers"
                                                        },
                                                        {
                                                            "handler": "advertise_scion",
                                                            "Strict-SCION": "17-ffaa:1:1103,192.168.56.1:7443"
                                                        },
                                                        {
                                                            "handler": "copy_response"
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                    "listen_protocols": [
                        ["h1", "h2"],
                        ["h1", "h2"],
                        ["h3"]
                    ]
                }
            }
        },
        "pki": {
            "certificate_authorities": {
                "local": {
                    "install_trust": false
                }
            }
        }
    },
    "logging": {
        "logs": {
            "default": {
                "level": "DEBUG"
            }
        }
    }
}
'''

WebServerFileTemplates['caddy_reverse_native'] = '''\
{
    "admin": {
        "disabled": false,
        "listen": "localhost:2020",
        "config": {
            "persist": false
        }
    },
    "apps": {
        "scion": {},
        "http": {
            "http_port": 8080,
            "https_port": 8443,
            "servers": {
                "proxy": {
                    "logs": {},
                    "metrics": {},
                    "listen": [
                        "scion/[1-ff00:0:112,127.0.0.1]:8443"
                    ],
                    "automatic_https": {
                        "disable_redirects": true
                    },
                    "routes": [
                        {
                            "match": [
                                {
                                    "host": [
                                        "localhost",
                                        "whoami.local",
                                        "scion.local",
                                        "ip.local"
                                    ]
                                }
                            ],
                            "handle": [
                                {
                                    "handler": "detect_scion"
                                },
                                {
                                    "handler": "reverse_proxy",
                                    "upstreams": [
                                        {
                                            "dial": "localhost:8081"
                                        }
                                    ],
                                    "handle_response": [
                                        {
                                            "routes": [
                                                {
                                                    "handle": [
                                                        {
                                                            "handler": "copy_response_headers"
                                                        },
                                                        {
                                                            "handler": "advertise_scion",
                                                            "Strict-SCION": "17-ffaa:1:1103,192.168.56.1:7443"
                                                        },
                                                        {
                                                            "handler": "copy_response"
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                    "Protocols": ["h3"]
                }
            }
        },
        "pki": {
            "certificate_authorities": {
                "local": {
                    "install_trust": false
                }
            }
        }
    },
    "logging": {
        "logs": {
            "default": {
                "level": "DEBUG"
            }
        }
    }
}
'''

WebServerFileTemplates['caddy_forward'] = '''\
{
    "admin": {
        "disabled": true,
        "config": {
            "persist": false
        }
    },
    "apps": {
        "http": {
            "http_port": 9080,
            "https_port": 9443,
            "servers": {
                "forward": {
                    "logs": {},
                    "metrics": {},
                    "listen": [
                        ":9080",
                        ":9443"
                    ],
                    "automatic_https": {
                        "disable_redirects": true
                    },
                    "routes": [
                        {
                            "handle": [
                                {
                                    "handler": "forward_proxy",
                                    "hosts": [
                                        "localhost",
                                        "forward-proxy.scion"
                                    ]
                                }
                            ]
                        }
                    ],
                    "tls_connection_policies": [
                        {}
                    ]
                }
            }
        },
        "pki": {
            "certificate_authorities": {
                "local": {
                    "install_trust": false,
                    "storage": {
                        "module": "file_system",
                        "root": "/usr/share/scion/caddy-scion"
                    }
                }
            }
        },
        "tls": {
            "certificates": {
                "automate": [
                    "localhost",
                    "forward-proxy.scion"
                ]
            },
            "automation": {
                "policies": [
                    {
                        "issuers": [
                            {
                                "module": "internal"
                            }
                        ],
                        "storage": {
                            "module": "file_system",
                            "root": "/usr/share/scion/caddy-scion"
                        }
                    }
                ]
            }
        }
    },
    "logging": {
        "logs": {
            "default": {
                "level": "DEBUG"
            }
        }
    }
}
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
        self.__index = '<h1>{nodeName} at {asn}</h1>'
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

    def install(self, node: Node):
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

    def __init__(self, kind: WebServerKind = WebServerKind.NGINX):
        """!
        @brief WebService constructor.
        """
        self._kind = kind
        super().__init__()
        self.addDependency('Base', False, False)
        self.addDependency('Routing', False, False)

    def _createServer(self) -> WebServerBase:
        match self._kind:
            case WebServerKind.NGINX:
                return NginxWebServer()
            case WebServerKind.CADDY:
                return CaddyWebServer()

    def getName(self) -> str:
        return 'WebService'

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'WebServiceLayer\n'

        return out

class CaddyWebServer(WebServerBase):

    def install(self, node: Node):

        node.addBuildCommand('curl -o scion-caddy -output-dir /usr/local/bin https://github.com/scionproto-contrib/caddy-scion/releases/download/v0.2.0-beta/scion-caddy-native_linux_x86_64')
        node.addBuildCommand('setcap cap_net_bind_service=+ep /usr/local/bin/scion-caddy')

        '''INSTALLATION
        scioncaddy can be downloaded as releases:
        https://github.com/scionproto-contrib/caddy-scion/releases/download/v0.2.0-beta/scion-caddy-forward_linux_x86_64
        https://github.com/scionproto-contrib/caddy-scion/releases/download/v0.2.0-beta/scion-caddy-native_linux_x86_64
        https://github.com/scionproto-contrib/caddy-scion/releases/download/v0.2.0-beta/scion-caddy-reverse_linux_x86_64

        otherwise the source code is available here:
        https://github.com/scionproto-contrib/caddy-scion.git branch: main
        '''

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

        pass

class NginxWebServer(WebServerBase):

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'Nginx Web server object.\n'

        return out

    def install(self, node: Node):
        """!
        @brief Install the service.
        """
        nginx_conf = '/etc/nginx/sites-available/default'
        key_path = '/etc/ssl/private/nginx.key'
        cert_path = '/etc/ssl/certs/nginx.crt'
        node.addSoftware('nginx-light')
        node.setFile('/var/www/html/index.html', self.getIndexContent().format(asn = node.getAsn(), nodeName = node.getName()))
        node.appendStartCommand('service nginx start')
        node.appendClassName("WebService")
        if self.getHTTPSEnabled():
            assert (self._getCAServerKind() != CAServerKind.NONE
                    and self.__enable_https_func != None), 'set a CAServer in order to use HTTPS'
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
