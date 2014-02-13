'''
Created on Aug 29, 2013

@author: Vincent Ketelaars
'''
import os
import random
import sys
from threading import Event

from src.logger import get_logger
from src.swift.swift_process import MySwiftProcess  # This should be imported first, or it will screw up the logs. # TODO: Fix this
from dispersy.callback import Callback

from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.endpoint import MultiEndpoint, try_sockets
from src.dispersy_extends.payload import SmallFileCarrier, FileHashCarrier,\
    APIMessageCarrier
from src.dispersy_extends.mydispersy import MyDispersy
from src.filepusher import FilePusher
from src.definitions import MASTER_MEMBER_PUBLIC_KEY, SECURITY, DEFAULT_MESSAGE_COUNT, DEFAULT_MESSAGE_DELAY, \
SLEEP_TIME, STATE_INITIALIZED, STATE_RUNNING, STATE_STOPPED, STATE_DONE, MESSAGE_KEY_STATE,\
    MESSAGE_KEY_SWIFT_STATE, MAX_MTU, DISPERSY_MESSAGE_MINIMUM,\
    BOOTSTRAPPERS_RESOLVE_TIME
from src.address import Address

logger = get_logger(__name__)

class DispersyInstance(object):
    '''
    Instance of Dispersy
    '''

    def __init__(self, dest_dir, swift_binpath, dispersy_work_dir=u".", sqlite_database=":memory:", swift_work_dir=None,
                 swift_zerostatedir=None, listen=[], peers=[], files_directory=None, files=[], file_timestamp_min=None, 
                 run_time=-1, bloomfilter_update=-1, walker=False, gateways={}, mtu=MAX_MTU, callback=None):
        """
        @param dest_dir: Directory in which downloads will be placed as well as logs
        @param swift_binpath: Path to the swift executable
        @param dispersy_work_dir: Working directory for Dispersy
        @param sqlite_database: Location of the sqlite_database, :memory: is in memory
        @param swift_work_dir: Working directory for Swift
        @param swift_zerostatedir: Zero state directory for Swift
        @param listen: Addresses of local sockets to bind to
        @param peers: Addresses of peers to communicate with
        @param files_directory: Directory to monitor for files that should be disseminated
        @param files: Files that should be disseminated
        @param file_timestamp_min: Minimum file modification time
        @param run_time: Total run time in seconds
        @param bloomfilter_update: Period after which another introduction request is sent in seconds
        @param walker: If enable the Dispersy walker will be enabled
        @param gateways: Ip addresses of the gateways for specific interfaces (eth0=192.168.0.1)
        @param mtu: Maximum transmission unit directs the maximum size of messages
        @param callback: Callback function that will called on certain events
        """
        self._dest_dir = dest_dir
        self._swift_binpath = swift_binpath
        self._dispersy_work_dir = unicode(dispersy_work_dir)
        self._sqlite_database = unicode(sqlite_database) # :memory: is in memory
        self._swift_work_dir = swift_work_dir if swift_work_dir is not None else dest_dir
        self._swift_zerostatedir = swift_zerostatedir 
        self._listen = [Address.unknown(l) for l in listen] # Local socket addresses
        self._peers = [Address.unknown(p) for p in peers] # Peer addresses
        self._files_directory = files_directory # Directory to monitor for new files (or changes in files)
        self._files = files # Files to monitor
        self._file_timestamp_min = file_timestamp_min  # Minimum file modification time
        self._run_time = int(run_time) # Time after which this process stops, -1 is infinite
        self._bloomfilter_update = float(bloomfilter_update) # Update every # seconds the bloomfilter to peers, -1 for never
        self._walker = walker # Turn walker on
        self._api_callback = callback # Subscription to various callbacks
        self._gateways = {}
        for g in gateways:
            a = g.split("=")
            if len(a) == 2:
                self._gateways[a[0]] = a[1]
        self._mtu = mtu
        
        self._filepusher = FilePusher(self._register_some_message, self._swift_binpath, 
                                      directory=self._files_directory, files=self._files, 
                                      file_size=self._mtu - DISPERSY_MESSAGE_MINIMUM,
                                      min_timestamp=self._file_timestamp_min)
        
        self._loop_event = Event() # Loop
        
        # redirect swift output:
        sys.stderr = open(self._dest_dir + "/" + str(os.getpid()) + ".err", "w")
        # redirect standard output: 
        sys.stdout = open(self._dest_dir + "/" + str(os.getpid()) + ".out", "w")
        
        self._state = STATE_INITIALIZED
    
    def start(self):
        try:
            self.run()
        except Exception:
            logger.exception("Dispersy instance failed to run properly")
        finally:
            return self._stop()
        
    def run(self):        
        # Create Dispersy object
        self._callback = Callback("Dispersy-Callback-" + str(random.randint(0,1000000)))
        
        self._swift = self.create_swift_instance(self._listen)
        self.do_callback(MESSAGE_KEY_SWIFT_STATE, STATE_INITIALIZED)
        self._endpoint = MultiEndpoint(self._swift, self._api_callback)

        self._dispersy = MyDispersy(self._callback, self._endpoint, self._dispersy_work_dir, self._sqlite_database)
        
        # Timeout determines how long the bootstrappers should try before continuing (at the moment)
        timeout = BOOTSTRAPPERS_RESOLVE_TIME if self._walker else 0.0 # 0.0 bootstrap will be registered instead of blocking call
        self._dispersy.start(timeout=timeout) 
        print "Dispersy is listening on port %d" % self._dispersy.lan_address[1]
        
        self._community = self._callback.call(self.create_mycommunity)
        self._community.dest_dir = self.dest_dir  # Will be used to put swift downloads
        self._community.update_bloomfilter = self._bloomfilter_update
        
        # Remove all duplicate ip addresses, regardless of their ports.
        # We assume that same ip means same dispersy instance for now.
        addrs = self.remove_duplicate_ip(self._peers)
        
        for a in addrs:
            self.send_introduction_request(a.addr())
        
        self._filepusher.start()
        
        self.state = STATE_RUNNING
        self._loop()
        
    def _loop(self):
        logger.debug("Start loop")
        while self._run_time < 0 and not self._loop_event.is_set():
            self._loop_event.wait(10.0) # Wait some time, so that we can actually receive keyboard signals (need that timeout)
        else:
            for _ in range(int(self._run_time / SLEEP_TIME)):
                if not self._loop_event.is_set():
                    self._loop_event.wait(SLEEP_TIME)
            
    def stop(self):
        self.state = STATE_STOPPED
        self._loop_event.set()
    
    def _stop(self):
        logger.debug("Stop instance")
        try:
            if self._filepusher is not None:
                self._filepusher.stop()
            return self._dispersy.stop()
        except AttributeError:
            logger.error("Could not stop Dispersy")
        finally:
            self.state = STATE_DONE
            # TODO: How do we make sure that we are completely done?

    @property
    def state(self):
        return self._state
    
    @state.setter
    def state(self, state):
        self._state = state
        logger.info("STATECHANGE %d", state)
        self.do_callback(MESSAGE_KEY_STATE, state)
            
    @property
    def dest_dir(self):
        return self._dest_dir

    def create_mycommunity(self):    
        master_member = self._dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
        my_member = self._dispersy.get_new_member(SECURITY)
        args = ()
        kwargs = {"enable" : self._walker, "api_callback" : self._api_callback}
        return MyCommunity.join_community(self._dispersy, master_member, my_member, *args, **kwargs)
        
    def _register_some_message(self, message=None, count=DEFAULT_MESSAGE_COUNT, delay=DEFAULT_MESSAGE_DELAY):
        logger.info("Registered %d messages: %s with delay %f", count, message, delay)
        if isinstance(message, SmallFileCarrier):
            self._callback.register(self._community.create_small_file_messages, (count, message), kargs={"update":False}, delay=delay)
        elif isinstance(message, FileHashCarrier):
            self._callback.register(self._community.create_file_hash_messages, (count, message), kargs={"update":False}, delay=delay)
        elif isinstance(message, APIMessageCarrier):
            self._callback.register(self._community.create_api_messages, (count, message), kargs={"update":False}, delay=delay)
        else:
            logger.debug("Don't know what this is: %s", message)
    
    def create_swift_instance(self, addrs):
        addrs = verify_addresses_are_free(addrs)
        httpgwport = None
        cmdgwport = None
        spmgr = None
        return MySwiftProcess(self._swift_binpath, self._swift_work_dir, self._swift_zerostatedir, addrs,
                                     httpgwport, cmdgwport, spmgr, gateways=self._gateways)
        
    def remove_duplicate_ip(self, addrs):
        faddrs = []
        for a in addrs:
            if all([a.ip != f.ip for f in faddrs]):
                faddrs.append(a)
        return faddrs
    
    def send_introduction_request(self, address):
        # Each new candidate will be sent an introduction request once
        # If update_bloomfilter > 0, then every so many seconds an introduction request will be sent
        # Introduction request contains the Dispersy address
        self._community.create_candidate(address, True, address, address, u"unknown")
        
    def do_callback(self, key, *args, **kwargs):
        if self._api_callback is not None:
            self._api_callback(key, *args, **kwargs)
        
def verify_addresses_are_free(addrs):    
    if not addrs: # None or []
        logger.warning("No address to return!")
        return addrs
    l = set() # No doubles!
    for addr in addrs:
        if not addr.resolve_interface():
            logger.debug("Interface for %s does not exist", addr)
        elif not try_sockets([addr]):
            logger.debug("Port %s is not available for %s on %s", addr.port, addr.ip, addr.interface.name)
            addr.set_port(0) # Let the system decide
            l.add(addr)
        else:
            l.add(addr)
    logger.debug("Swift will listen to %s", [str(a) for a in l])        
    return list(l)
    
if __name__ == '__main__':
    from src.main import main
    args, kwargs = main()
    d = DispersyInstance(*args, **kwargs)
    d.start()
