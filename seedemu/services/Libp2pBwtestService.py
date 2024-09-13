from seedemu.core import Node, Service, Server

class Libp2pBwtestServer(Server):

    def __init__(self):
        super().__init__()

    def install(self, node: Node):
        node.addSoftware('curl git build-essential')
        node.addBuildCommand('curl -O https://dl.google.com/go/go1.22.5.linux-arm64.tar.gz')
        node.addBuildCommand('rm -rf /usr/local/go && tar -C /usr/local -xzf go1.22.5.linux-arm64.tar.gz')
        node.addBuildCommand('git clone --branch feature/scion https://github.com/netsys-lab/go-libp2p.git')
        node.addBuildCommand('export PATH=$PATH:/usr/local/go/bin && cd /go-libp2p/p2p/transport/scionquic/cmd/server && go build main.go')
        node.addBuildCommand('export PATH=$PATH:/usr/local/go/bin && cd /go-libp2p/p2p/transport/scionquic/cmd/client && go build main.go')

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'Libp2pBwtestServer'
        return out

class Libp2pBwtestService(Service):

    def __init__(self):
        super().__init__()
        self.addDependency('Base', False, False)

    def _createServer(self) -> Server:
        return Libp2pBwtestServer()

    def getName(self) -> str:
        return 'Libp2pBwtestService'

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'Libp2pBwtestService'
        return out
