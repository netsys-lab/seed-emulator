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


class WebServer(Server):
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


    def setPort(self, port: int) -> WebServer:
        """!
        @brief Set HTTP port.

        @param port port.

        @returns self, for chaining API calls.
        """
        self.__port = port

        return self

    def setIndexContent(self, content: str) -> WebServer:
        """!
        @brief Set content of index.html.

        @param content content. {nodeName} and {asn} are available and will be
        filled in.

        @returns self, for chaining API calls.
        """
        self.__index = content

        return self

    def setServerNames(self, serverNames: List[str]) -> WebServer:
        """!
        @brief Set server names.

        @param serverNames list of server names.

        @returns self, for chaining API calls.
        """
        self._server_name = serverNames

        return self

    def setCAServer(self, ca: CAServerBase) -> WebServer:
        """!
        @brief Get certificates from a particular CA server.

        @param ca CA server.

        @returns self, for chaining API calls.
        """
        self.__enable_https_func = ca.enableHTTPSFunc

        self.__ca_server_kind = CAServerKind.fromCAServer(ca)
        return self

    def enableHTTPS(self) -> WebServer:
        """!
        @brief Enable TLS.

        @returns self, for chaining API calls.
        """
        self.__enable_https = True
        return self

    def install(self, node: Node):
        """!
        @brief Install the service.
        """
        nginx_conf = '/etc/nginx/sites-available/default'
        key_path = '/etc/ssl/private/nginx.key'
        cert_path = '/etc/ssl/certs/nginx.crt'
        node.addSoftware('nginx-light')
        node.setFile('/var/www/html/index.html', self.__index.format(asn = node.getAsn(), nodeName = node.getName()))
        node.appendStartCommand('service nginx start')
        node.appendClassName("WebService")
        if self.__enable_https:
            assert (self.__ca_server_kind != CAServerKind.NONE
                    and self.__enable_https_func != None), 'set a CAServer in order to use HTTPS'
            self.__enable_https_func(node=node,
                                     context='nginx',
                                     server_names=self._server_name,
                                     dst_cert_path=cert_path,
                                     dst_key_path=key_path)
            match self.__ca_server_kind:
                case CAServerKind.MINICA:
                    # change nginx config file to use the cert
                    node.setFile(nginx_conf,
                     WebServerFileTemplates['nginx_site'].format(port = f'{self.__port if self.__port != 80 else 443} ssl',
                                                                 listen_http = f'listen {self.__port};',
                                                                 ssl_cert = f'ssl_certificate {cert_path};',
                                                                 ssl_key = f'ssl_certificate_key {key_path};',
                                                                 ssl_proto = 'ssl_protocols TLSv1.2 TLSv1.3;',
                                                                 serverName = ' '.join(self._server_name)
                                                                 ))
                case CAServerKind.SMALLSTEP:
                # 'ssl_*' fields are set by certbot with --nginx flag
                    node.setFile(nginx_conf,
                     WebServerFileTemplates['nginx_site'].format(port = self.__port,
                                                                 ssl_cert = '',
                                                                 listen_http = '',
                                                                 ssl_proto = '',
                                                                 ssl_key = '',
                                                                 serverName = ' '.join(self._server_name)))

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'Web server object.\n'

        return out

class WebService(Service):
    """!
    @brief The WebService class.
    """

    def __init__(self):
        """!
        @brief WebService constructor.
        """
        super().__init__()
        self.addDependency('Base', False, False)
        self.addDependency('Routing', False, False)

    def _createServer(self) -> Server:
        return WebServer()

    def getName(self) -> str:
        return 'WebService'

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'WebServiceLayer\n'

        return out