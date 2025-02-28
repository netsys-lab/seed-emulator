from enum import Flag, auto
from typing import List, Optional, Type, Any



class AutoRegister():

    def __init_subclass__(cls, **kwargs):
        """Automatically register all subclasses upon definition."""

        print(f'{cls.__name__} __init_subclass__')

        from .OptionRegistry import OptionRegistry
        super().__init_subclass__(**kwargs)
        #  Auto-register & create factory method
        OptionRegistry().register(cls)
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

    @classmethod
    def prefix(cls) -> Optional[str]:
        if hasattr(cls, '__prefix'):
            return cls.__prefix
        else:
            return None
    
    @ClassProperty
    def name(cls) -> str:
        # some old code expects a property (no '()' call operator )
        return cls.__name__.lower()

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

    @classmethod
    def supportedModes(cls) -> OptionMode:
        pass

    # def __eq__(self, other: Option):

# simple option
class Option(BaseOption):
    # Immutable class variable to be defined in subclasses
    value_type: Type[Any]
 
    def __init__(self, value: Optional[Any] = None, mode: OptionMode = None):
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
        # Ensure default matches the class-level type
        if value is not None and not isinstance(value, self.value_type):
            raise TypeError(f"Expected {self.value_type.__name__} for '{self.name}', got {type(value).__name__}")

        self._mutable_value = value if value != None else cls.default()
        self._mutable_mode = None
        if not mode in [ OptionMode.BUILD_TIME, None]:
            assert mode in self.supportedModes(), f'unsupported mode for option {key.upper()}'
            self._mutable_mode = mode

    def __repr__(self):
        return f"Option(key={self.name()}, value={self._mutable_value})"
    
    @classmethod
    def getType(cls) -> Type:
        """return this option's value type"""
        return cls.value_type

    @property
    def value(self) -> str:
        if (val := self._mutable_value) != None:
            return val
        else:
            return self.default()
    
    @classmethod
    def default(cls):
        """ default option value if unspecified by user"""
        return None

    @classmethod
    def defaultMode(cls):
        """ default mode if unspecified by user"""
        return OptionMode.BUILD_TIME
    
    @value.setter
    def value(self, new_value: Any):
        """Allow updating the value attribute."""
        if not isinstance(new_value, self.value_type):
            raise TypeError(f"Expected {self.value_type.__name__} for '{self.name}', got {type(new_value).__name__}")
        assert new_value != None, 'Logic Error - option value cannot be None!'
        self._mutable_value = new_value

    @property
    def mode(self):
        if (mode := self._mutable_mode) != None:
            return mode
        else:
            return self.defaultMode()
    
    @mode.setter
    def mode(self, new_mode):
        self._mutable_mode = new_mode

    @classmethod
    def description(cls) -> str:
        return cls.__doc__ or "No documentation available."


# class ScopedOption:
# wrapper around List[Tuple[ BaseOption, Scope ] ]
#  that is an option, that is aware, that it has different values in different scopes




class BaseOptionGroup(BaseComponent , metaclass=OptionGroupMeta):
    _children = {}
    

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