from typing import List
from functools import cmp_to_key
from typing import Optional, Dict, Tuple
from seedemu.core.Scope import *
from seedemu.core.Option import BaseOption, OptionMode

class Customizable(object):

    """!
    @brief something that can be configured by Options
    """
    _config: Dict[str,Tuple[BaseOption,Scope]]

    def __init__(self):  # scope param. actually only for debug/tests  , scope: Scope = None        
        super().__init__()
        self._config = {}
        self._scope = None
    
    def scope(self)-> Scope:
        """!@brief returns a scope that includes only this very customizable instance ,nothing else"""
        # it's only natural for a customizable to know its place in the hierarchy
        if not self._scope: return Scope(ScopeTier.Global) # maybe introduce a ScopeTier.NONE for this...
        else: return self._scope
            

    def getScopedOption(self, key: str, scope: Scope = None) -> Optional[Tuple[BaseOption, Scope]]:
        """! @brief retrieves an option along with the most specific Scope in which it was set.
        """
        if not scope:  scope = self.scope()
        
        if key not in self._config: return None
        
        # fetch the most specific option setting to the requested scope
        for ps in filter(None, Customizable._possible_scopes(scope)):
            for (opt,s ) in self._config[key]:            
                try:
                    # scope has equality-relation on all elements
                    if s==ps: # exact match for this specific scope
                        return opt, s
                    elif ps< s: # but this might not be implemented.. and throw
                        # return fst test scope that is included in a setting
                        return opt,s

                except :
                    pass
            
        return None

    def getOption(self, key: str, scope: Scope = None ) -> Optional[BaseOption]:
        """!@brief Retrieves an option(if set) based on the precedence rules (scoping).
                If not specified the option value for the scope most specific to 'this' customizable 
                will be returned.
                However by explicitly asking for a more general scope, all parent 'handDowns' up to the Global settings
                can be retrieved from any customizable regardless of its scope.
            @note actually each layer that provides options should at least provide global defaults.
            So None will be rare if layer implementation is correct and inherits all settings to all nodes.
        """
        optn = self.getScopedOption(key, scope)
        if optn:
            return optn[0]
        else:
            return None

    def _possible_scopes(scope: Scope) -> List[Scope]:
        possible_scopes = [
            Scope(ScopeTier.Node, scope._node_type, 
                  as_id=scope.asn, node_id=scope._node_id) if scope._node_id and scope._as_id and scope._node_type else None,   # Node-specific + type
            Scope(ScopeTier.Node,node_id=scope._node_id, as_id=scope._as_id) if scope._node_id and scope._as_id else None,   # Node-specific
            Scope(ScopeTier.AS, scope._node_type, as_id=scope._as_id) if scope._as_id and scope._node_type else None,   # AS & Type
            Scope(ScopeTier.AS, ScopeType.ANY, as_id=scope._as_id) if scope._as_id else None,    # AS-wide
            Scope(ScopeTier.Global, scope._node_type),   # Global & Type
            Scope(ScopeTier.Global)                     # Global (fallback)
        ]
        return possible_scopes

    def _getKeys(self) -> List[str]:
        
        return list( self._config.keys())
        
    # Tuple[ BaseOption, Scope ]  or List[ScopedOption] where ScopedOption is just a wrapper around Tuple[BaseOption, Scope]
    def getOptions(self, scope: Scope = None )  -> List[BaseOption]:
        """! @brief return all options included by the given scope.
        """
        return [ self.getOption(k, scope) for k in self._getKeys() ]
    
    def getScopedOptions(self, scope: Scope = None )  -> List[Tuple[BaseOption,Scope]]:
        """! @brief return all options included by the given scope.
        """
        return [ self.getScopedOption(k, scope) for k in self._getKeys() ]    
    
    # this method confines all the scope-related uglyness and spares us to expose get/setOptions() methods
    def handDown(self, child: 'Customizable'):
        """! @brief some Customizables are aggregates and own other Customizables.
            i.e. ASes are a collection of Nodes.
            This methods performs the inheritance of options from parent to child.
        """
        
        try: # scopes could be incomparable
            assert self.scope()>child.scope(), 'logic error - cannot inherit options from more general scopes'
        except :
            pass

        for k, val in self._config.items():
            for (op, s) in val:
                child.setOption(op, s)

    def setOption(self, op: BaseOption, scope: Scope = None ):
        """! @brief set option within the given scope.
            If unspecified the option will be overridden only for "this" Customizable i.e. AS
        """
        # TODO should we add a check here, that scope is of same or higher Tier ?!
        # Everything else would be counterintuitive i.e. setting individual node overrides through the 
        # API of the AS , rather than the respective node's itself

        if not scope:  scope = self.scope()

        if not op.name in self._config: # fst encounter of this option -> no conflict EASY 
            self._config[op.name] = [(op,scope)]
            return
        else: # conflict / or override for another scope

            # keep the list of (scope, opt-val) sorted  ascending (from narrow to broad) by scope
                
            def find_index(lst, key):
            
                for i, element in enumerate(lst):
                    try:
                        if element == key:
                            return i
                    except TypeError:
                        pass  # Skip elements that are truly incomparable
                return -1  # Not found


            def cmp_snd(a, b):
                """Custom comparator for sorting based on the second tuple element."""
                try:
                    if a[1] < b[1]:
                        return -1
                    elif a[1] > b[1]:
                        return 1
                    else:
                        return 0
                except TypeError:
                    return 0 


            # settings for this scope already exist
            if (i:=find_index( [s for _,s in self._config[op.name]], scope)) !=-1:
                # update the option value (change of mind)
                self._config[op.name][i] = (op,scope)
            else: # add the setting for the new scope
                self._config[op.name].append((op,scope))
                res= sorted(self._config[op.name], key=cmp_to_key(cmp_snd) )
                            # key=cmp_to_key(Scope.collate),reverse=True)
                self._config[op.name]  = res
            

    def getRuntimeOptions(self, scope: Scope = None) -> List[BaseOption]:
        return [ o for o in self.getOptions(scope) if o.mode==OptionMode.RUN_TIME]
    
    def getScopedRuntimeOptions(self, scope: Scope = None) -> List[Tuple[BaseOption,Scope]]:
        scopts = self.getScopedOptions(scope)
        return [ (o,s) for o,s in scopts if o.mode==OptionMode.RUN_TIME]
       
if __name__ == "__main__":


    class _Option(BaseOption,Enum):
        # TODO: add CS tracing
        # TODO: add dispatchable port range
        ROTATE_LOGS = "rotate_logs"
        USE_ENVSUBST = "use_envsubst"
        EXPERIMENTAL_SCMP = 'experimental_scmp'
        DISABLE_BFD = 'disable_bfd'
        LOGLEVEL = 'loglevel'
        SERVE_METRICS = 'serve_metrics'
        APPROPRIATE_DIGEST = 'appropriate_digest'
        MAX_BANDWIDTH = 'max_bandwidth'
       
        def __init__(self, key, value=None):
            self._key = key
            #if value==None:
            #    value = self.defaultValue()
            self._mutable_value = value  # Separate mutable storage
            self._mutable_mode = OptionMode.BUILD_TIME

        @property
        def name(self) -> str:
            return self._key

        @property
        def value(self) -> str:
            return self._mutable_value if self._mutable_value else str(self.defaultValue()).lower()

        @value.setter
        def value(self, new_value: str):
            """Allow updating the value attribute."""
            self._mutable_value = new_value

        @property
        def mode(self):
            return self._mutable_mode
        @mode.setter
        def mode(self, new_mode):
            self._mutable_mode = new_mode

        def supportedModes(self) -> OptionMode:
            return OptionMode.BUILD_TIME
        
        #@classmethod
        #def get_default(cls, name):
        #    return getattr(ScionRouting, f"_{name.lower()}", None)

        def defaultValue(self):
            match self._name_:
                case "ROTATE_LOGS": return False
                case "APPROPRIATE_DIGEST": return True
                case "DISABLE_BFD": return True
                case "EXPERIMENTAL_SCMP": return False
                case "LOGLEVEL": return "error"
                case "SERVE_METRICS": return False
                case "USE_ENVSUBST": return False
                case "MAX_BANDWIDTH": return -1

        @classmethod
        def custom(cls, key, value, mode=None ):

            #valid_keys = {member.name for member in cls}
            valid_keys = set()
            for member in cls:
                if isinstance(member.name,str):
                    valid_keys.add(member.name)
            if key not in valid_keys:
                raise ValueError(f"Invalid Option: {key}. Must be one of {valid_keys}.")

            custom_option = object.__new__(cls)
            custom_option._key = key
            custom_option._mutable_value = value
            custom_option._name_ = key.upper()            
            custom_option._mode = mode if mode else OptionMode.BUILD_TIME
            return custom_option

        def __repr__(self):
            return f"Option(key={self._key}, value={self._mutable_value})"

    #----------------------------------------------------------------------
    config = Customizable()

    # Define scopes
    global_scope = Scope(ScopeTier. Global)
    global_router_scope = Scope(ScopeTier. Global, ScopeType.RNODE)
    as_router_scope = Scope(ScopeTier.AS, ScopeType.RNODE, as_id=42)
    node_scope = Scope(ScopeTier.Node, ScopeType.RNODE, node_id="A", as_id=42)
    
    config.setOption( _Option.custom("max_bandwidth", 100), global_scope)
    config.setOption( _Option.custom("max_bandwidth", 200), global_router_scope)
    config.setOption( _Option.custom("max_bandwidth", 400), as_router_scope)
    config.setOption( _Option.custom("max_bandwidth", 500), node_scope)
    
    # Retrieve values using a Scope object
    assert (opt:=config.getOption("max_bandwidth", Scope(ScopeTier.Node, ScopeType.RNODE, node_id="A",as_id=42)))            != None and opt.value==500# 500 (Node-specific)
    assert (opt:=config.getOption("max_bandwidth", Scope(ScopeTier.Node, ScopeType.HNODE, node_id="C", as_id=42)))  != None and opt.value==100# 100 (Global fallback)
    assert (opt:=config.getOption("max_bandwidth", Scope(ScopeTier.Node, ScopeType.RNODE, node_id="D", as_id=99)))  != None and opt.value==200# 200 (Global & Type)
    assert (opt:=config.getOption("max_bandwidth", Scope(ScopeTier.Node, ScopeType.HNODE, node_id="E", as_id=99)))  != None and opt.value==100# 100 (Global-wide)
    assert (opt:=config.getOption("max_bandwidth", Scope(ScopeTier.Node, ScopeType.RNODE, node_id="B", as_id=42))) != None and opt.value==400 # 400 (AS & Type)
    
    child_config = Customizable(node_scope)
    assert not child_config.getOption("max_bandwidth")
    config.handDown(child_config)
    assert (opt:=child_config.getOption("max_bandwidth"))!=None and opt.value==500

    pass