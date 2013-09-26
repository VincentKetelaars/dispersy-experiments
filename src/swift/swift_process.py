'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import binascii
import random
import subprocess
import sys
from collections import defaultdict
from threading import RLock, currentThread, Thread, Event

from Tribler.Core.Swift.SwiftProcess import SwiftProcess, DONE_STATE_WORKING,\
    DONE_STATE_SHUTDOWN

from dispersy.logger import get_logger
logger = get_logger(__name__)

class MySwiftProcess(SwiftProcess):
    '''
    
    '''
    
    def __init__(self, binpath, workdir, zerostatedir, listenports, httpgwport, cmdgwport, spmgr):
        # Called by any thread, assume sessionlock is held
        self.splock = RLock()
        self.binpath = binpath
        self.workdir = workdir
        self.zerostatedir = zerostatedir
        self.spmgr = spmgr
        self.listenports = []

        # Main UDP listen socket
        if listenports is None:
            self.listenport = random.randint(10001, 10999)
        else:
            self.listenports = listenports
            self.listenport = listenports[0]
        
        # NSSA control socket
        if cmdgwport is None:
            self.cmdport = random.randint(11001, 11999)
        else:
            self.cmdport = cmdgwport
        # content web server
        if httpgwport is None:
            self.httpport = random.randint(12001, 12999)
        else:
            self.httpport = httpgwport

        # Security: only accept commands from localhost, enable HTTP gw,
        # no stats/webUI web server
        args = []
        # Arno, 2012-07-09: Unicode problems with popen
        args.append(self.binpath.encode(sys.getfilesystemencoding()))

        # Arno, 2012-05-29: Hack. Win32 getopt code eats first arg when Windows app
        # instead of CONSOLE app.
        args.append("-j")
#         args.append("-B") # Set Channel debug_file
        args.append("-l")  # listen port
        ports = ""
        for l in self.listenports:
            ports += "0.0.0.0:" + str(l) +","
        args.append(ports[:-1]) # Remove last comma
        args.append("-c")  # command port
        args.append("127.0.0.1:" + str(self.cmdport))
        args.append("-g")  # HTTP gateway port
        args.append("127.0.0.1:" + str(self.httpport))
        args.append("-w")
        if zerostatedir is not None:
            if sys.platform == "win32":
                # Swift on Windows expects command line arguments as UTF-16.
                # popen doesn't allow us to pass params in UTF-16, hence workaround.
                # Format = hex encoded UTF-8
                args.append("-3")
                zssafe = binascii.hexlify(zerostatedir.encode("UTF-8"))
                args.append(zssafe)  # encoding that swift expects
            else:
                args.append("-e")
                args.append(zerostatedir)
            args.append("-T")  # zero state connection timeout
            args.append("180")  # seconds
        # args.append("-B")  # Enable debugging on swift

        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            creationflags = 0

        # See also SwiftDef::finalize popen
        # We would really like to get the stdout and stderr without creating a new thread for them.
        # However, windows does not support non-files in the select command, hence we cannot integrate
        # these streams into the FastI2I thread
        # A proper solution would be to switch to twisted for the communication with the swift binary
        self.popen = subprocess.Popen(args, cwd=workdir, creationflags=creationflags, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Callback for read_and_print
        self.read_and_print_callback = self.read_and_print_out
        
        # This event must be set when is verified that swift is running
        self._swift_running = Event()

        def read_and_print(socket):
            prefix = currentThread().getName() + ":"
            while True:
                line = socket.readline()
                self.read_and_print_callback(line)
                if not line:
                    print >> sys.stderr, prefix, "readline returned nothing quitting"
                    break
                print >> sys.stderr, prefix, line.rstrip()
        self.popen_outputthreads = [Thread(target=read_and_print, args=(self.popen.stdout,), name="SwiftProcess_%d_stdout" % self.listenport), Thread(target=read_and_print, args=(self.popen.stderr,), name="SwiftProcess_%d_stderr" % self.listenport)]
        [thread.start() for thread in self.popen_outputthreads]

        self.roothash2dl = {}
        self.donestate = DONE_STATE_WORKING  # shutting down
        self.fastconn = None

        # callbacks for when swift detect a channel close
        self._channel_close_callbacks = defaultdict(list)

        # Only warn once when TUNNELRECV messages are received without us having a Dispersy endpoint.  This occurs after
        # Dispersy shutdown
        self._warn_missing_endpoint = True
        
    def read_and_print_out(self, line):
        if line.find("TCP") != -1:
            self._swift_running.set()
            
    def start_cmd_connection(self):
        while not self._swift_running.is_set():
            self._swift_running.wait()
        SwiftProcess.start_cmd_connection(self)
    
    def set_on_swift_restart_callback(self, callback):
        self.swift_restart_callback = callback
    
    def i2ithread_readlinecallback(self, ic, cmd):
        logger.debug("CMD IN: %s", cmd)
        words = cmd.split()
        if words[0] == "ERROR":
            self.connection_lost(self.get_cmdport(), error=True)
        return SwiftProcess.i2ithread_readlinecallback(self, ic, cmd)
    
    def write(self, msg):
        if self.fastconn is not None or self.donestate == DONE_STATE_SHUTDOWN or not self._swift_running.is_set():
            try:
                SwiftProcess.write(self, msg)
            except:
                logger.warning("FastConnection is down")
            
    def connection_lost(self, port, error=False):
        logger.debug("CONNECTION LOST")
        self.swift_restart_callback()

            