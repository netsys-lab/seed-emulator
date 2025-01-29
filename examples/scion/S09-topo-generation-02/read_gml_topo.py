#!/usr/bin/env python3

from seedemu.compiler import Docker,Graphviz
from seedemu.core import Emulator
from seedemu.generators import DefaultScionGenerator, CommonRouterForAllIF
from seedemu.generators.providers import GMLDataProvider
from seedemu.layers import ScionBase, ScionRouting, ScionIsd, Scion
from seedemu.layers.Scion import LinkType as ScLinkType
from seedemu.services import *

if __name__=="__main__":


  # Initialize
  emu = Emulator()
  base = ScionBase()

  routing = ScionRouting()
  scion_isd = ScionIsd()
  scion = Scion()

  # real ASN to alias
  # {'33154': 2, '2914': 3, '13030': 4, '3303': 5, '553': 6, '42': 7, '23467': 8,
  # '559': 9, '62454': 10, '1239': 11, '5564': 12, '6939': 13, '3356': 14, '14909': 15}
  terminals= [2,8,10,12,15]
  # coreAS is '14' 
  provider = GMLDataProvider("examples/scion/S07-multicast/tiny_test_sample_multi.gml")

  #  CoreAS is '5'
  #{'8075': 2, '1547': 3, '56857': 4, '6939': 5, '202140': 6, '3356': 7, '31133': 8, '7332': 9,
  #  '2854': 10, '6697': 11, '42': 12, '553': 13, '6453': 14, '3257': 15, '3267': 16, '49487': 17,
  #  '20688': 18, '132692': 19, '60890': 20, '2914': 21, '3303': 22, '50411': 23, '12523': 24,
  #  '20081': 25, '27510': 26, '3327': 27}
  # provider = GMLDataProvider("examples/scion/S07-multicast/test_sample3_multi_new.gml")

  generator = DefaultScionGenerator(provider)
  

  emu.addLayer(base)
  emu.addLayer(routing)
  emu.addLayer(scion_isd)
  emu.addLayer(scion)     


  emu = generator.generate_custom(14, 25,emu)


  reg = emu.getRegistry()
  assert  len(base.getAsns()) == len(provider.getASes())
  print( f'nr of ASes  provider: {len(provider.getASes())} base: {len(base.getAsns())}')
  for asn in base.getAsns():

      _as = base.getAutonomousSystem(asn)
      _as.setBeaconingIntervals('90s', '90s', '90s') # the default is 5s for each

      routers = [ _as.getRouter(r) for r in _as.getRouters() ]


      number_of_hosts = 1
      for i in range(number_of_hosts):
        hname = f'host{asn}_{i}'
        host = _as.createHost(hname)
        for netname in _as.getNetworks():
            net = _as.getNetwork(netname)
            if net.getType() == NetworkType.Local:
               host.joinNetwork(net.getName()) 
               break      

  emu.render()

  # Compilation
  emu.compile(Docker(), './output' )
 # emu.compile(Graphviz(), './out_graph')

