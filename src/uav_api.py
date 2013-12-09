'''
Created on Nov 28, 2013

@author: Vincent Ketelaars
'''
import time
from threading import Event

from Common.Status.StatusDbReader import StatusDbReader
from Common.API import get_config, get_status

import sys
# print sys.path
sys.path.insert(2, "/home/vincent/git/dispersy-experiments")
sys.path.insert(3, "/home/vincent/git/dispersy-experiments/tribler")

from src.address import Address
from src.definitions import STATE_DONE, STATE_INITIALIZED, STATE_NOT, STATE_RUNNING, STATE_STOPPED,\
    STATE_RESETTING
from src.logger import get_logger
from src.api import API

logger = get_logger(__name__)

OLDDATATIME = 10 # The time in seconds that may have elapsed after which data from the database becomes to old for use

class UAVAPI(API):
    '''
    This class will be the bridge between Dispersy / Libswift and the current UAV system.
    Particularly it will monitor the status of the channels on the UAV, using StatusDbReader.
    At the moment this is still pull based, but this could change.
    '''

    STATES = {STATE_DONE : "done", STATE_INITIALIZED : "initialized", STATE_NOT : "none",
              STATE_RUNNING : "running", STATE_STOPPED : "stopped", STATE_RESETTING : "resetting"}

    def __init__(self, *di_args, **di_kwargs):
        '''
        @param di_args: Tuple of arguments for DispersyInstance
        @param di_kwargs: Dictionary of arguments for DispersyInstance
        '''
        name = "Network.Dispersy"
        self.db_reader = StatusDbReader()
        
        self.cfg = get_config(name)
        self.status = get_status(name)
        
        try:
            di_args, di_kwargs = self._get_arguments_from_config()
        except:
            logger.exception("Could not get arguments from config, make do with what you've got")
        
        API.__init__(self, name, *di_args, **di_kwargs)

        self.status["state"] = self.STATES[self.state]

        self.run_event = Event()
        self.sleep = 5
        self.stop_on_dispersy_stop = True
        
        # dictionary of known interfaces that should be used and the last state and time
        self.use_interfaces = {}
        
        # Set callbacks
        self.state_change_callback(self._state_changed)
        self.swift_state_callback(self._swift_state_changed)   
        
    def run(self):
        while not self.run_event.is_set():
            try:
                channels = self.db_reader.get_channels()
                for c in channels:
                    if c.startswith("Network") or c.encode('UTF-8') == self.name:
                        params = self.db_reader.get_parameters(c)
                        logger.debug("I have got channel %s with params %s", c, 
                                     [(p, self.db_reader.get_last_status_value(c, p)) for p in params])
                
            except:
                logger.exception("To bad")
                
            current_dialers = self._get_dialers()
            for cd in current_dialers:
                t, state = self.db_reader.get_last_status_value(cd, u"state")
                if (state == u"up" and time.time() - t < OLDDATATIME and 
                    # Either don't know about it yet, or was down
                    (not cd in self.use_interfaces.iterkeys() or (cd in self.use_interfaces.iterkeys() and self.use_interfaces[cd][1] != u"up"))):
                    self._tell_dispersy_if_came_up(cd)
                ip = self._get_channel_value(cd, u"ip")
                self.use_interfaces[cd] = (time, state, ip) # Set the newest state
                
            self.run_event.wait(self.sleep)
        logger.debug("Stopped running")
    
    
    def stop(self):
        API.stop(self)
        self._stop()
        
    def _stop(self):
        self.run_event.set()
        self.db_reader.close_connection() # TODO: Do we even have a connection???
        
    def on_dispersy_stopped(self):
        logger.debug("Dispersy has stopped")
        self._stop()
        
    """
    CALLBACKS
    """
        
    def _state_changed(self, state):
        self.status["state"] = self.STATES[state]
        
    def _swift_state_changed(self, state, error=None):
        self.status["swift.state"] = self.STATES[state]
        
    def swift_info_callback(self, download):
        base = "swift.downloads." + download["roothash"] + "."
        if not self.status.has_key(base + "filename"):
            self.status[base + "filename"] = download["filename"]
            self.status[base + "seeding"] = download["seeding"]
            self.status[base + "path"] = download["path"]
        self.status[base + "leeching"] = download["leeching"]   
        self.status[base + "dynasize"] = download["dynasize"]        
        self.status[base + "progress"] = download["progress"]        
        self.status[base + "current_down_speed"] = download["current_down_speed"]
        self.status[base + "current_up_speed"] = download["current_up_speed"]
        self.status[base + "leechers"] = download["leechers"]
        self.status[base + "seeders"] = download["seeders"]        
        self.status[base + "total_up"] = download["total_up"]        
        self.status[base + "total_down"] = download["total_down"]      
        
        basechannel = "swift.sockets."
        channels = download["channels"]
        for c in channels:
            if_name = self._get_device_by_ip(c["sock_ip"])
            peer_name = c["ip"].replace(".","_") + ":" + str(c["port"])
            self.status[basechannel + if_name + "." + peer_name + ".total_up"] = c["utotal"] # KB
            self.status[basechannel + if_name + "." + peer_name + ".total_down"] = c["dtotal"] # KB
            
    def dispersy_info_callback(self, info):
        base_endpoint = "dispersy.endpoint."
        try:
            me = info["multiendpoint"]
            for e in me:
                name = self._get_device_by_address(e["address"])
                self.status[base_endpoint + name + ".total_up"] = e["total_up"]
                self.status[base_endpoint + name + ".total_down"] = e["total_down"]
                self.status[base_endpoint + name + ".total_send"] = e["total_send"]
        except:
            pass
            
    def socket_state_callback(self, address, state):
        base = "swift.sockets."
        name = self._get_device_by_address(address)
        
        if name is None:
            name = "unknown"
            
        self.status[base + name + ".ip"] = address.ip
        self.status[base + name + ".port"] = address.port
        self.status[base + name + ".state"] = state
            
    
    """
    PRIVATE FUNCTIONS
    """
    
    def _get_device_by_address(self, address):
        if address.interface is not None and address.interface.name in self.use_interfaces.iterkeys():
            name = address.interface.name
        else:
            name = self._get_device_by_ip(address.ip)
        return name              
    
    def _get_device_by_ip(self, ip):
        for i, v in self.use_interfaces.iteritems():
            if v[2] == ip:
                return i[i.rfind('.') + 1:]
        return None
    
    def _get_argument_children(self, arg):
        try:
            listen = self.cfg.get("parameters." + arg)
            return [a.get_value() for a in listen.get_children()]
        except:
            logger.exception("Failed to recover listen parameter")
        return []
    
    def _get_arguments_from_config(self):
        di_args = (self.cfg["parameters.dest_dir"], self.cfg["parameters.swift_binpath"])
        dispersy_work_dir = self.cfg["parameters.dispersy_work_dir"]
        sqlite_database = self.cfg["parameters.sqlite_database"]
        swift_work_dir = self.cfg["parameters.swift_work_dir"]
        swift_zerostatedir = self.cfg["parameters.swift_zerostatedir"]
        listen = self._get_argument_children("listen")
        peers = self._get_argument_children("peers")
        files_directory = self.cfg["parameters.files_directory"]
        files = self._get_argument_children("files")
        run_time = int(self.cfg["parameters.run_time"])
        bloomfilter_update = int(self.cfg["parameters.bloomfilter_update"])
        walker = self.cfg["parameters.walker"]        
        
        di_kwargs = {}
        if dispersy_work_dir is not None:
            di_kwargs["dispersy_work_dir"] = dispersy_work_dir
        if sqlite_database is not None:
            di_kwargs["sqlite_database"] = sqlite_database
        if swift_work_dir is not None:            
            di_kwargs["swift_work_dir"] = swift_work_dir
        if swift_zerostatedir is not None:
            di_kwargs["swift_zerostatedir"] = swift_zerostatedir
        if listen is not None:
            di_kwargs["listen"] = [Address.unknown(l.encode('UTF-8')) for l in listen]
        if peers is not None:
            di_kwargs["peers"] = [Address.unknown(p.encode('UTF-8')) for p in peers]
        if files_directory is not None:
            di_kwargs["files_directory"] = files_directory
        if files is not None:
            di_kwargs["files"] = files
        if run_time is not None:
            di_kwargs["run_time"] = run_time
        if bloomfilter_update is not None:
            di_kwargs["bloomfilter_update"] = bloomfilter_update
        if walker is not None:
            di_kwargs["walker"] = walker
        return di_args, di_kwargs
    
    def _get_channel_value(self, channel, value):
        """
        @return the database value, otherwise None.
        """
        try:
            res = self.db_reader.get_last_status_value(channel, value)
        except:
            logger.exception("Can't get %s %s", channel, value)
            return None 
        return None if res[1] is None else res[1].encode("UTF-8")
        
    def _get_dialers(self):
        channels = []
        try:
            channels = self.db_reader.get_channels()
        except:
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
#     from src.main import main
#     main(UAVAPI)
    uav = UAVAPI()
    uav.start()