'''
Created on Aug 29, 2013

@author: Vincent Ketelaars
'''
import os
import random
import sys
import argparse
from threading import Event

from dispersy.logger import get_logger
from src.swift.swift_process import MySwiftProcess # This should be imported first, or it will screw up the logs.
# from dispersy.candidate import WalkCandidate
from dispersy.callback import Callback
from dispersy.dispersy import Dispersy

from src.address import Address
from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.endpoint import MultiEndpoint, try_sockets
from src.dispersy_extends.payload import SimpleFileCarrier, FileHashCarrier
from src.filepusher import FilePusher
from src.definitions import DISPERSY_WORK_DIR, SQLITE_DATABASE, TOTAL_RUN_TIME, MASTER_MEMBER_PUBLIC_KEY, SECURITY, DEFAULT_MESSAGE_COUNT, \
DEFAULT_MESSAGE_DELAY, SLEEP_TIME, RANDOM_PORTS, DEST_DIR, SWIFT_BINPATH, BLOOM_FILTER_UPDATE, ENABLE_CANDIDATE_WALKER

logger = get_logger(__name__)

class DispersyInstance(object):
    '''
    Instance of Dispersy that runs on its own process
    '''

    def __init__(self, dest_dir, swift_binpath, work_dir=u".", sqlite_database=u":memory:", swift_work_dir=None, 
                 swift_zerostatedir=None, listen=[], peers=[], directory=None, files=[], run_time=-1, bloomfilter_update=-1,
                 walker=False):
        self._dest_dir = dest_dir
        self._swift_binpath = swift_binpath
        self._work_dir = work_dir
        self._sqlite_database = sqlite_database
        self._swift_work_dir = swift_work_dir
        self._swift_zerostatedir = swift_zerostatedir
        self._listen = listen
        self._peers = peers
        self._directory = directory
        self._files = files
        self._filepusher = None
        self._run_time = run_time
        self._bloomfilter_update = bloomfilter_update
        self._walker = walker
        
        self._loop_event = Event()
        
        # redirect swift output:
        sys.stderr = open(self._dest_dir+"/"+str(os.getpid()) + ".err", "w")
        # redirect standard output: 
        sys.stdout = open(self._dest_dir+"/"+str(os.getpid()) + ".out", "w")
        

    def create_mycommunity(self):    
        master_member = self._dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
        my_member = self._dispersy.get_new_member(SECURITY)
        return MyCommunity.join_community(self._dispersy, master_member, my_member, {"enable":self._walker,})
    
    def start(self):
        try:
            self.run()
        except Exception:
            logger.exception("Dispersy instance failed to run properly")
        finally:
            self._stop()
        
    def run(self):        
        # Create Dispersy object
        self._callback = Callback("Dispersy-Callback")
        
        self._swift = self.create_swift_instance(self._listen)
        endpoint = MultiEndpoint(self._swift)

        self._dispersy = Dispersy(self._callback, endpoint, self._work_dir, self._sqlite_database)
        
        self._dispersy.start()
        print "Dispersy is listening on port %d" % self._dispersy.lan_address[1]
        
        self._community = self._callback.call(self.create_mycommunity)
        self._community.dest_dir = self.dest_dir # Will be used to put swift downloads
        self._community.update_bloomfilter = self._bloomfilter_update
        
        # Remove all duplicate ip addresses, regardless of their ports.
        # We assume that same ip means same dispersy instance for now.
        addrs = self.remove_duplicate_ip(self._peers)
        
        for a in addrs:
            self.send_introduction_request(a.addr())
            
        # Start Filepusher if directory or files available
        if self._directory or self._files:
            self._filepusher = FilePusher(self._register_some_message, self._swift_binpath, directory=self._directory, files=self._files)
            self._filepusher.start()
        
        self._loop()
        
    def _register_some_message(self, message=None, count=DEFAULT_MESSAGE_COUNT, delay=DEFAULT_MESSAGE_DELAY):
        logger.info("Registered %d messages: %s with delay %f", count, message.filename, delay)
        if isinstance(message, SimpleFileCarrier):
            self._callback.register(self._community.create_simple_messages, (count,message), kargs={"update":False}, delay=delay)
        elif isinstance(message, FileHashCarrier):
            self._callback.register(self._community.create_file_hash_messages, (count,message), kargs={"update":False}, delay=delay)
        else:
            self._callback.register(self._community.create_simple_messages, (count,None), kargs={"update":False}, delay=delay)
        
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
        self._loop_event.set()
    
    def _stop(self):
        logger.debug("Stop instance")
        try:
            if self._filepusher is not None:
                self._filepusher.stop()
            self._dispersy.stop()
        except:
            logger.error("STOPPING HAS FAILED!")
        
    @property
    def dest_dir(self):
        return self._dest_dir
    
    def create_swift_instance(self, addrs):
        
        def recur(addrs, n, iteration):
            if iteration >= 5:
                return None
            if addrs is None or not addrs:
                addrs = [Address.localport(random.randint(*RANDOM_PORTS)) for _ in range(n)]
            # TODO: Go through each address separately, otherwise unnecessary generating, and increasing chance of failure
            if not try_sockets(addrs):
                addrs = recur(None, n, iteration + 1)
            return addrs
        
        if addrs is None or not addrs:
            addrs = recur(None, 1, 0)
        else:
            addrs = recur(addrs, len(addrs), 0)
        
        if addrs is None:
            logger.warning("Could not obtain free ports!")
        else:
            logger.debug("Swift will listen to %s", [str(a) for a in addrs])
        
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
        # Each new candidate will be sent an introduction request, if update_bloomfilter > 0
        self._community.create_candidate(address, True, address, address, u"unknown") 
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start Dispersy instance')
    parser.add_argument("-b", "--bloomfilter",help="Send bloom filter every # seconds")
    parser.add_argument("-d", "--directory",help="List directory of files to send")
    parser.add_argument("-D", "--destination", help="List directory to put downloads")
    parser.add_argument("-f", "--files", nargs="+", help="List files to send")
    parser.add_argument("-l", "--listen", nargs="+", help="List of sockets to listen to (port, ip4, ip6), space separated")
    parser.add_argument("-p", "--peers", nargs="+", help="List of Dispersy peers(port, ip4, ip6), space separated")
    parser.add_argument("-q", "--sqlite_database", default=u":memory:", help="SQLite Database directory")
    parser.add_argument("-s", "--swift", help="Swift binary path")
    parser.add_argument("-t", "--time",type=float, help="Set runtime")
    parser.add_argument("-w", "--work_dir", help="Working directory")
    parser.add_argument("-W", "--walker", action='store_true', help="Enable candidate walker")
    args = parser.parse_args()
    
    if args.time:
        TOTAL_RUN_TIME = args.time
        
    if args.destination:
        DEST_DIR = args.destination
    
    if args.swift:
        SWIFT_BINPATH = args.swift
        
    if args.work_dir:
        DISPERSY_WORK_DIR = args.work_dir
        
    if args.sqlite_database:
        SQLITE_DATABASE = args.sqlite_database
        
    if args.bloomfilter:
        BLOOM_FILTER_UPDATE = args.bloomfilter
        
    if args.walker:
        ENABLE_CANDIDATE_WALKER = args.walker
        
    localip = "127.0.0.1"
    local_interface = Dispersy._guess_lan_address(Dispersy._get_interface_addresses())
    if local_interface is not None:
        localip = local_interface.address
        
    listen = []
    if args.listen:
        for a in args.listen:
            addr = Address.unknown(a)
            if addr.is_wildcard_ip():
                addr.set_ipv4(localip)
            listen.append(addr)
    
    peers = []
    if args.peers:
        for p in args.peers:
            addr = Address.unknown(p)
            if addr.is_wildcard_ip():
                addr.set_ipv4(localip)
            peers.append(addr)
        
    d = DispersyInstance(DEST_DIR, SWIFT_BINPATH, work_dir=DISPERSY_WORK_DIR, sqlite_database=SQLITE_DATABASE, 
                         swift_work_dir=DEST_DIR, listen=listen, peers=peers, directory=args.directory, 
                         files=args.files, run_time=TOTAL_RUN_TIME, bloomfilter_update=BLOOM_FILTER_UPDATE, 
                         walker=ENABLE_CANDIDATE_WALKER)
    d.start()
    