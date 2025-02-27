from enum import Flag, auto
from typing import List, Optional



class AutoRegister():

    def __init_subclass__(cls, **kwargs):
        """Automatically register all subclasses upon definition."""

        print(f'{cls.__name__} __init_subclass__')

        from .OptionRegistry import OptionRegistry
        super().__init_subclass__(**kwargs)
        #instance = cls()  # Create an instance
        #  Auto-register & create factory method
        #OptionRegistry().register(instance)
        OptionRegistry().register(cls)
        # registry.register(instance)  
        '''
        if issubclass(cls, BaseComponent):
            if (children := cls.components()) != None:
                for c in children:
                    OptionRegistry.register(c.name(), cls.name() )
        '''

# makes @property work with @classmethod
class ClassProperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.func(owner)

class BaseComponent(): # metaclass=OptionGroupMeta

    
    @ClassProperty
    #@classmethod
    def name(cls) -> str:
        # some old code expects a property (no '()' call operator )
        return cls.__name__.lower() # self.__class__.__name__

    @classmethod
    def getName(cls) -> str:
        return cls.__name__.lower()
    
    @classmethod
    def components(cls) -> Optional[List['BaseComponent']]:
        return None
    
class OptionMode(Flag):
    BUILD_TIME = auto()  # static/hardcoded (required re-compile to change)
    RUN_TIME = auto()  # i.e. envsubst (required only docker compose stop/start )


class OptionGroupMeta(type): # or BaseComponentMeta ..
    """Metaclass to auto-register nested options within a group."""

    def __new__(cls, name, bases, class_dict):

        print(f'{name} __new__')
        if name.lower() == 'scionstackopts':
            name = 'scion'

        from .OptionRegistry import OptionRegistry
        
        new_cls = super().__new__(cls, name, bases, class_dict)
        # if (cls == OptionGroupMeta): return new_cls
        if BaseComponent in bases or any([ issubclass(b, BaseComponent) for b in bases]):
            new_cls._children = {}

            # Auto-register nested Option classes
            hit = False
            for attr_name, attr_value in class_dict.items():
                if issubclass(type(attr_value), OptionGroupMeta):
                    hit = True
                    #option_instance = attr_value()  # Instantiate option
                    #prefixed_name = f"{name}.{option_instance.get_name()}"
                    #new_cls._options[prefixed_name] = option_instance

                    # prefixed_name = f"{name}_{attr_value.name()}"
                    # better call new_cls.add() # here
                    new_cls._children[attr_value.name] = attr_value
            if hit:
                OptionRegistry().register(new_cls)
        return new_cls

# Actually duplicated with 'Option'
# TODO: make option values typed ! i.e if option is 'bool' and you try to set it to a 'str' value -> exception
class BaseOption(BaseComponent, metaclass=OptionGroupMeta):
    """! a base class for KEY-VALUE pairs representing Settings, Parameters or Feature Flags"""

    

    def __eq__(self, other):
        if not other:
            return False

        if issubclass(other, BaseOption):
            return self.name == other.name
        else:
            raise NotImplementedError

    '''
    @property
    def name(self) -> str:
        """Should return the name of the option."""
        pass
    '''

    @property
    def value(self) -> str:
        """Should return the value of the option."""
        pass

    @value.setter
    def value(self, new_value: str):
        """Should allow setting a new value."""
        pass

    @property
    def mode(self) -> OptionMode:
        """Should return the mode of the option."""
        pass

    @mode.setter
    def mode(self, new_mode: OptionMode):
        pass

    # def defaultValue(self)
    @classmethod
    def supportedModes(cls) -> OptionMode:
        pass

    # def __eq__(self, other: Option):

    # TODO: add description(self)->str: here
    # options really should be self-describing/explanatory


# simple option
class Option(BaseOption):
 
    def __init__(self, value = None, mode: OptionMode = None):
        cls = self.__class__
        key = cls.getName().lower()
        # TODO: ONLY REGISTRY IS ALLOWED TO INSTANTIATE ME !!
        # i.e. caller_name must be 'create_option'
        '''
        import inspect
        caller_frame = inspect.stack()[1]
        caller_name = caller_frame.function
        assert caller_name in valid_keys or caller_name in [ 'getAvailableOptions', '__init__'], 'constructor of ScionRouting.Option is private'
        
        '''

        self._mutable_value = value if value != None else cls.default()
        self._mutable_mode = None
        if not mode in [ OptionMode.BUILD_TIME, None]:
            assert mode in self.supportedModes(), f'unsupported mode for option {key.upper()}'
        self._mutable_mode = mode

    def __repr__(self):
        return f"Option(key={self.name()}, value={self._mutable_value})"
    
    @property
    def value(self) -> str:
        if (val := self._mutable_value) != None:
            return val
        else:
            return self.default()
    
    @classmethod
    def default(cls):
        return None
    
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


# class ScopedOption:
# wrapper around List[Tuple[ BaseOption, Scope ] ]
#  that is an option, that is aware, that it has different values in different scopes




class BaseOptionGroup(BaseComponent , metaclass=OptionGroupMeta):
    _children = {}
    
    '''
    def __new__(cls, name, bases, class_dict):
        from .OptionRegistry import OptionRegistry

        print(f'{name} __new__')
       # OptionRegistry().register(cls)

        new_cls = super().__new__(cls, name, bases, class_dict)
        # if (cls == OptionGroupMeta): return new_cls
        new_cls._children = {}

        # Auto-register nested Option classes
        for attr_name, attr_value in class_dict.items():
            if isinstance(attr_value, type) and issubclass(attr_value, Option):
                #option_instance = attr_value()  # Instantiate option
                #prefixed_name = f"{name}.{option_instance.get_name()}"
                #new_cls._options[prefixed_name] = option_instance

                # prefixed_name = f"{name}_{attr_value.name()}"
                # better call new_cls.add() # here
                new_cls._children[attr_value.name()] = attr_value

        #OptionRegistry().register(cls)
        return new_cls
    '''

    '''
    def __init__(self):
        super().__init__()
        self._children = {}
        self.__class__._children = {}
    '''

    def describe(self) -> str:
        return f"OptionGroup {self.__class__.__name__}:\n" + "\n".join(
            #[f"  - {opt.name}" for opt in self._children] 
            [f"  - {name}" for name,_ in self._children.items()] 
            )
    '''
    def add(self, option: BaseComponent):
        #self._children.append( option )
        self._children[option.name] = [f"  - {opt.name}" for opt in self._children] 

    def get(self, option_name: str) -> Optional[BaseComponent]:
       return self._children.get(option_name, None)
    '''
    
    @classmethod
    def components(cls):
        return [v for _, v in cls._children.items()]
        #return self._children