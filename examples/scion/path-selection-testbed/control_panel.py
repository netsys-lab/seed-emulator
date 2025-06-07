# The device uses ESP8266 and the serial to usb chip used, CH340G, needs the right driver installed
# https://learn.sparkfun.com/tutorials/how-to-install-ch340-drivers/all

import serial
import json
import time
import requests
import logging
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from contextlib import contextmanager


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ControlMode(Enum):
    """Network parameter control modes"""
    LATENCY = "latency"
    BANDWIDTH = "bw"
    JITTER = "jitter"
    LOSS = "loss"


class PathTarget(Enum):
    """Path target clients"""
    CLIENT1 = "client1"
    CLIENT2 = "client2"


@dataclass
class Config:
    """Application configuration"""
    serial_port: str
    baudrate: int
    link_api_url: str
    topo_file: str
    parameter_ranges: Dict[ControlMode, Tuple[int, int]]
    client_ports: Dict[str, int]
    num_faders: int
    fader_change_threshold: int
    link_set_rate_limit: float

    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        """Create Config from dictionary"""
        # Convert string keys to ControlMode enums for parameter_ranges
        ranges = {}
        for mode_str, range_tuple in config_dict.get('parameter_ranges', {}).items():
            try:
                mode = ControlMode(mode_str)
                ranges[mode] = tuple(range_tuple)
            except ValueError:
                logger.warning(f"Unknown control mode: {mode_str}")
        
        config_dict['parameter_ranges'] = ranges
        return cls(**config_dict)
    
    @classmethod
    def load_from_file(cls, config_file: str = "config.json") -> 'Config':
        """Load configuration from JSON file"""
        try:
            with open(config_file) as f:
                config_data = json.load(f)
            return cls.from_dict(config_data)
        except FileNotFoundError:
            logger.info(f"Config file {config_file} not found, using defaults")
            return cls.get_default()
    
    @classmethod
    def get_default(cls) -> 'Config':
        """Get default configuration"""
        return cls(
            serial_port='/dev/ttyUSB0',
            baudrate=115200,
            link_api_url="http://localhost:8050/set_link",
            topo_file="topo/topo.json",
            parameter_ranges={
                ControlMode.LATENCY: (5, 500),
                ControlMode.BANDWIDTH: (5, 50),
                ControlMode.JITTER: (0, 30),
                ControlMode.LOSS: (0, 10)
            },
            client_ports={
                "client1": 28016,
                "client2": 28017
            },
            num_faders=6,
            fader_change_threshold=2,
            link_set_rate_limit=1.0
        )

@dataclass
class LinkMetrics:
    """Link data"""
    bw: int
    latency: int
    jitter: int

class NetworkTopology:
    """Manages network topology data"""
    
    def __init__(self, topo_file: str):
        self.topo_file = topo_file
        self.links: List[str] = []
        self.server_ia: Optional[str] = None
        self._load_topology()
    
    def _load_topology(self) -> None:
        """Load topology from JSON file"""
        try:
            with open(self.topo_file) as f:
                topo = json.load(f)
            
            topo_links = topo.get("links", [])
            topo_links = topo_links[:min(Config.get_default().num_faders, len(topo_links))]
            self.links = [f"ix{link['id']}" for link in topo_links]
            server_asn = topo.get("server_asn")
            server_isd = 0
            for _as in topo.get("ASes", []):
                if _as.get("asn") == server_asn:
                    server_isd = _as.get("isd")
                    break
            if server_isd is None:
                logger.error(f"Server ASN {server_asn} not found in topology")
                raise ValueError(f"Server ASN {server_asn} not found in topology")
            self.server_ia = f"{server_isd}-{server_asn}"
            
            logger.info(f"Loaded {len(self.links)} links from topology")
            logger.info(f"Links: {self.links}")
        except FileNotFoundError:
            logger.error(f"Topology file {self.topo_file} not found")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in topology file: {e}")
            raise
    
    @property
    def num_links(self) -> int:
        """Get number of links"""
        return len(self.links)


class SerialController:
    """Handles serial communication with hardware controller"""
    
    def __init__(self, port: str, baudrate: int, timeout: float = 1.0, max_retries: int = 3, retry_delay: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.serial_conn: Optional[serial.Serial] = None
    
    @contextmanager
    def connection(self):
        """Context manager for serial connection with reconnection logic"""
        retries = 0
        while retries <= self.max_retries:
            try:
                if self.serial_conn and self.serial_conn.is_open:
                    self.serial_conn.close()
                self.serial_conn = serial.Serial(
                    self.port, self.baudrate, timeout=self.timeout
                )
                logger.info(f"Connected to serial port {self.port}")
                yield self
                break
            except serial.SerialException as e:
                retries += 1
                if retries <= self.max_retries:
                    logger.warning(f"Failed to connect to serial port (attempt {retries}/{self.max_retries}): {e}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to connect to serial port after {self.max_retries} attempts: {e}")
                    raise
            finally:
                if self.serial_conn and self.serial_conn.is_open:
                    self.serial_conn.close()
                    logger.info("Serial connection closed")
    
    def read_data(self) -> Optional[Dict[str, Any]]:
        """Read and parse data from serial port"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
        
        try:
            line = self.serial_conn.readline().decode("utf-8").strip()
            if not line:
                return None
            
            return json.loads(line)
        except json.JSONDecodeError:
            logger.debug(f"Invalid JSON received: {line}")
            return None
        except Exception as e:
            logger.error(f"Error reading serial data: {e}")
            return None


class NetworkAPI:
    """Handles API communication for network updates"""
    
    def __init__(self, link_api_url: str, client_ports: Dict[str, int]):
        self.link_api_url = link_api_url
        self.client_ports = client_ports
        self.session = requests.Session()
    
    def update_link(self, link: str, parameter: str, value: int) -> bool:
        """Update a link parameter"""
        payload = {"link": link, parameter: value}
        
        try:
            response = self.session.post(
                self.link_api_url, 
                json=payload, 
                timeout=1
            )
            response.raise_for_status()
            logger.info(f"Updated {link} {parameter} = {value}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to update link: {e}")
            return False
    
    def update_path(self, target: str, dashboard_asn: str, path_index: int) -> bool:
        """Update client path"""
        if target not in self.client_ports:
            logger.error(f"Unknown client target: {target}")
            return False
        
        port = self.client_ports[target]
        url = f"http://localhost:{port}/path"
        payload = {"ia": dashboard_asn, "path_index": path_index}
        
        try:
            response = self.session.post(url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info(f"Updated {target} path to index {path_index}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to update path: {e}")
            return False
    
    def close(self):
        """Close the session"""
        self.session.close()


class LinkController:
    """Main controller logic"""
    
    def __init__(self, config: Config, topology: NetworkTopology, api: NetworkAPI):
        self.config = config
        self.topology = topology
        self.api = api
    
        # Track last fader positions for each mode
        self.last_fader_positions: List[int] = [100] * topology.num_links
        
        self.last_mode: Optional[ControlMode] = None
        self.last_rotary: Optional[int] = None
        self.last_path_target: Optional[PathTarget] = None
        self.link_set_last_times: Dict[str, float] = {
            link: time.time() for link in topology.links
        }
    
    def determine_mode(self, button0: bool, button1: bool) -> ControlMode:
        """Determine control mode from button states"""
        if button0 and button1:
            return ControlMode.LOSS
        elif button0:
            return ControlMode.BANDWIDTH
        elif button1:
            return ControlMode.JITTER
        return ControlMode.LATENCY
    
    def determine_path_target(self, button2: bool, button3: bool) -> Optional[PathTarget]:
        """Determine path target from button states"""
        if button2 and not button3:
            return PathTarget.CLIENT1
        elif button3 and not button2:
            return PathTarget.CLIENT2
        return None
    
    def fader_to_value(self, raw: int, mode: ControlMode) -> int:
        """Convert fader value (0-100) to parameter value"""
        range_ = self.config.parameter_ranges[mode]
        return int(range_[0] + (raw / 100.0) * (range_[1] - range_[0]))
    
    def process_data(self, data: Dict[str, Any]) -> None:
        """Process incoming controller data"""
        # Extract inputs
        buttons = [data.get(f"button{i+1}", 0) for i in range(4)]
        faders = [data.get(f"fader{i+1}", 0) for i in range(self.topology.num_links)]
        rotary = data.get("rotary", 0)

        # Validate inputs
        if not all(isinstance(b, (int, bool)) for b in buttons):
            logger.warning("Invalid button values received")
            return
            
        if not all(isinstance(f, int) and 0 <= f <= 100 for f in faders):
            logger.warning("Invalid fader values received")
            return
            
        if not isinstance(rotary, int) or rotary < 0:
            logger.warning("Invalid rotary value received")
            return
        
        # Determine mode and target
        mode = self.determine_mode(bool(buttons[0]), bool(buttons[1]))
        path_target = self.determine_path_target(bool(buttons[2]), bool(buttons[3]))
        
        now = time.time()
        
        # Handle path updates
        if path_target and (path_target != self.last_path_target or rotary != self.last_rotary):
            self.api.update_path(
                path_target.value, 
                self.topology.server_ia, 
                rotary
            )
            self.last_rotary = rotary
            self.last_path_target = path_target
        
        # Handle fader updates
        if mode != self.last_mode:
            self.last_mode = mode
            logger.info(f"Switched to {mode.value.upper()} mode")
        
        self._process_faders(faders, mode, now)
    
    def _process_faders(self, faders: List[int], mode: ControlMode) -> None:
        """Process fader values"""
        for i, raw in enumerate(faders):
            if i >= len(self.topology.links):
                break
                
            link = self.topology.links[i]
            value = self.fader_to_value(raw, mode)
            last_raw = self.last_fader_positions[i]
            last_time = self.link_set_last_times[link]

            if (abs(raw - last_raw) > self.config.fader_change_threshold and 
                (time.time() - last_time) > self.config.link_set_rate_limit):
                logger.debug(f"Fader moved {link} {last_raw} to {raw}")
                self.last_fader_positions[i] = raw
                self.link_set_last_times[link] = time.time()
                self.api.update_link(link, mode.value, value)                    

def main():
    """Main application entry point"""
    # Load configuration
    config = Config.load_from_file()
    
    # Initialize components
    try:
        topology = NetworkTopology(config.topo_file)
        api = NetworkAPI(config.link_api_url, config.client_ports)
        controller = LinkController(config, topology, api)
        serial_ctrl = SerialController(config.serial_port, config.baudrate)
        
        # Main control loop
        with serial_ctrl.connection():
            logger.info("Network Link Controller started. Press Ctrl+C to exit.")
            
            while True:
                try:
                    data = serial_ctrl.read_data()
                    if data:
                        controller.process_data(data)
                    
                except KeyboardInterrupt:
                    logger.info("Shutdown requested")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
        
    except Exception as e:
        logger.critical(f"Failed to initialize: {e}")
        sys.exit(1)
    finally:
        if 'api' in locals():
            api.close()
        logger.info("Network Link Controller stopped")


if __name__ == "__main__":
    main()