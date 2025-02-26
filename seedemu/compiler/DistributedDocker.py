# Distributed Docker Compiler is not maintained 

from .Docker import Docker, DockerCompilerFileTemplates
from seedemu.core import Emulator, ScopedRegistry, Node, Network, BaseVolume
from seedemu.core.enums import NodeRole
from typing import Dict
from hashlib import md5
from os import mkdir, chdir, rmdir
from yaml import dump

DistributedDockerCompilerFileTemplates: Dict[str, str] = {}

DistributedDockerCompilerFileTemplates['compose_network_ix_worker'] = """\
    {netId}:
        external:
            name: sim_ix_{netId}
        driver: overlay
        labels:
{labelList}
"""

DistributedDockerCompilerFileTemplates['compose_network_ix_master'] = """\
    {netId}:
        driver: overlay
        ipam:
            config:
                - subnet: {prefix}
        labels:
{labelList}
"""

class DistributedDocker(Docker):
    """!
    @brief The DistributedDocker compiler class.

    DistributedDocker is one of the compiler driver. It compiles the lab to
    docker containers. This compiler will generate one set of containers with
    their docker-compose.yml for each AS, enable you to run the emulator
    distributed. 

    This works by making every IX network overlay network. 
    """

    def __init__(self, namingScheme: str = "as{asn}{role}-{name}-{primaryIp}"):
        """!
        @brief DistributedDocker compiler constructor.

        @param namingScheme (optional) node naming scheme. Available variables
        are: {asn}, {role} (r - router, h - host, rs - route server), {name},
        {primaryIp}
        """
        super().__init__(namingScheme= namingScheme)

    def getName(self) -> str:
        return 'DistributedDocker'

    def __compileIxNetMaster(self, net) -> str:
        (scope, _, _) = net.getRegistryInfo()
        return DistributedDockerCompilerFileTemplates['compose_network_ix_master'].format(
            netId = '{}{}'.format(self._contextToPrefix(scope, 'net'), net.getName()),
            prefix = net.getPrefix(),
            labelList = self._getNetMeta(net)
        )

    def __compileIxNetWorker(self, net) -> str:
        (scope, _, _) = net.getRegistryInfo()
        return DistributedDockerCompilerFileTemplates['compose_network_ix_worker'].format(
            netId = '{}{}'.format(self._contextToPrefix(scope, 'net'), net.getName()),
            labelList = self._getNetMeta(net)
        )

    def _doCompile(self, emulator: Emulator):
        registry = emulator.getRegistry()

        self._groupSoftware(emulator)

        toplevelvolumes = '' 
        if len(topvols := self._getVolumes()) > 0:
            toplevelvolumes += 'volumes:\n'
            #topvols = set(map( lambda vol: TopLvlVolume(vol), pool.getVolumes() ))

            for v in  topvols:
                v.mode = 'toplevel'

            #toplevelvolumes += '\n'.join(map( lambda line: '        ' + line ,dump( topvols ).split('\n') ) ) 

            # sharedFolders/bind mounts do not belong in the top-level volumes section
            for v in [vv  for  vv in topvols if vv.asDict()['type'] == 'volume' ]: 
                toplevelvolumes += '  {}:\n'.format(v.asDict()['source']) # why not 'name'
                lines = dump( v ).rstrip('\n').split('\n')
                toplevelvolumes += '\n'.join( map( lambda x: '        ' if x[0] != 0 
                                                else '        ' + x[1] if x[1] != ''
                                                else '', enumerate(lines ) ) )
                toplevelvolumes += '\n'

        scopes = set()
        for (scope, _, _) in registry.getAll().keys(): scopes.add(scope)

        ix_nets = ''

        for ixnet in ScopedRegistry('ix', registry).getByType('net'):
            ix_nets += self.__compileIxNetWorker(ixnet)

        for scope in scopes:
            mkdir(scope)
            chdir(scope)

            services = ''
            networks = ''

            for ((_scope, type, name), obj) in registry.getAll().items():
                if _scope != scope: continue

                if type == 'rnode':
                    self._log('compiling router node {} for as{}...'.format(name, scope))
                    services += self._compileNode(obj)

                if type == 'hnode':
                    self._log('compiling host node {} for as{}...'.format(name, scope))
                    services += self._compileNode(obj)

                if type == 'rs':
                    self._log('compiling rs node for {}...'.format(name))
                    services += self._compileNode(obj)

                if type == 'snode':
                    self._log('compiling service node {}...'.format(name))
                    services += self._compileNode(obj)

                if type == 'net':
                    self._log('creating network: {}/{}...'.format(scope, name))
                    networks += self.__compileIxNetMaster(obj) if scope == 'ix' else self._compileNet(obj)

            if len(services) > 0 or len(networks) > 0 :
                if scope != 'ix': networks += ix_nets
                self._log('creating docker-compose.yml...'.format(scope, name))
                print(DockerCompilerFileTemplates['compose'].format(
                    services = services,
                    networks = networks,
                    volumes = toplevelvolumes,
                    dummies = self._makeDummies()
                ), file=open('docker-compose.yml', 'w'))

                self._used_images = set()
          
                if scope != 'ix':
                    self.generateEnvFile(scope, f'./{scope}')

            chdir('..')

            if services == '' and networks == '': rmdir(scope)
