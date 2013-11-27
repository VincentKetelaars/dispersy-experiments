'''
Created on Aug 29, 2013

@author: Vincent Ketelaars
'''
import os
import random
import sys
from threading import Event

from dispersy.logger import get_logger
from src.swift.swift_process import MySwiftProcess  # This should be imported first, or it will screw up the logs. # TODO: Fix this
from dispersy.callback import Callback
from dispersy.dispersy import Dispersy

from src.address import Address
from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.endpoint import MultiEndpoint, try_sockets
from src.dispersy_extends.payload import SimpleFileCarrier, FileHashCarrier
from src.filepusher import FilePusher
from src.definitions import MASTER_MEMBER_PUBLIC_KEY, SECURITY, DEFAULT_MESSAGE_COUNT, DEFAULT_MESSAGE_DELAY, \
SLEEP_TIME, RANDOM_PORTS, STATE_INITIALIZED, STATE_RUNNING, STATE_STOPPED, STATE_DONE, MESSAGE_KEY_STATE

logger = get_logger(__name__)

class DispersyInstance(object):
    '''
    Instance of Dispersy that runs on its own process
    '''

    def __init__(self, dest_dir, swift_binpath, dispersy_work_dir=u".", sqlite_database=u":memory:", swift_work_dir=None,
                 swift_zerostatedir=None, listen=[], peers=[], files_directory=None, files=[], run_time=-1, bloomfilter_update=-1,
                 walker=False, callback=None):
        self._dest_dir = dest_dir
        self._swift_binpath = swift_binpath
        self._dispersy_work_dir = dispersy_work_dir 
        self._sqlite_database = sqlite_database # :memory: is in memory
        self._swift_work_dir = swift_work_dir
        self._swift_zerostatedir = swift_zerostatedir 
        self._listen = listen # Local socket addresses, instances of Address
        self._peers = peers # Peer addresses, instances of Address
        self._files_directory = files_directory # Directory to monitor for new files (or changes in files)
        self._files = files # Files to monitor
        self._run_time = run_time # Time after which this process stops, -1 is infinite
        self._bloomfilter_update = bloomfilter_update # Update every # seconds the bloomfilter to peers, -1 for never
        self._walker = walker # Turn walker on
        self._api_callback = callback # Subscription to various callbacks
        
        self._filepusher = None
        
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
        self._endpoint = MultiEndpoint(self._swift, self._api_callback)

        self._dispersy = Dispersy(self._callback, self._endpoint, self._dispersy_work_dir, self._sqlite_database)
        
        # Timeout determines how long the bootstrappers should try before continuing (at the moment)
        self._dispersy.start(timeout=1.0) 
        print "Dispersy is listening on port %d" % self._dispersy.lan_address[1]
        
        self._community = self._callback.call(self.create_mycommunity)
        self._community.dest_dir = self.dest_dir  # Will be used to put swift downloads
        self._community.update_bloomfilter = self._bloomfilter_update
        
        # Remove all duplicate ip addresses, regardless of their ports.
        # We assume that same ip means same dispersy instance for now.
        addrs = self.remove_duplicate_ip(self._peers)
        
        for a in addrs:
            self.send_introduction_request(a.addr())
            
        # Start Filepusher regardless of availability of directory or files
        self._filepusher = FilePusher(self._register_some_message, self._swift_binpath, directory=self._files_directory, files=self._files)
        self._filepusher.start()
        
        self.state = STATE_RUNNING
        self._loop()
        
    def _loop(self):
        # Perhaps this should be a separate thread?
        logger.debug("Start loop")
        for _ in range(int(self._run_time / SLEEP_TIME)):
            if not self._loop_event.is_set():
                self._loop_event.wait(SLEEP_TIME)
                
        while self._run_time == -1 and not self._loop_event.is_set():
            logger.debug("Start infinite loop")
            self._loop_event.wait()
    
    def stop(self):
        self.state = STATE_STOPPED
        self._loop_event.set()
    
    def _stop(self):
        logger.debug("Stop instance")
        try:
            if self._filepusher is not None:
                self._filepusher.stop()
            return self._dispersy.stop()
        except:
            logger.error("STOPPING HAS FAILED!")
        finally:
            self.state = STATE_DONE
            # TODO: How do we make sure that we are completely done?
            pass

    @property
    def state(self):
        return self._state
    
    @state.setter
    def state(self, state):
        self._state = state
        logger.info("STATECHANGE %d", state)
        if self._api_callback is not None:
            self._api_callback(MESSAGE_KEY_STATE, state)
            
    @property
    def dest_dir(self):
        return self._dest_dir

    def create_mycommunity(self):    
        master_member = self._dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
        my_member = self._dispersy.get_new_member(SECURITY)
        return MyCommunity.join_community(self._dispersy, master_member, my_member, *(), **{"enable":self._walker})
        
    def _register_some_message(self, message=None, count=DEFAULT_MESSAGE_COUNT, delay=DEFAULT_MESSAGE_DELAY):
        logger.info("Registered %d messages: %s with delay %f", count, message.filename, delay)
        if isinstance(message, SimpleFileCarrier):
            self._callback.register(self._community.create_simple_messages, (count, message), kargs={"update":False}, delay=delay)
        elif isinstance(message, FileHashCarrier):
            self._callback.register(self._community.create_file_hash_messages, (count, message), kargs={"update":False}, delay=delay)
        else:
            self._callback.register(self._community.create_simple_messages, (count, None), kargs={"update":False}, delay=delay)
    
    def create_swift_instance(self, addrs):
        addrs = verify_addresses_are_free(addrs)
        httpgwport = None
        cmdgwport = None
        spmgr = None
        return MySwiftProcess(self._swift_binpath, self._swift_work_dir, self._swift_zerostatedir, addrs,
                                     httpgwport, cmdgwport, spmgr)
        
    def remove_duplicate_ip(self, addrs):
        faddrs = []
        for a in addrs:
            if all([a.ip != f.ip for f in faddrs]):
                faddrs.append(a)
        return faddrs
    
    def send_introduction_request(self, address):
        # Each new candidate will be sent an introduction request once
        # If update_bloomfilter > 0, then every so many seconds an introduction request will be sent
        self._community.create_candidate(address, True, address, address, u"unknown")
        
def verify_addresses_are_free(addrs):
    def recur(addrs, n, iteration):
        if iteration >= 5:
            return None
        if addrs is None or not addrs:
            addrs = [Address.localport(random.randint(*RANDOM_PORTS)) for _ in range(n)]
        for addr in addrs:
            if not try_sockets([addr]):
                addr.set_port(random.randint(*RANDOM_PORTS))
                addr = recur([addr], 1, iteration + 1)[0]
        return addrs
    
    if addrs is None or not addrs:
        addrs = recur(None, 1, 0)
    else:
        addrs = recur(addrs, len(addrs), 0)
    
    if addrs is None:
        logger.warning("Could not obtain free ports!")
    else:
        logger.debug("Swift will listen to %s", [str(a) for a in addrs])
        
    return addrs
    
if __name__ == '__main__':
    from src.main import main
    main(DispersyInstance)
