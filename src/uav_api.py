'''
Created on Nov 28, 2013

@author: Vincent Ketelaars
'''
import time
import signal
from threading import Event

from Common.Status.StatusDbReader import StatusDbReader
from Common.API import get_config, get_status

from src.address import Address
from src.definitions import STATE_DONE, STATE_INITIALIZED, STATE_NOT, STATE_RUNNING, STATE_STOPPED,\
    STATE_RESETTING
from src.logger import get_logger, get_uav_logger
from src.api import API

logger = get_logger(__name__)

SLEEP = 1

class UAVAPI(API):
    '''
    This class will be the bridge between Dispersy / Libswift and the current UAV system.
    Particularly it will monitor the status of the channels on the UAV, using StatusDbReader.
    At the moment this is still pull based, but this could change.
    '''

    STATES = {STATE_DONE : "done", STATE_INITIALIZED : "initialized", STATE_NOT : "none",
              STATE_RUNNING : "running", STATE_STOPPED : "stopped", STATE_RESETTING : "resetting"}

    def __init__(self, stop_event=Event(), name="Network.Dispersy"):
        '''
        @param stop_event: Event that controls the run of this instance, but does not affect this event itself
        @param name: Name of the instance, must reflect the location of configuration parameters
        '''
        self.stop_event = stop_event
        self.db_reader = StatusDbReader()
        
        self.cfg = get_config(name)
        self.status = get_status(name)
        self.log = get_uav_logger(name)
        
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
        self.use_interfaces = {}
        
        # Set callbacks
        self.state_change_callback(self._state_changed)
        self.swift_state_callback(self._swift_state_changed)
        
        # Set signal quit handler
        signal.signal(signal.SIGQUIT, self.on_quit)
        
    def run(self):
        self.log.info("Running")
        while not self.run_event.is_set() and not self.stop_event.is_set():                
            current_dialers = self._get_dialers()
            for cd in current_dialers:
                timestamp, state = self.db_reader.get_last_status_value(cd, u"state")
                ip = self._get_channel_value(cd, u"ip")
                if (state == u"up" and (not cd in self.use_interfaces.iterkeys() or # Don't know about it yet
                     (cd in self.use_interfaces.iterkeys() and self.use_interfaces[cd][1] != u"up"))): # We do know it, but it wasn't running
                    self._tell_dispersy_if_came_up(cd)
                self.use_interfaces[cd] = (timestamp, state, ip) # Set the newest state
            
            if not self.stop_event.is_set():
                self.run_event.wait(SLEEP)
        if not self._stopping:
            self.stop()
        self.log.debug("Stopped running") 
    
    def stop(self):
        self._stopping = True
        self.log.info("Stopping")
        API.stop(self)
        self._stop()
        
    def _stop(self):
        self.run_event.set()
        self.db_reader.close_connection() # TODO: Do we even have a connection???  
        self.status.kill() # TODO: Perhaps try stop(), doesn't always work
        # Note that stopping status will make the UAV system restart this UAV_API again after some time (within a minute or so)
        
    def on_dispersy_stopped(self):
        logger.debug("Dispersy has stopped")
        self.stop()
        
    def on_quit(self, signal, frame):
        logger.debug("Signaled to quit")
        self.stop()
        
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
        name = self._get_device_by_address(address)
        
        if name is None:
            name = "unknown"
        # TODO: Perhaps update self.use_interfaces
            
        self.status[base + name + ".ip"] = address.ip
        self.status[base + name + ".port"] = address.port
        self.status[base + name + ".state"] = state
        
    def message_received_callback(self, message):
        self.log.info("Received message: %s", message)
        
    def bad_swarm_callback(self, filename):
        self.log.info("Swift can not handle %s", filename)
    
    """
    PRIVATE FUNCTIONS
    """
    
    def _get_device_by_address(self, address):
        if address.interface is not None and address.interface.device is not None:
            name = address.interface.device
        else:
            name = self._get_device_by_ip(address.ip)
        return name              
    
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
    
    def _get_channel_value(self, channel, value):
        """
        @return the database value, otherwise None.
        """
        try:
            res = self.db_reader.get_last_status_value(channel, value)
        except AttributeError:
            logger.exception("Can't get %s %s", channel, value)
            return None 
        return None if res[1] is None else res[1].encode("UTF-8")
        
    def _get_dialers(self):
        channels = []
        try:
            channels = self.db_reader.get_channels()
        except AttributeError:
            pass
        return [c for c in channels if c.startswith("Network.Dialer") and not c.endswith("ChannelChecker")]
    
    def _tell_dispersy_if_came_up(self, device):
        logger.debug("Telling dispersy we have a brand new interface %s", device)
        gateway = self._get_channel_value(device, u"default_gateway")
        ip = self._get_channel_value(device, u"ip")
        interface = self._get_channel_value(device, u"ppp_interface")
        # Send only the device name, without any parents prepended
        self.interface_came_up(ip, interface, device[device.rfind('.') + 1:], gateway=gateway)
        
if __name__ == "__main__":
    uav = UAVAPI()
    uav.start()