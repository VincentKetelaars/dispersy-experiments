'''
Created on Aug 29, 2013

@author: Vincent Ketelaars
'''
import os
import random
import sys
import argparse
from threading import Thread, Event

from dispersy.callback import Callback
from dispersy.dispersy import Dispersy
from dispersy.candidate import WalkCandidate

from src.swift.swift_process import MySwiftProcess
from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.endpoint import MultiEndpoint, SwiftEndpoint
from src.dispersy_extends.payload import SimpleFileCarrier, FileHashCarrier
from src.filepusher import FilePusher
from src.definitions import DISPERSY_WORK_DIR, SQLITE_DATABASE, TOTAL_RUN_TIME, MASTER_MEMBER_PUBLIC_KEY, SECURITY, DEFAULT_MESSAGE_COUNT, \
DEFAULT_MESSAGE_DELAY, SLEEP_TIME, RANDOM_PORTS, DEST_DIR, SWIFT_BINPATH

import logging.config
logger = logging.getLogger(__name__)

class DispersyInstance(object):
    '''
    Instance of Dispersy that runs on its own process
    '''

    def __init__(self, dest_dir, swift_binpath, work_dir=DISPERSY_WORK_DIR, sqlite_database=SQLITE_DATABASE, swift_work_dir=None, 
                 swift_zerostatedir=None, ports=[], addresses=[], directory=None, files=[], run_time=TOTAL_RUN_TIME):
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

    def _create_mycommunity(self):    
        master_member = self._dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
        my_member = self._dispersy.get_new_member(SECURITY)
        return MyCommunity.join_community(self._dispersy, master_member, my_member)
        
    def run(self):        
        # Create Dispersy object
        self._callback = Callback("Dispersy-Callback")
        
        endpoint = MultiEndpoint()
        if self._ports:
            for p in self._ports:
                endpoint.add_endpoint(self.create_endpoint(p))
        else:
            endpoint.add_endpoint(self.create_endpoint())

        self._dispersy = Dispersy(self._callback, endpoint, self._work_dir, self._sqlite_database)
        
        self._dispersy.start()
        print "Dispersy is listening on port %d" % self._dispersy.lan_address[1]
        
        self._community = self._callback.call(self._create_mycommunity)
        self._community.dest_dir = self.dest_dir
                
        for address in self._addresses:
            self._callback.call(self._dispersy.create_introduction_request, 
                                (self._community, WalkCandidate(address, False, address, address, u"unknown"),
                                 True,True))
            
        # Start Filepusher if directory or files available
        if self._directory or self._files:
            self._filepusher = FilePusher(self._register_some_message, self._swift_binpath, directory=self._directory, files=self._files)
            self._filepusher.start()
        
        self._thread_loop = Thread(target=self._loop)
        self._thread_loop.daemon = True
        self._thread_loop.start()
        
    def _register_some_message(self, message=None, count=DEFAULT_MESSAGE_COUNT, delay=DEFAULT_MESSAGE_DELAY):
        logger.info("Registered %d messages: %s with delay %f", count, message.filename, delay)
        if isinstance(message, SimpleFileCarrier):
            self._callback.register(self._community.create_simple_messages, (count,message), delay=delay)
        elif isinstance(message, FileHashCarrier):
            self._callback.register(self._community.create_file_hash_messages, (count,message), delay=delay)
        else:
            self._callback.register(self._community.create_simple_messages, (count,None), delay=delay)
        
    def _loop(self):
        # Perhaps this should be a separate thread?
        logger.debug("Start loop")
        self._loop_event = Event()
        for _ in range(int(self._run_time / SLEEP_TIME)):
            if not self._loop_event.is_set():
                self._loop_event.wait(SLEEP_TIME)
        self._stop()
    
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
    
    def create_endpoint(self, port=None):
        """
        Create single SwiftEndpoint
        
        @param port: If set use port to create SwiftProcess, otherwise choose random port
        @return: SwiftEndpoint
        """
        if port is None:
            port = random.randint(*RANDOM_PORTS)
        # TODO: Make sure that the port is not already in use!
        httpgwport = None
        cmdgwport = None
        spmgr = None
        swift_process = MySwiftProcess(self._swift_binpath, self._swift_work_dir, self._swift_zerostatedir, port, 
                                     httpgwport, cmdgwport, spmgr)
        return SwiftEndpoint(swift_process, self._swift_binpath)
    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start Dispersy instance')
    parser.add_argument("-a", "--addresses", nargs="+", help="List addresses of other dispersy instances: 0.0.0.0:12345, space separated")
    parser.add_argument("-d", "--directory",help="List directory of files to send")
    parser.add_argument("-D", "--destination", help="List directory to put downloads")
    parser.add_argument("-f", "--files", nargs="+", help="List files to send")
    parser.add_argument("-i", "--logging", action="store_true", help="If set, logs will be shown in the cmd")
    parser.add_argument("-p", "--ports", type=int, nargs="+", help="List ports to assign to endpoints, space separated")
    parser.add_argument("-P", "--peer_ports", type=int, nargs="+", help="List ports of local dispersy instances, space separated")
    parser.add_argument("-q", "--sqlite_database", default=u":memory:", help="SQLite Database directory")
    parser.add_argument("-s", "--swift", help="Swift binary path")
    parser.add_argument("-S", "--swift_work_dir", help="Swift working directory")
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

    if args.logging:
        logger_conf = os.path.abspath(os.environ.get("LOGGER_CONF", "logger.conf"))
        logging.config.fileConfig(logger_conf, disable_existing_loggers=False)    
        logger.info("Logger using configuration file: " + logger_conf)
        
    # redirect swift output:
    sys.stderr = open(DEST_DIR+"/"+str(os.getpid()) + ".err", "w")
    # redirect standard output: 
    sys.stdout = open(DEST_DIR+"/"+str(os.getpid()) + ".out", "w")
        
    addresses = []
    if args.addresses:
        for a in args.addresses:
            i = a.find(":")
            ip = a[:i]
            port = int(a[i+1:])
            addresses.append((ip, port))
            
    if args.peer_ports:
        for p in args.peer_ports:
            addresses.append((Dispersy._guess_lan_address(),p))
    
    ports = []
    if args.ports:
        for p in args.ports:
            ports.append(p)
        
    d = DispersyInstance(DEST_DIR, SWIFT_BINPATH, work_dir=DISPERSY_WORK_DIR, sqlite_database=SQLITE_DATABASE, 
                         swift_work_dir=args.swift_work_dir, addresses=addresses, ports=ports, directory=args.directory, 
                         files=args.files, run_time=TOTAL_RUN_TIME)
    d.run()
    