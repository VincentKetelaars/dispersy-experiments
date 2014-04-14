'''
Created on Apr 7, 2014

@author: Vincent Ketelaars
'''
import time
import signal
import os
import re
from threading import Event, Thread
from errno import EWOULDBLOCK

from src.database.API import get_status, get_config

from src.address import Address
from src.definitions import STATE_DONE, STATE_INITIALIZED, STATE_NOT, STATE_RUNNING, STATE_STOPPED,\
    STATE_RESETTING
from src.api import API
from src.logger import get_logger
from pywifi.wifi.scan import Cell
from pywifi.wifi.scheme import Scheme
from pywifi.wifi.exceptions import InterfaceError

logger = get_logger(__name__)

SLEEP = 1
WIRELESS_QUALITY_GAP_PERCENTAGE = 1.25

class DelftAPI(API):
    '''
    This class will be the bridge between Dispersy / Libswift and the current UAV system.
    Particularly it will monitor the status of the channels on the UAV, using StatusDbReader.
    At the moment this is still pull based, but this could change.
    '''

    STATES = {STATE_DONE : "done", STATE_INITIALIZED : "initialized", STATE_NOT : "none",
              STATE_RUNNING : "running", STATE_STOPPED : "stopped", STATE_RESETTING : "resetting"}

    def __init__(self, stop_event=Event(), name="Network"):
        '''
        @param stop_event: Event that controls the run of this instance, but does not affect this event itself
        @param name: Name of the instance, must reflect the location of configuration parameters
        '''
        name += ".Dispersy"
        
        self.stop_event = stop_event
        
        self.cfg = get_config(name)
        self.status = get_status(name)
        
        di_kwargs = {}
        self.network_configurations = {}
        try:
            di_kwargs, self.network_configurations = self._get_arguments_from_config()
        except:
            logger.exception("Could not get arguments from config, make do with what you've got")
        finally:
            self.cfg.close_connection() # Don't need it anymore!
        
        API.__init__(self, name, **di_kwargs)

        self.status["state"] = self.STATES[self.state]

        self.run_event = Event()
        self.stop_on_dispersy_stop = True
        self._stopping = False
        
        # dictionary of known interfaces that should be used and the last state and time
        self.use_interfaces = {} # (timestamp, status, ip)
        self._listen_args = [Address.unknown(l) for l in di_kwargs.get("listen", [])]
        
        # Set callbacks
        self.state_change_callback(self._state_changed)
        self.swift_state_callback(self._swift_state_changed)
        
        # Set signal quit handler
        signal.signal(signal.SIGQUIT, self.on_quit)
        
        # Remember networks and strengths
        self.network_strengths = {}
        
        # Make sure we don't try to start to many interfaces
        self.starting_interface = False
        
    def run(self):
        logger.info("Running")
        while not self.run_event.is_set() and not self.stop_event.is_set():
            self._monitor_wireless()
            self._parse_iproute()
            self._evaluate_available_networks("wlan0", *self._current_essid_and_quality("wlan0"))
            if not self.stop_event.is_set():
                self.run_event.wait(SLEEP)
        if not self._stopping:
            self.stop()
        logger.debug("Stopped running") 
    
    def stop(self):
        self._stopping = True
        logger.info("Stopping")
        API.stop(self)
        self._stop()
        
    def _stop(self):
        self.run_event.set()
        self.status.kill() # TODO: Perhaps try stop(), doesn't always work
        # Note that stopping status will make the UAV system restart this UAV_API again after some time (within a minute or so)
        
    def on_dispersy_stopped(self):
        logger.debug("Dispersy has stopped")
        self.stop()
        
    def on_quit(self, signal, frame):
        logger.debug("Signaled to quit")
        self.stop()
        
    """
    OVERWRITE
    """
    def interface_came_up(self, ip, interface_name, device_name, gateway=None, port=0):
        """
        If the initial configuration has explicitly mentioned this ip address, then use this port
        """
        for l in self._listen_args:
            if l.ip == ip:
                port = l.port
        API.interface_came_up(self, ip, interface_name, device_name, gateway=gateway, port=port)
        
    """
    CALLBACKS
    """
        
    def _state_changed(self, state):
        self.status["state"] = self.STATES[state]
        
    def _swift_state_changed(self, state, error_code):
        self.status["swift.state"] = self.STATES[state]
        
    def swift_info_callback(self, info):
        regular = info.get("regular")
        base = "swift."
        if regular is not None:
            for k, v in regular.iteritems():
                self.status[base + k] = v
            
        download = info.get("direct")
        if download is None:
            return
        base = "swift.downloads." + download["roothash"] + "."
        for k, v in download.iteritems():
            if k != "moreinfo":
                self.status[base + k] = v
        
        basechannel = "swift.sockets." # Maybe set this to dispersy.endpoint
        (channels, total) = download["moreinfo"]
        for c in channels:
            if_name = self._get_device_by_ip(c["sock_ip"])
            peer_name = c["ip"].replace(".","_") + ":" + str(c["port"])
            if if_name is None:
                addr = Address(ip=c["sock_ip"], port=c["sock_port"])
                addr.resolve_interface()
                if addr.interface is not None:
                    if_name = addr.interface.device
                    self.use_interfaces[if_name] = (time.time(), u"up", c["sock_ip"]) # Insert this interface into the known interfaces
                else:
                    if_name = "unknown"
            for k, v in c.iteritems():
                self.status[basechannel + if_name + "." + peer_name + "." + download["roothash"] + "." + k] = v
        
        for k, v in total.iteritems():
            self.status[base + k] = v
            
    def dispersy_info_callback(self, info):
        base_endpoint = "dispersy.endpoint."
        try:
            me = info["multiendpoint"]
            for e in me:
                name = self._get_interface_by_address(e["address"])
                self.status[base_endpoint + name + ".ip"] = e["address"].ip
                self.status[base_endpoint + name + ".port"] = e["address"].port
                self.status[base_endpoint + name + ".total_up"] = e["total_up"]
                self.status[base_endpoint + name + ".total_down"] = e["total_down"]
                self.status[base_endpoint + name + ".total_send"] = e["total_send"]
        except KeyError:
            pass
            
    def socket_state_callback(self, address, state):
        base = "swift.sockets."
        device = self._get_interface_by_address(address)
        
        if device is None:
            device = "unknown"
        status = u"up" if state in [-1, 0, EWOULDBLOCK] else u"down"
        self.use_interfaces[device] = (time.time(), status, address.ip)
            
        self.status[base + device + ".ip"] = address.ip
        self.status[base + device + ".port"] = address.port
        self.status[base + device + ".state"] = state
        
    def message_received_callback(self, message):
        logger.info("Received message: %s", message)
        
    def bad_swarm_callback(self, filename):
        logger.info("Swift can not handle %s", filename)
    
    """
    PRIVATE FUNCTIONS
    """
    
    def _parse_iproute(self):
        ifs = {}
        iwgetid = os.popen('iwgetid').read()
        for line in iwgetid.splitlines(False):
            device = self._regex_find(line, "ESSID:(.+)", "").strip('"')
            device = device.replace(" ", "_")
            if_name = self._regex_find(line, "(\w+\d)", None)
            ifs[if_name] = device
            self.status["wireless." + device + ".if_name"] = if_name        
        iproute = os.popen('ip route').read()
        for line in iproute.splitlines(False): # There might be multiple lines that correspond
            ip = self._regex_find(line, "src (\d+\.\d+\.\d+\.\d+)", None)
            if_name = self._regex_find(line, "dev ([a-zA-Z]{3,4}\d)", None)
            gateway = self._regex_find(line, "default via (\d+\.\d+\.\d+\.\d+)", None)
            if ip is not None and if_name is not None:
                device = if_name[0:-1]
                if not self._interface_running(device):
                    self.interface_came_up(ip, if_name, device, gateway=gateway)
                    self.use_interfaces[device] = (time.time(), u"up", ip) # Set the newest state
                self.status["dispersy.endpoint." + if_name + ".essid"] = ifs.get(if_name)
                
    def _interface_running(self, device):
        return device in self.use_interfaces.iterkeys() and self.use_interfaces[device][1] == u"up"
        
    def _regex_find(self, _input, _format, default):
        m = re.search(_format, _input, re.IGNORECASE)
        if m:
            return m.groups()[0]
        return default
    
    def _get_interface_by_address(self, address):
        if address.interface is not None:
            return address.interface.name
        return None
    
    def _get_device_by_address(self, address):
        if address.interface is not None and address.interface.device is not None:
            return address.interface.device
        return None              
    
    def _get_device_by_ip(self, ip):
        for i, v in self.use_interfaces.iteritems():
            if v[2] == ip:
                return i[i.rfind('.') + 1:]
        return None
    
    def _get_arguments_from_config(self):
        
        def children(param):
            parameters = []
            try:
                parameters = self.cfg.get(param).get_children()
            except AttributeError:
                logger.exception("Failed to recover %s", param)
            return parameters
        
        def value(value):
            if isinstance(value, unicode):
                return value.encode("ascii", "ignore")
            return value
        
        di_kwargs = {}
        for p in children("parameters"):
            if p.datatype != "folder":
                di_kwargs[value(p.name)] = value(p.get_value())
            else:
                di_kwargs[value(p.name)] = [value(c.get_value()) for c in children("parameters." + value(p.name))]
        
        networks = {}
        for p in children("networks"):
            n_kwargs = {}
            for n in children("networks." + value(p.name)):
                n_kwargs[value(n.name)] = value(n.get_value())
            networks[n_kwargs.get("wireless-essid")] = n_kwargs
            
        return di_kwargs, networks
    
    def _monitor_wireless(self, **kwargs):
        cells = []
        try:
            cells = Cell.all()
        except InterfaceError:
            pass
        for c in cells:
            device = c.ssid.replace(" ", "_")
            quality, maximum = vars(c).get("quality", "-1/-1").split("/")
            info = {"signal" : int(vars(c).get("signal", -1)), "quality" : int(quality),
                    "max_quality" : int(maximum), "encryption_type" : vars(c).get("encryption_type", ""),
                    "channel" : vars(c).get("channel", -1)}
            for k, v in info.iteritems():
                self.status["wireless." + device + "." + k] = v 
            self.network_strengths[device] = info
            
    def _current_essid_and_quality(self, if_name):
        essid = self.status["dispersy.endpoint." + if_name + ".essid"]
        try:
            return essid.get_value(), self.status["wireless." + essid.get_value() + ".quality"].get_value()
        except TypeError:
            pass
        return None, -1
    
    def _evaluate_available_networks(self, if_name, current_essid):
        current = self.network_strengths.get(current_essid, {})
        for essid, value in self.network_strengths.iteritems():
            if value["quality"] > 0 and value["quality"] > current.get("quality", 0) * WIRELESS_QUALITY_GAP_PERCENTAGE:
                logger.debug("%s with quality %d is a better choice than %s with quality %d", 
                             essid, value[1], current_essid, current["quality"])
                if essid in self.network_configurations.keys():
                    if not self.starting_interface:
                        self._start_adhoc_interface(if_name, self.network_configurations.get(essid))                    
                break # TODO: Not taking account multiple better choices
            
    def _start_adhoc_interface(self, if_name, conf):
        """
        # auto IF_NAME
        iface IF_NAME inet static
        address IP
        netmask NETMASK
        # gateway GATEWAY
        wireless-channel CHANNEL
        wireless-essid SSID
        wireless-mode ad-hoc
        wireless-key KEY
        """
#         options = {"address" : ip, "netmask" : netmask, "wireless-channel" : channel, "gateway" : gateway,
#                    "wireless-essid" : ssid, "wireless-mode" : "ad-hoc", "wireless-key" : key}
        
        def run():
            self.starting_interface = True
            scheme = Scheme.find(if_name, conf.get("wireless-essid", None))
            if scheme is not None:
                scheme.delete()
            scheme = Scheme(if_name, conf.get("wireless-essid", None), inet="static", options=conf)
            scheme.save()
            try:
                scheme.activate()
            except:
                logger.exception("Failed to activate wireless network")
            else:
                for k, v in conf.iteritems():
                    self.status["wireless." + conf.get("wireless-essid") + "." + k] = v
                self.status["dispersy.endpoint." + if_name + ".essid"] = conf.get("wireless-essid")
            finally:
                self.starting_interface = False
            
        t = Thread(name="Adhoc", target=run)
        t.start()
                    
if __name__ == "__main__":
    delft = DelftAPI()
    delft.start()