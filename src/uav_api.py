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
from src.definitions import STATE_DONE, STATE_INITIALIZED, STATE_NOT, STATE_RUNNING, STATE_STOPPED
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
              STATE_RUNNING : "running", STATE_STOPPED : "stopped"}

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
        self.state_change_callback(self.state_changed)        
        
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
                self.use_interfaces[cd] = (time, state) # Set the newest state
                
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
        
    def state_changed(self, state):
        self.status["state"] = self.STATES[state]
        
    
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
    
    def _get_channel_value(self, channel, *values):
        """
        Returns the resulting list of string values in the same order they were requested.
        If an error occurs, order cannot be maintained and the result is None
        """
        r = []
        for v in values:
            try:
                res = self.db_reader.get_last_status_value(channel, v)
                r.append(res[1].encode("UTF-8"))
            except:
                logger.exception("Can't get %s %s", channel, v)
                return None 
        return r    
        
    def _get_dialers(self):
        channels = []
        try:
            channels = self.db_reader.get_channels()
        except:
            pass
        return [c for c in channels if c.startswith("Network.Dialer") and not c.endswith("ChannelChecker")]
    
    def _tell_dispersy_if_came_up(self, device):
        logger.debug("Telling dispersy we have a brand new interface %s", device)
        res = self._get_channel_value(device, u"default_gateway", u"ip", u"ppp_interface")
        if res is not None:
            # Send only the device name, without any parents prepended
            self.interface_came_up(res[1], res[2], device[device.rfind('.') + 1:], gateway=res[0])
        else:
            logger.debug("Couldn't get all the information")
        
if __name__ == "__main__":
#     from src.main import main
#     main(UAVAPI)
    uav = UAVAPI()
    uav.start()