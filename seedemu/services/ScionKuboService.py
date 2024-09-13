from seedemu.core import Node, Service, Server

class ScionKuboServer(Server):
    __address: str

    def __init__(self):
        super().__init__()

    def setAddress(self, address: str):
        self.__address = address

    def install(self, node: Node):
        node.addSoftware('curl git build-essential')
        node.addBuildCommand('curl -O https://dl.google.com/go/go1.22.5.linux-arm64.tar.gz')
        node.addBuildCommand('rm -rf /usr/local/go && tar -C /usr/local -xzf go1.22.5.linux-arm64.tar.gz')
        node.addBuildCommand('git clone --branch feature/scion https://github.com/netsys-lab/kubo.git')
        node.addBuildCommand('export PATH=$PATH:/usr/local/go/bin && cd kubo && make build')

        node.appendStartCommand('/kubo/cmd/ipfs/ipfs init -p test')
        node.appendStartCommand('/kubo/cmd/ipfs/ipfs config --json Addresses.Swarm \'["{}"]\''.format(self.__address))
        node.appendStartCommand('/kubo/cmd/ipfs/ipfs config --json Swarm.Transports.Network \'{"QUIC": false, "SCIONQUIC": true}\'')
        node.appendStartCommand('while true; do /kubo/cmd/ipfs/ipfs daemon --debug; done')

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'ScionKuboServer'
        return out

class ScionKuboService(Service):

    def __init__(self):
        super().__init__()
        self.addDependency('Base', False, False)

    def _createServer(self) -> Server:
        return ScionKuboServer()

    def getName(self) -> str:
        return 'ScionKuboService'

    def print(self, indent: int) -> str:
        out = ' ' * indent
        out += 'ScionKuboService'
        return out
