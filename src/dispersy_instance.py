'''
Created on Aug 29, 2013

@author: Vincent Ketelaars
'''

import random
import sys
import os
import argparse
import time

from datetime import datetime

from dispersy.callback import Callback
from dispersy.dispersy import Dispersy
from dispersy.candidate import WalkCandidate
from Tribler.Core.Swift.SwiftProcess import SwiftProcess

from src.extend.community import MyCommunity
from src.extend.endpoint import MultiEndpoint, SwiftEndpoint
from src.extend.payload import SimpleFileCarrier, FileHashCarrier
from src.filepusher import FilePusher

import logging.config

SECURITY = u"medium"

# generated: Wed Aug  7 14:21:33 2013
# curve: medium <<< NID_sect409k1 >>>
# len: 409 bits ~ 104 bytes signature
# pub: 128 307e301006072a8648ce3d020106052b81040024036a0004004b2c2fbbf036a0ae1dedf4420ff724869e324bc63064ec2e7bad062a7a9c7f31a7c3ff17a11fd582c9eb8b727dacb228afceb2002ad6e916efd4531e79f040341c7259c99938aae9f6ece17c5075b7ab8e9c92f7ff4493468d1e354a31d139e73928266b824fe3
# prv: 178 3081af0201010433252d8205db8f95bbe82a6668ba04c9e13db70b7c3669b451f5d18c24590b8ccb6033f37a9c49b956c84e412a0992f6f76f25ffa00706052b81040024a16c036a0004004b2c2fbbf036a0ae1dedf4420ff724869e324bc63064ec2e7bad062a7a9c7f31a7c3ff17a11fd582c9eb8b727dacb228afceb2002ad6e916efd4531e79f040341c7259c99938aae9f6ece17c5075b7ab8e9c92f7ff4493468d1e354a31d139e73928266b824fe3
# pub-sha1 04b6c5a1eafb928ca5763a8bb93c5ad5a44c971e
# prv-sha1 31510601257b8649d8280cf3334e52de646d4aa9
# -----BEGIN PUBLIC KEY-----
# MH4wEAYHKoZIzj0CAQYFK4EEACQDagAEAEssL7vwNqCuHe30Qg/3JIaeMkvGMGTs
# LnutBip6nH8xp8P/F6Ef1YLJ64tyfayyKK/OsgAq1ukW79RTHnnwQDQcclnJmTiq
# 6fbs4XxQdberjpyS9/9Ek0aNHjVKMdE55zkoJmuCT+M=
# -----END PUBLIC KEY-----
# -----BEGIN EC PRIVATE KEY-----
# MIGvAgEBBDMlLYIF24+Vu+gqZmi6BMnhPbcLfDZptFH10YwkWQuMy2Az83qcSblW
# yE5BKgmS9vdvJf+gBwYFK4EEACShbANqAAQASywvu/A2oK4d7fRCD/ckhp4yS8Yw
# ZOwue60GKnqcfzGnw/8XoR/Vgsnri3J9rLIor86yACrW6Rbv1FMeefBANBxyWcmZ
# OKrp9uzhfFB1t6uOnJL3/0STRo0eNUox0TnnOSgma4JP4w==
# -----END EC PRIVATE KEY-----

MASTER_MEMBER_PUBLIC_KEY = "307e301006072a8648ce3d020106052b81040024036a0004004b2c2fbbf036a0ae1dedf4420ff724869e324bc63064ec2e7bad062a7a9c7f31a7c3ff17a11fd582c9eb8b727dacb228afceb2002ad6e916efd4531e79f040341c7259c99938aae9f6ece17c5075b7ab8e9c92f7ff4493468d1e354a31d139e73928266b824fe3".decode("HEX")

RANDOM_PORTS = (10000, 20000) # TODO: Determine exact range of available ports

DEFAULT_MESSAGE_COUNT = 1
DEFAULT_MESSAGE_DELAY = 0.0

# Time in seconds
SLEEP_TIME = 0.5
TOTAL_RUN_TIME = 10
DEST_DIR = "/home/vincent/Desktop/tests_dest"
SWIFT_BINPATH = "/home/vincent/svn/libswift/ppsp/swift"
WORK_DIR = os.path.expanduser("~") + u"/Music/"+ datetime.now().strftime("%Y%m%d%H%M%S") + "_" + str(os.getpid()) + "/"
SQLITE_DATABASE = u":memory:"

class DispersyInstance(object):
    '''
    Instance of Dispersy that runs on its own process
    '''

    def __init__(self, dest_dir, swift_binpath, work_dir=WORK_DIR, sqlite_database=SQLITE_DATABASE, swift_work_dir=None, 
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
            self._filepusher = FilePusher(self._register_some_message, directory=self._directory, files=self._files)
            self._filepusher.start()
            
        self._loop()
        
        self._stop()
        
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
        self._continue = True
        for _ in range(int(self._run_time / SLEEP_TIME)):
            if not self._continue:
                break
            time.sleep(SLEEP_TIME)
    
    def stop(self, continue_):
        self._continue = continue_
    
    def _stop(self):
        try:
            if self._filepusher is not None:
                self._filepusher.stop()
            self._dispersy.stop()
        except:
            logger.info("STOPPING HAS FAILED!")
        
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
        httpgwport = None
        cmdgwport = None
        spmgr = None
        swift_process = SwiftProcess(self._swift_binpath, self._swift_work_dir, self._swift_zerostatedir, port, 
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
        WORK_DIR = args.work_dir
        
    if args.sqlite_database:
        SQLITE_DATABASE = args.sqlite_database
        
    if args.logging:
        logger_conf = os.path.abspath(os.environ.get("LOGGER_CONF", "logger.conf"))
        logging.config.fileConfig(logger_conf)
        logger = logging.getLogger(__name__)
        logger.info("Logger using configuration file: " + logger_conf)
        # redirect swift output:
        sys.stderr = open(DEST_DIR+"/"+str(os.getpid()) + ".err", "w")
        # redirect standard output: 
        sys.stdout = open(DEST_DIR+"/"+str(os.getpid()) + ".out", "w")
    else:
        logger = logging.getLogger(__name__)
        
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
        
    d = DispersyInstance(DEST_DIR, SWIFT_BINPATH, work_dir=WORK_DIR, sqlite_database=SQLITE_DATABASE, 
                         swift_work_dir=args.swift_work_dir, addresses=addresses, ports=ports, directory=args.directory, 
                         files=args.files, run_time=TOTAL_RUN_TIME)
    d.run()
    