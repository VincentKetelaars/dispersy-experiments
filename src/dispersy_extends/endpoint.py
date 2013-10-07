'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''

from os import urandom, makedirs
from os.path import isfile, dirname, exists, basename, getmtime
from datetime import datetime
from threading import Thread, Event
from sets import Set
import binascii
import socket
import time
import logging

from dispersy.endpoint import Endpoint, TunnelEndpoint
from dispersy.statistics import Statistics
from dispersy.candidate import WalkCandidate
from dispersy.logger import get_logger
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.Swift.SwiftProcess import DONE_STATE_EARLY_SHUTDOWN

from src.swift.swift_process import MySwiftProcess
from src.swift.swift_download_config import FakeSession, FakeSessionSwiftDownloadImpl
from src.download import Download
from src.definitions import SLEEP_TIME, HASH_LENGTH

logger = get_logger(__name__)

class NoEndpointAvailableException(Exception):
    pass

class EndpointDownloads(object):
    
    def __init__(self):
        self.added_peers = Set()
        self.downloads = {}

class EndpointStatistics(Statistics):
    
    def __init__(self):
        self.start_time = datetime.now()
        self.is_alive = False # The endpoint is alive between open and close
        self.id = urandom(16)
        self.known_addresses = Set()
        
    def update(self):
        pass

class MultiEndpoint(TunnelEndpoint, EndpointStatistics, EndpointDownloads):
    '''
    MultiEndpoint holds a list of Endpoints, which can be added dynamically. 
    The status of each of these Endpoints will be checked periodically (push / pull?). 
    According to the available Endpoints and their status,
    data will be send via those as to provide the fastest means of delivering data. 
    '''

    def __init__(self, swift_process):
        self._thread_stop_event = Event()
        self._resetting = False
        self._endpoint = None
        self.swift_endpoints = []
        TunnelEndpoint.__init__(self, swift_process)
        EndpointStatistics.__init__(self)
        EndpointDownloads.__init__(self)
        
        if swift_process:
            self._swift.set_on_swift_restart_callback(self.restart_swift)
            for p in self._swift.listenports:
                self.add_endpoint(SwiftEndpoint(swift_process, p))      
    
    def get_address(self):
        if self._endpoint is None:
            return ("0.0.0.0", -1)
        else:
            return self._endpoint.get_address()
        
    def get_all_addresses(self):
        return list(endpoint.get_address() for endpoint in self.swift_endpoints)
    
    def send(self, candidates, packets):
        self.update_known_addresses(candidates, packets)
        self.determine_endpoint(known_addresses=self.known_addresses, subset=True)
        self._endpoint.send(candidates, packets)
        self._send_introduction_requests_to_unknown(candidates, packets)
            
    def open(self, dispersy):
        ret = TunnelEndpoint.open(self, dispersy)
        self._swift.start_cmd_connection()
        ret = ret and all([x.open(dispersy) for x in self.swift_endpoints])
                    
        self.is_alive = True   
        
        self._thread_loop = Thread(target=self._loop)
        self._thread_loop.daemon = True
        self._thread_loop.start()
        return ret
    
    def close(self, timeout=0.0):
        logger.info("TOTAL %s: down %d, send %d, up %d, cur %d", self.get_address(), self.total_down, self.total_send, self.total_up, self.cur_sendqueue)
        self.is_alive = False
        self._thread_stop_event.set()
        self._thread_loop.join()
        self._swift.remove_download(self, True, True)
        self._swift.early_shutdown()
        # TODO: Try clean and fast shutdown
        self._swift.network_shutdown() # Kind of harsh, so make sure downloads are handled
        # Try the sockets to see if they are in use
        if not try_sockets(self._swift.listenports, timeout=1.0):
            logger.warning("Socket(s) is/are still in use")
        # Note that the swift_endpoints are still available after return, although closed
        return all([x.close(timeout) for x in self.swift_endpoints]) and super(TunnelEndpoint, self).close(timeout)
    
    def add_endpoint(self, endpoint):
        assert isinstance(endpoint, Endpoint), type(endpoint)
        self.swift_endpoints.append(endpoint)
        if len(self.swift_endpoints) == 1:
            self._endpoint = endpoint
            
    def remove_endpoint(self, endpoint):
        """
        Remove endpoint.
        """
        assert isinstance(endpoint, Endpoint), type(endpoint)
        for e in self.swift_endpoints:
            if e == endpoint:
                e.close()
                self.swift_endpoints.remove(e)
                if self._endpoint == e:
                    self.determine_endpoint()
                break
    
    def _lowest_sendqueue(self):
        """
        Return the endpoint with the lowest sendqueue.
        If the sendqueues are equally long, the first in the list is returned.
        """
        e = self.swift_endpoints[0]
        for x in self.swift_endpoints:
            if e.cur_sendqueue > x.cur_sendqueue: # First check is unnecessarily with itself 
                e = x
        return e
    
    def _next_endpoint(self):
        i = -1
        for x in self.swift_endpoints:
            if x == self._endpoint:
                return self.swift_endpoints[i % len(self.swift_endpoints)]
            i+=1
        return self._endpoint
    
    def determine_endpoint(self, swift=False, known_addresses=None, subset=True):
        """
        The endpoint that will take care of the task at hand, will be chosen here. 
        The chosen endpoint will be assigned to self._endpoint
        If no appropriate endpoint is found, the current endpoint will remain.
        """
        
        def recur(endpoints, swift=False, known_addresses=None, subset=True):
            if endpoints == Set():
                return self._endpoint
            
            endpoint = None
            tried = Set()
            if known_addresses is not None:
                for e in endpoints:
                    tried.add(e)
                    if subset and Set(known_addresses).issubset(e.known_addresses):
                        endpoint = e
                    if not subset and not Set(known_addresses).issubset(e.known_addresses):
                        endpoint = e
                
                if endpoint is None:
                    return self._endpoint
            
            else:
                endpoint = endpoints.pop()
                tried.add(endpoint)
            
            if swift and not isinstance(endpoint, SwiftEndpoint):
                recur(tried.difference(endpoints), swift, known_addresses, subset)
                
            return endpoint  
        
        if (len(self.swift_endpoints) == 0):
            self._endpoint = None
        elif (len(self.swift_endpoints) > 1):
            self._endpoint = recur(Set(self.swift_endpoints), swift, known_addresses, subset)
        else:
            self._endpoint = self.swift_endpoints[0]
    
    def add_file(self, filename, roothash):
        """
        This method lets the swiftprocess know that an additional file is available.
        
        @param filename: The absolute path of the file
        @param roothash: The roothash of this file
        """        
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys() and len(roothash) == HASH_LENGTH / 2: # Check if not already added, and if the unhexlified roothash has the proper length
            logger.debug("Add file %s with roothash %s", filename, roothash)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(filename)

            self.update_known_downloads(roothash, filename, d, seed=True)
            
            self._swift.start_download(d)
            self._swift.set_moreinfo_stats(d, True)
            
            self.distribute_all_hashes_to_peers() # After adding the file, directly add the peer as well
        
    def distribute_all_hashes_to_peers(self):
        """
        All known addresses and downloads are added.
        """
        for roothash in self.downloads.keys():
            for addr in self.known_addresses:
                self.add_peer(addr, roothash)
    
    def add_peer(self, addr, roothash):                
        """
        Send message to the swift process to add a peer.
        
        @param addr: address of the peer: (ip, port)
        @param roothash: Must be unhexlified roothash
        """
        if roothash is not None and not (addr, roothash) in self.added_peers:
            d = self.retrieve_download_impl(roothash)
            if d is not None:
                logger.debug("Add peer %s with roothash %s ", addr, roothash)
                self.downloads[roothash].add_peer(addr)
                self._swift.add_peer(d, addr)
                self.added_peers.add((addr, roothash))
            
    def start_download(self, filename, directories, roothash, dest_dir, addr=None):
        """
        This method lets the swift instance know that it should download the file that comes with this roothash.
        
        @param filename: The name the file will get
        @param roothash: hash to locate swarm
        @param dest_dir: The folder the file will be put
        """
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys():
            logger.info("Start download of %s with roothash %s", filename, roothash)
            dir_ = dest_dir + "/" + directories
            if not exists(dir_):
                makedirs(dir_)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(dir_ + basename(filename))
            self._swift.start_download(d)
            self._swift.set_moreinfo_stats(d, True)
            
            self.update_known_downloads(roothash, d.get_dest_dir(), d, address=addr, download=True)
            
    def _send_introduction_requests_to_unknown(self, candidates, packets):
        meta = self._dispersy.convert_packet_to_meta_message(packets[0], load=False, auto_load=False)
        addrs = Set([c.get_destination_address(self._dispersy.wan_address) for c in candidates])
        for e in self.swift_endpoints:
            if meta.name.find("dispersy") == -1 or e != self._endpoint:
                diff = addrs.difference(e.known_addresses)
                for a in diff:
                    logger.debug("%s sends introduction request to %s", e.get_address(), a)
                    e.known_addresses.add(a)
                    self._dispersy._callback.call(self._dispersy.create_introduction_request, 
                                    (meta._community, WalkCandidate(a, True, a, a, u"unknown"),True,True))
        
    def download_is_ready_callback(self, roothash):
        """
        This method is called when a download is ready
        
        @param roothash: Identifier of the download
        """
        download = self.downloads[roothash]
        if download.set_finished() and not download.seeder():
            if not download.moreinfo:
                self.clean_up_files(roothash, True, False)
                
    def moreinfo_callback(self, roothash):
        """
        This method is called whenever more info comes in.
        In case the download is finished and not supposed to seed, clean up the files
        
        @param roothash: The roothash to which the more info is related
        """
        download = self.downloads[roothash]
        if download.is_finished() and not download.seeder():
            self.clean_up_files(roothash, True, False)
        
    def i2ithread_data_came_in(self, session, sock_addr, data, incoming_port=0):
        if isinstance(sock_addr, tuple):
            self.known_addresses.update([sock_addr])
            
        for e in self.swift_endpoints:
            if e.port == incoming_port:
                e.i2ithread_data_came_in(session, sock_addr, data)
                return
        # In case the incoming_port number does not match any of the endpoints
        TunnelEndpoint.i2ithread_data_came_in(self, session, sock_addr, data)
        
    def create_download_impl(self, roothash):
        """
        Create DownloadImpl
        
        @param roothash: Roothash of a file
        """
        sdef = SwiftDef(roothash=roothash)
        # This object must have: get_def, get_selected_files, get_max_speed, get_swift_meta_dir
        d = FakeSessionSwiftDownloadImpl(FakeSession(), sdef, self._swift)
        d.setup()
        # get_selected_files is initialized to empty list
        # get_max_speed for UPLOAD and DOWNLOAD are set to 0 initially (infinite)
        d.set_swift_meta_dir(None)
        d.set_download_ready_callback(self.download_is_ready_callback)
        d.set_moreinfo_callback(self.moreinfo_callback)
        return d
        
    def retrieve_download_impl(self, roothash):
        """
        Retrieve DownloadImpl with roothash
        
        @return: DownloadImpl, otherwise None
        """
        self._swift.splock.acquire()
        d = None
        try:
            d = self._swift.roothash2dl[roothash]
        except:
            logger.error("Could not retrieve downloadimpl from roothash2dl")
        finally:
            self._swift.splock.release()
        return d
    
    def restart_swift(self):
        """
        Restart swift if the endpoint is still alive, generally called when an Error occurred in the swift instance
        After swift has been terminated, a new process starts and previous downloads and their peers are added.
        """
        if self.is_alive and not self._resetting:
            self._resetting = True
            logger.info("Resetting swift")
            # Make sure that the current swift instance is gone
            self._swift.donestate = DONE_STATE_EARLY_SHUTDOWN
            self._swift.network_shutdown()
            self.added_peers = Set() # Reset the peers added before shutdown
            
            # Try the sockets to see if they are in use
            if not try_sockets(self._swift.listenports):
                logger.warning("Socket(s) is/are still in use")
            
            # Make sure not to make the same mistake as what let to this
            # Any roothash added twice will create an error, leading to this. 
            self._swift = MySwiftProcess(self._swift.binpath, self._swift.workdir, None, self._swift.listenports, None, None, None)
            self._swift.set_on_swift_restart_callback(self.restart_swift) # Normally in init
            self._swift.add_download(self) # Normally in open
            # We have to make sure that swift has already started, otherwise the tcp binding might fail
            self._swift.start_cmd_connection() # Normally in open
            for h, d in self.downloads.iteritems():
                self._swift.start_download(d.downloadimpl)
                for addr in d.peers():
                    if not (addr, h) in self.added_peers:
                        self._swift.add_peer(d.downloadimpl, addr)
                        self.added_peers.add((addr, h))
            self._resetting = False
    
    def _loop(self):
        while not self._thread_stop_event.is_set():
            self._thread_stop_event.wait(SLEEP_TIME)
            for _, D in self.downloads.iteritems():
                if D.downloadimpl is not None:
                    (_, stats, seeding_stats, _) = D.downloadimpl.network_get_stats(None)
                    logger.debug("INFO: %s, %s\r\nSEEDERS: %s\r\nPEERS: %s \r\nUPLOADED: %s\r\nDOWNLOADED: %s\r\nSEEDINGSTATS: %s" + 
                                "\r\nUPSPEED: %s\r\nDOWNSPEED: %s\r\nFRACTION: %s\r\nSPEW: %s", 
                                self.get_address(), D.roothash_as_hex(), stats["stats"].numSeeds, stats["stats"].numPeers, stats["stats"].upTotal, 
                                stats["stats"].downTotal, seeding_stats, stats["up"], stats["down"], stats["frac"], stats["spew"])
    
    def clean_up_files(self, roothash, rm_state, rm_download):
        """
        Remove download
        
        @param roothash: roothash to find the correct DownloadImpl
        @param rm_state: Remove state boolean
        @param rm_download: Remove download file boolean
        """
        d = self.retrieve_download_impl(roothash)
        if d is not None:
            self._swift.remove_download(d, rm_state, rm_download)
        self.added_peers = Set([p for p in self.added_peers if p[1] != roothash])
        
    def update_known_addresses(self, candidates, packets):
        ka_size = len(self.known_addresses)
        self.known_addresses.update(list(c.sock_addr for c in candidates if isinstance(c.sock_addr, tuple)))
        if ka_size < len(self.known_addresses):
            self.distribute_all_hashes_to_peers()
            
    def update_known_downloads(self, roothash, filename, download_impl, address=None, seed=False, download=False):
        # Know about all hashes that go through this endpoint
        self.downloads[roothash] = Download(roothash, filename, download_impl, seed=seed, download=download)
        self.downloads[roothash].moreinfo = True
        self.downloads[roothash].add_peer(address)
    
class SwiftEndpoint(TunnelEndpoint, EndpointStatistics):
    
    def __init__(self, swift_process, port):
        super(SwiftEndpoint, self).__init__(swift_process) # Dispersy and session code 
        EndpointStatistics.__init__(self)
        self.port = port
        
    def open(self, dispersy):
        self.is_alive = True
        return Endpoint.open(self, dispersy) # Dispersy, but not add_download(self)
        
    def close(self, timeout=0.0):
        self.is_alive = False
        self._swift = None
        return super(TunnelEndpoint, self).close(timeout)
    
    def get_address(self):
        # Dispersy retrieves the local ip
        if self._dispersy is not None:
            return (self._dispersy.lan_address[0],self.port)
        else:
            return (TunnelEndpoint.get_address(self)[0], self.port)
    
    def send(self, candidates, packets):
        if self._swift.is_alive():
            if any(len(packet) > 2**16 - 60 for packet in packets):
                raise RuntimeError("UDP does not support %d byte packets" % len(max(len(packet) for packet in packets)))

            self._total_up += sum(len(data) for data in packets) * len(candidates)
            self._total_send += (len(packets) * len(candidates))
            wan_address = self._dispersy.wan_address
    
            self._swift.splock.acquire()
            try:
                for candidate in candidates:
                    sock_addr = candidate.get_destination_address(wan_address)
                    assert self._dispersy.is_valid_address(sock_addr), sock_addr
    
                    for data in packets:
                        if logger.isEnabledFor(logging.DEBUG):
                            try:
                                name = self._dispersy.convert_packet_to_meta_message(data, load=False, auto_load=False).name
                            except:
                                name = "???"
                            logger.debug("%30s -> %15s:%-5d %4d bytes", name, sock_addr[0], sock_addr[1], len(data))
                            self._dispersy.statistics.dict_inc(self._dispersy.statistics.endpoint_send, name)
                        self._swift.send_tunnel(self._session, sock_addr, data, self.port)
    
                # return True when something has been send
                return candidates and packets
    
            finally:
                self._swift.splock.release()
                
            self.known_addresses.update(list(c.sock_addr for c in candidates if isinstance(c.sock_addr, tuple)))      
        
    def i2ithread_data_came_in(self, session, sock_addr, data):
        if isinstance(sock_addr, tuple):
            self.known_addresses.update([sock_addr])
        TunnelEndpoint.i2ithread_data_came_in(self, session, sock_addr, data)
                    
                    
def get_hash(filename, swift_path):
    """
    Determine the roothash of this file. If the mbinmap file already exists, 
    and the actual file has not been edited later than this mbinmap file,
    we can retrieve the roothash from the second line of this file.
    
    @param filename: The absolute path of the file
    @param swift_path: The absolute path to the swift binary file
    @return roothash in readable hexadecimal numbers
    """
    if isfile(filename):
        mbinmap = filename + ".mbinmap"
        roothash = None
        if isfile(mbinmap) and getmtime(filename) < getmtime(mbinmap):
            try:
                with file(mbinmap) as f:
                    f.readline()
                    hashline = f.readline()
                    roothash = hashline.strip().split(" ")[2]
            except Exception:
                logger.exception("Reading mbinmap failed")
        if roothash is not None:
            logger.debug("Found roothash in mbinmap: %s", roothash)
            return roothash
        sdef = SwiftDef()
        sdef.add_content(filename)
        sdef.finalize(swift_path, destdir=dirname(filename))            
        # returning get_roothash() gives an error somewhere (perhaps message?)
        return sdef.get_roothash_as_hex()
    
def try_sockets(ports, timeout=1.0):
    """
    This method returns when all UDP sockets are free to use, or if the timeout is reached
    
    @param ports: List of local socket ports
    @param timeout: Try until timeout time has been exceeded
    @return: True if the sockets are free
    """
    event = Event()
    t = time.time()        
    while not event.is_set() and t + timeout > time.time():
        if all([try_socket(p) for p in ports]):
            event.set()
        event.wait(0.1)
        
    return all([try_socket(p) for p in ports])
    
def try_socket(port):
    """
    This methods tries to bind to an UDP socket.
    
    @param port: Local socket port
    @return: True if socket is free to use
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("", port))
        return True
    except Exception:
        logger.exception("Bummer, socket is still in use!")
        return False
    finally:
        s.close()
    