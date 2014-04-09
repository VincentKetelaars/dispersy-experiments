'''
Created on Apr 7, 2014

@author: Vincent Ketelaars
'''
import time
import signal
import os
import re
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from threading import Event
from errno import EWOULDBLOCK

from src.database.API import get_status, get_config

from src.address import Address
from src.definitions import STATE_DONE, STATE_INITIALIZED, STATE_NOT, STATE_RUNNING, STATE_STOPPED,\
    STATE_RESETTING
from src.api import API
from src.logger import get_logger

logger = get_logger(__name__)

SLEEP = 1

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
        try:
            di_kwargs = self._get_arguments_from_config()
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
        
        # Listen to systembus
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.NM = 'org.freedesktop.NetworkManager'
        self.bus.add_signal_receiver(self._bus_wireless_feedback, None, self.NM + '.AccessPoint', None, None)
        self.nm = self.bus.get_object(self.NM, '/org/freedesktop/NetworkManager')
        
    def run(self):
        logger.info("Running")
        while not self.run_event.is_set() and not self.stop_event.is_set():
            self._bus_wireless_feedback()
            self._parse_iproute()
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
                name = self._get_device_by_address(e["address"])
                self.status[base_endpoint + name + ".ip"] = e["address"].ip
                self.status[base_endpoint + name + ".port"] = e["address"].port
                self.status[base_endpoint + name + ".total_up"] = e["total_up"]
                self.status[base_endpoint + name + ".total_down"] = e["total_down"]
                self.status[base_endpoint + name + ".total_send"] = e["total_send"]
        except KeyError:
            pass
            
    def socket_state_callback(self, address, state):
        base = "swift.sockets."
        device = self._get_device_by_address(address)
        
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
        iwgetid = os.popen('iwgetid').read()
        ifs = {}
        for line in iwgetid.splitlines(False):
            device = self._regex_find(line, "ESSID:(\.+)", "").strip('"')
            device = device.replace(" ", "_")
            ifs[self._regex_find(line, "(\w+\d)", None)] = device
        iproute = os.popen('ip route').read()
        for line in iproute.splitlines(False): # There might be multiple lines that correspond
            ip = self._regex_find(line, "src (\d+\.\d+\.\d+\.\d+)", None)
            if_name = self._regex_find(line, "dev ([a-zA-Z]{3,4}\d)", None)
            gateway = self._regex_find(line, "default via (\d+\.\d+\.\d+\.\d+)", None)
            if ip is not None and if_name is not None:
                device = ifs.get(if_name) if ifs.get(if_name) is not "" else if_name[0:-1]
                if not self._interface_running(device):
                    self.interface_came_up(ip, if_name, device, gateway=gateway)
                    self.use_interfaces[device] = (time.time(), u"up", ip) # Set the newest state
                    self.status["wireless." + device + ".ip"] = ip
                    self.status["wireless." + device + ".if_name"] = if_name
                    self.status["wireless." + device + ".gateway"] = gateway                    
                
    def _interface_running(self, device):
        return device in self.use_interfaces.iterkeys() and self.use_interfaces[device][1] == u"up"
        
    def _regex_find(self, _input, _format, default):
        m = re.search(_format, _input, re.IGNORECASE)
        if m:
            return m.groups()[0]
        return default
    
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

        return di_kwargs
    
    def dbus_get_property(self, prop, member, proxy):
        return proxy.Get(self.NM + '.' + member, prop, dbus_interface = 'org.freedesktop.DBus.Properties')
    
    def dbus_get_properties(self, dev, member):
        return dev.GetAll(self.NM + '.' + member)
    
    def _bus_wireless_feedback(self, **kwargs):
        for device in self.nm.GetDevices(dbus_interface = self.NM):
            tmp = self.bus.get_object(self.NM, device)
#             logger.debug(self.dbus_get_properties(tmp, "Device"))
            if self.dbus_get_property('DeviceType', 'Device', tmp) == 2: # 2 == Wifi
                for j in self.bus.get_object(self.NM, device).GetAccessPoints(dbus_interface = self.NM+'.Device.Wireless'):
                    k = self.bus.get_object(self.NM, j)
                    ssid = self.dbus_get_property('Ssid', 'AccessPoint', k)
                    strength = self.dbus_get_property('Strength', 'AccessPoint', k)
                    device = "".join([str(s) for s in ssid])
                    device = device.replace(" ", "_")
                    self.status["wireless." + device + ".strength"] = int(strength)
                    
if __name__ == "__main__":
    delft = DelftAPI()
    delft.start()