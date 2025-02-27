from typing import Dict, Type


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


'''
# @singleton Decorator for option registry

def singleton(cls):
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
'''

class OptionRegistry(metaclass=SingletonMeta):
    _options: Dict[str, Type['Option']]  = {}

    '''
    _instance = None  # Class-level storage for the single instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    '''

    @classmethod
    def register(cls, option: Type['BaseComponent'], prefix: str = None):
        """Registers an option by name and creates a factory method for it."""

        # if issubclass(option, BaseOptionGroup): return ?!

        opt_name = option.__name__
        if opt_name in ['BaseOption', 'Option', 'BaseComponent', 'BaseOptionGroup'] : return

        cls._options[opt_name] = option
        if prefix != None: prefix += '_'
        else: prefix = ''
        # Dynamically add a factory method to the registry class
        factory_name = f"{prefix}{opt_name.lower()}"
        if not hasattr(cls, factory_name):
            # setattr(cls, factory_name, lambda: option ) # option.__class__()

            setattr(cls, factory_name, lambda **kwargs: cls.create_option(opt_name, **kwargs))

        # also register any children
        if (components := option.components()) != None:
            for c in components:
                cls.register(c, prefix + option.name)

    @classmethod
    def create_option(cls, name: str, **kwargs) -> 'Option':
        """Creates an option instance if it's registered."""
        option_cls = cls._registry.get(name)
        if not option_cls:
            raise ValueError(f"Option '{name}' is not registered.")
        return option_cls(**kwargs)  # Instantiate with given arguments


    @classmethod
    def get(cls, name: str, prefix: str = None) -> Type['BaseComponent']:
        """Retrieves a registered option."""
        if prefix != None:
            name = prefix + '_' + name

        return cls._options.get(name)

    @classmethod
    def list_options(cls):
        """Lists all registered options."""
        return list(cls._options.keys())

# module level singleton instance
# registry = OptionRegistry()
