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
from dispersy.candidate import WalkCandidate
from dispersy.callback import Callback

from src.tools.runner import CallFunctionThread
from dispersy.dispersy import Dispersy
from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.endpoint import MultiEndpoint, try_sockets
from src.dispersy_extends.payload import SimpleFileCarrier, FileHashCarrier
from src.filepusher import FilePusher
from src.definitions import DISPERSY_WORK_DIR, SQLITE_DATABASE, TOTAL_RUN_TIME, MASTER_MEMBER_PUBLIC_KEY, SECURITY, DEFAULT_MESSAGE_COUNT, \
DEFAULT_MESSAGE_DELAY, SLEEP_TIME, RANDOM_PORTS, DEST_DIR, SWIFT_BINPATH

logger = get_logger(__name__)

class DispersyInstance(object):
    '''
    Instance of Dispersy that runs on its own process
    '''

    def __init__(self, dest_dir, swift_binpath, work_dir=u".", sqlite_database=u":memory:", swift_work_dir=None, 
                 swift_zerostatedir=None, ports=[], addresses=[], directory=None, files=[], run_time=-1):
        self._dest_dir = dest_dir
        self._swift_binpath = swift_binpath
        self._work_dir = work_dir
        self._sqlite_database = sqlite_database
        self._swift_work_dir = swift_work_dir
        self._swift_zerostatedir = swift_zerostatedir
        self._ports = ports
        self._addresses = addresses
        self._directory = directory
        self._files = files
        self._filepusher = None
        self._run_time = run_time
        
        self._loop_event = Event()
        
        # redirect swift output:
        sys.stderr = open(self._dest_dir+"/"+str(os.getpid()) + ".err", "w")
        # redirect standard output: 
        sys.stdout = open(self._dest_dir+"/"+str(os.getpid()) + ".out", "w")
        

    def create_mycommunity(self):    
        master_member = self._dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
        my_member = self._dispersy.get_new_member(SECURITY)
        return MyCommunity.join_community(self._dispersy, master_member, my_member)
    
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
        
        self._swift = self.create_swift_instance(self._ports)
        endpoint = MultiEndpoint(self._swift)

        self._dispersy = Dispersy(self._callback, endpoint, self._work_dir, self._sqlite_database)
        
        self._dispersy.start()
        print "Dispersy is listening on port %d" % self._dispersy.lan_address[1]
        
        self._community = self._callback.call(self.create_mycommunity)
        self._community.dest_dir = self.dest_dir # Will be used to put swift downloads
        
        # Remove all duplicate ip addresses, regardless of their ports.
        # We assume that same ip means same dispersy instance for now.
        addrs = self.remove_duplicate_ip(self._addresses)
        
        for address in addrs:
            self.send_introduction_request(address)
            
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
    
    def create_swift_instance(self, ports):
        
        def recur(ports, n, iteration):
            if iteration >= 5:
                return None
            if ports is None or not ports:
                ports = [random.randint(*RANDOM_PORTS) for _ in range(n)]
            if not try_sockets(ports):
                recur(None, iteration + 1)
            return ports
        
        if ports is None or not ports:
            ports = recur(None, 1, 0)
        else:
            ports = recur(ports, len(ports), 0)
        
        if ports is None:
            logger.warning("Could not obtain free ports!")
        else:
            logger.debug("Swift will listen to %s", ports)
        
        httpgwport = None
        cmdgwport = None
        spmgr = None
        return MySwiftProcess(self._swift_binpath, self._swift_work_dir, self._swift_zerostatedir, ports, 
                                     httpgwport, cmdgwport, spmgr)
        
    def remove_duplicate_ip(self, addrs):
        faddrs = []
        for a in addrs:
            if all([a[0] != f[0] for f in faddrs]):
                faddrs.append(a)
        return faddrs
    
    def send_introduction_request(self, address):
        addr = [1] # Tuple is not remembered in callback. Array is.
        addr[0] = address
        
        def send_request():
            self._callback.register(self._dispersy.create_introduction_request, 
                                (self._community, WalkCandidate(addr[0], True, addr[0], addr[0], u"unknown"),
                                 True,True),callback=callback)

        thread_func = CallFunctionThread()
        event = Event()
        
        def callback(result):
            if isinstance(result, Exception):
                # Somehow the introduction request did not work
                event.wait(1)
                thread_func.put(send_request)
            # Stop thread_func.. No longer necessary
            thread_func.stop()
        
        thread_func.start()
        thread_func.put(send_request)
        
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start Dispersy instance')
    parser.add_argument("-a", "--addresses", nargs="+", help="List addresses of other dispersy instances: 0.0.0.0:12345, space separated")
    parser.add_argument("-d", "--directory",help="List directory of files to send")
    parser.add_argument("-D", "--destination", help="List directory to put downloads")
    parser.add_argument("-f", "--files", nargs="+", help="List files to send")
    parser.add_argument("-p", "--ports", type=int, nargs="+", help="List ports to assign to endpoints, space separated")
    parser.add_argument("-P", "--peer_ports", type=int, nargs="+", help="List ports of local dispersy instances, space separated")
    parser.add_argument("-q", "--sqlite_database", default=u":memory:", help="SQLite Database directory")
    parser.add_argument("-s", "--swift", help="Swift binary path")
    parser.add_argument("-t", "--time",type=float, help="Set runtime")
    parser.add_argument("-w", "--work_dir", help="Working directory")
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
        
    addresses = []
    if args.addresses:
        for a in args.addresses:
            i = a.find(":")
            ip = a[:i]
            port = int(a[i+1:])
            addresses.append((ip, port))
    
    if args.peer_ports:
        for p in args.peer_ports:
            local_address = Dispersy._guess_lan_address()
            if local_address is None:
                local_address = "0.0.0.0"
            addresses.append((local_address,p))
    
    ports = []
    if args.ports:
        for p in args.ports:
            ports.append(p)
        
    d = DispersyInstance(DEST_DIR, SWIFT_BINPATH, work_dir=DISPERSY_WORK_DIR, sqlite_database=SQLITE_DATABASE, 
                         swift_work_dir=DEST_DIR, addresses=addresses, ports=ports, directory=args.directory, 
                         files=args.files, run_time=TOTAL_RUN_TIME)
    d.start()
    