'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import binascii
import random
import subprocess
import sys
import os
import json
from collections import defaultdict
from threading import RLock, currentThread, Thread, Event

from src.logger import get_logger
from Tribler.Core.simpledefs import VODEVENT_START, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Core.Swift.SwiftProcess import SwiftProcess, DONE_STATE_WORKING, DONE_STATE_SHUTDOWN,\
    DONE_STATE_EARLY_SHUTDOWN, DEBUG

from src.address import Address
from src.definitions import LIBEVENT_LIBRARY
import socket

try:
    os.environ["LD_LIBRARY_PATH"]
except KeyError:
    os.environ["LD_LIBRARY_PATH"] = LIBEVENT_LIBRARY

logger = get_logger(__name__)

class MySwiftProcess(SwiftProcess):
    
    def __init__(self, binpath, workdir, zerostatedir, listenaddrs, httpgwport, cmdgwport, spmgr, gateways={}):
        # Called by any thread, assume sessionlock is held
        self.splock = RLock()
        self.binpath = binpath
        self.workdir = workdir
        self.zerostatedir = zerostatedir
        self.spmgr = spmgr
        self.listenaddrs = []
        self.confirmedaddrs = []

        # Main UDP listen socket
        if listenaddrs is None:
            self.listenaddrs = []
        else:
            self.listenaddrs = listenaddrs
        
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
#         args.append("-D" + self.workdir + "/channeldebug")
        if self.listenaddrs: # In case there is nothing to listen too, either None or []
            args.append("-l")  # listen
            addrs = ""
            for l in self.listenaddrs:
                addrs += str(l) + ","
            args.append(addrs[:-1]) # Remove last comma
        
        if len(gateways.items()) > 0:
            args.append("-R")
            gs = ""
            for i, g in gateways.iteritems():
                gs += i + "=" + g + ","
            args.append(gs[:-1])
        
        args.append("-c")  # command port
        args.append("127.0.0.1:" + str(self.cmdport))
#         args.append("-g")  # HTTP gateway port
#         args.append("127.0.0.1:" + str(self.httpport))
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
        
        # Endpoint callbacks
        self._sockaddr_info_callback = None
        self._swift_restart_callback = None
        self._tcp_connection_open_callback = None
        
        self.roothash2dl = {}
        self.donestate = DONE_STATE_WORKING  # shutting down
        self.fastconn = None

        # callbacks for when swift detect a channel close
        self._channel_close_callbacks = defaultdict(list)

        # Only warn once when TUNNELRECV messages are received without us having a Dispersy endpoint.  This occurs after
        # Dispersy shutdown
        self._warn_missing_endpoint = True
        
        if not os.path.exists(self.workdir):
            os.mkdir(self.workdir)

        # See also SwiftDef::finalize popen
        # We would really like to get the stdout and stderr without creating a new thread for them.
        # However, windows does not support non-files in the select command, hence we cannot integrate
        # these streams into the FastI2I thread
        # A proper solution would be to switch to twisted for the communication with the swift binary
        self.popen = subprocess.Popen(args, cwd=self.workdir, creationflags=creationflags, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # This event must be set when is verified that swift is running and the cmdgw is up
        self._swift_running = Event()

        def read_and_print(socket):
            prefix = currentThread().getName() + ":"
            while True:
                line = socket.readline()
                self.read_and_print_out(line)
                if not line:
                    print >> sys.stderr, prefix, "readline returned nothing quitting"
                    # Most of the time the socket will throw an error as well, but not always
                    self.connection_lost(self.get_cmdport(), output_read=True)
                    break
                print >> sys.stderr, prefix, line.rstrip()
        self.popen_outputthreads = [Thread(target=read_and_print, args=(self.popen.stdout,), name="SwiftProcess_%d_stdout" % self.popen.pid), 
                                    Thread(target=read_and_print, args=(self.popen.stderr,), name="SwiftProcess_%d_stderr" % self.popen.pid)]
        [thread.start() for thread in self.popen_outputthreads]

                
    def read_and_print_out(self, line):
        # As soon as a TCP connection has been made, will the FastI2I be allowed to start
        line.strip()
        listenstr = "swift::Listen addr" 
        if line.find("Creating new TCP listener") != -1:
            self._swift_running.set()
        elif line.find(listenstr) != -1:
            addrstr = line[len(listenstr):]
            saddr = Address.unknown(addrstr)
            logger.debug("Found listen address %s", saddr)
            if saddr != Address():
                self.confirmedaddrs.append(saddr)
                if self._sockaddr_info_callback:
                    self._sockaddr_info_callback(saddr, 0)
            
    def start_cmd_connection(self):
        # Wait till Libswift is actually ready to create a TCP connection
        # TODO: Set timeout so that endpoint can make a new attempt at starting Swift
        def wait_to_start():
            while not self._swift_running.is_set():
                self._swift_running.wait()
            SwiftProcess.start_cmd_connection(self)
            if self.fastconn is not None and self._tcp_connection_open_callback is not None:
                self._tcp_connection_open_callback()
            else:
                logger.debug("TCP connection failed")
        
        t = Thread(target=wait_to_start)
        t.setDaemon(True) # This thread should die when main is quit
        t.start()
        # TODO: Should this thread be cleaned up somewhere?
    
    def set_on_swift_restart_callback(self, callback):
        self._swift_restart_callback = callback
        
    def set_on_tcp_connection_callback(self, callback):
        self._tcp_connection_open_callback = callback
        
    def set_on_sockaddr_info_callback(self, callback):
        self._sockaddr_info_callback = callback
    
    def i2ithread_readlinecallback(self, ic, cmd):
        logger.debug("CMD IN: %s", cmd)
        if self.donestate != DONE_STATE_WORKING:
            return

        words = cmd.split()
        assert all(isinstance(word, str) for word in words)
        
        if words[0] == "TUNNELRECV":
            address, session = words[1].split("/")
            host, port = address.split(":")
            port = int(port)
            session = session.decode("HEX")
            length = int(words[2])
            incoming_addr = 0 # None port numbers are ignored
            if len(words) > 3:
                incoming_addr = Address.unknown(words[3])

            # require LENGTH bytes
            if len(ic.buffer) < length:
                return length - len(ic.buffer)

            data = ic.buffer[:length]
            ic.buffer = ic.buffer[length:]

            try:
                self.roothash2dl["dispersy-endpoint"].i2ithread_data_came_in(session, (host, port), data, incoming_addr)
            except KeyError:
                if self._warn_missing_endpoint:
                    self._warn_missing_endpoint = False
                    print >> sys.stderr, "sp: Dispersy endpoint is not available"
                    
        elif words[0] == "SOCKETINFO":
            saddr = Address.unknown(words[1])
            state = -1
            try:
                state = int(words[2])
            except ValueError:
                pass
            if saddr != Address():
                if state == 0 and not saddr in self.confirmedaddrs:
                    self.confirmedaddrs.append(saddr)
                if self._sockaddr_info_callback:
                    self._sockaddr_info_callback(saddr, state)

        else:
            roothash = binascii.unhexlify(words[1])

            if words[0] == "ERROR":
                if words[2] == "bad" and words[3] == "swarm": # bad swarm does not lead to shutdown!!!!
                    logger.debug("This is a bad swarm %s", words[1])
                    d = self.roothash2dl.get(roothash, None)
                    if d is not None:
                        try:
                            d._bad_swarm_callback(roothash) # TODO: Callback should be directly, not via downloadimpl
                        except AttributeError:
                            pass
                else:
                    self.connection_lost(self.get_cmdport(), error=words[2:])

            self.splock.acquire()
            try:
                d = self.roothash2dl[roothash]
            except KeyError:
                logger.debug("Unknown roothash %s", roothash)
                return
            finally:
                self.splock.release()

            # Hide NSSA interface for SwiftDownloadImpl
            if words[0] == "INFO":  # INFO HASH status dl/total
                dlstatus = int(words[2])
                pargs = words[3].split("/")
                dynasize = int(pargs[1])
                if dynasize == 0:
                    progress = 0.0
                else:
                    progress = float(pargs[0]) / float(pargs[1])
                dlspeed = float(words[4])
                ulspeed = float(words[5])
                numleech = int(words[6])
                numseeds = int(words[7])
                contentdl = 0  # bytes
                contentul = 0  # bytes
                if len(words) > 8:
                    contentdl = int(words[8])
                    contentul = int(words[9])
                d.i2ithread_info_callback(dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul)
            elif words[0] == "PLAY":
                # print >>sys.stderr,"sp: i2ithread_readlinecallback: Got PLAY",cmd
                httpurl = words[2]
                d.i2ithread_vod_event_callback(VODEVENT_START, httpurl)
            elif words[0] == "MOREINFO":
                jsondata = cmd[len("MOREINFO ") + 40 + 1:]
                midict = json.loads(jsondata)
                d.i2ithread_moreinfo_callback(midict)
            elif words[0] == "ERROR":
                d.i2ithread_info_callback(DLSTATUS_STOPPED_ON_ERROR, 0.0, 0, 0.0, 0.0, 0, 0, 0, 0)                    
            elif words[0] == "CHANNELCLOSED":
                saddr = Address.unknown(words[2])
                paddr = Address.unknown(words[3])
                if d._channel_closed_callback is not None:
                    d._channel_closed_callback(roothash, saddr, paddr)
                
    
    def write(self, msg):
        if self.is_running():
            logger.debug("CMD OUT: %s", msg[0:100])
            try:
                SwiftProcess.write(self, msg)
            except (AttributeError, socket.error):
                logger.warning("FastConnection is down")
            
    def connection_lost(self, port, error=None, output_read=False):
        if self.donestate != DONE_STATE_WORKING:
            # Only if it is still running should we consider restarting swift
            return
        logger.debug("CONNECTION LOST")
        self.donestate = DONE_STATE_SHUTDOWN # Mark as done for
        if self._swift_restart_callback is not None:
            self._swift_restart_callback(error)
        
    def send_tunnel(self, session, address, data, addr=Address()):
        if addr.port == 0:
            SwiftProcess.send_tunnel(self, session, address, data)
        else:
            self.write("TUNNELSEND %s:%d/%s %d %s\r\n" % (address[0], address[1], session.encode("HEX"), len(data), str(addr)))
            self.write(data)
            
    def is_running(self):
        return (self.fastconn is not None and self.donestate != DONE_STATE_SHUTDOWN
                and self._swift_running.is_set() and self.is_alive())

    def is_ready(self):
        # TODO: Make sure that fastconn is not busy writing
        return self.is_running();
    
    def add_peer(self, d, addr, saddr):
        self.splock.acquire()
        try:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return
            
            addrstr = None
            if addr is not None:
                addrstr = str(addr)
            saddrstr = None
            if saddr is not None:
                saddrstr = str(saddr)
            roothash_hex = d.get_def().get_roothash_as_hex()
            self.send_peer_addr(roothash_hex, addrstr, saddrstr)
        finally:
            self.splock.release()

    def send_peer_addr(self, roothash_hex, addrstr, saddrstr):
        # assume splock is held to avoid concurrency on socket
        cmd = 'PEERADDR ' + roothash_hex + ' '
        if addrstr is not None:
            cmd += addrstr
        else:
            logger.warning("You cannot add a peer without supplying one!")
        if saddrstr is not None:
            cmd += ' ' + saddrstr
        cmd += '\r\n'
        self.write(cmd)

    def add_socket(self, saddr, overwrite=False):
        logger.debug("Add socket %s %s",saddr, saddr.interface)
        self.splock.acquire()
        try:
            if self.donestate != DONE_STATE_WORKING or not self.is_alive():
                return
            
            if saddr in self.listenaddrs:
                logger.debug("Address already in use %s", saddr)
                if not overwrite:
                    return
                else: # Remove from listenaddrs and put it back in. Remove also from confirmedaddrs if there
                    self.listenaddrs.remove(saddr)
                    if saddr in self.confirmedaddrs:
                        self.confirmedaddrs.remove(saddr)
                    self.listenaddrs.append(saddr)                    
            else:
                # saddr is of instance Address
                self.listenaddrs.append(saddr)

            saddrstr = str(saddr)
            if saddr.interface is not None:
                self.send_add_socket(saddrstr, saddr.interface.name, saddr.interface.gateway, saddr.interface.device)
            else:
                self.send_add_socket(saddrstr)
        finally:
            self.splock.release()
            
    def send_add_socket(self, saddrstr, if_name=None, gateway=None, device=None):
        # assume splock is held to avoid concurrency on socket
        cmd = 'ADDSOCKET ' + saddrstr
        if gateway is not None:
            cmd+= ' ' + gateway 
        else:
            cmd+= ' 0.0.0.0'
        if if_name is not None:
            cmd+= ' ' + if_name
        if device is not None:
            cmd += ' ' + device
        cmd += '\r\n'
        self.write(cmd)
        
    def set_pex(self, roothash, enable):
        self.send_pex(roothash, enable)
        
    def send_pex(self, roothash_hex, enable):
        onoff = "0"
        if enable:
            onoff = "1"
        self.write('PEX ' + roothash_hex + ' ' + onoff + '\r\n')
