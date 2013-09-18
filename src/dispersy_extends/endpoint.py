'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''

from os import urandom, makedirs
from os.path import isfile, dirname, exists, basename
from datetime import datetime
from threading import Thread, Event
from sets import Set
import binascii

from dispersy.endpoint import Endpoint, TunnelEndpoint
from dispersy.statistics import Statistics
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.Swift.SwiftProcess import DONE_STATE_EARLY_SHUTDOWN

from src.swift.swift_process import MySwiftProcess
from src.swift.swift_download_config import FakeSession, FakeSessionSwiftDownloadImpl
from src.download import Download
from src.definitions import SLEEP_TIME, FILE_HASH_MESSAGE_NAME, HASH_LENGTH

import logging
logger = logging.getLogger(__name__)

class NoEndpointAvailableException(Exception):
    pass

class EndpointStatistics(Statistics):
    
    def __init__(self):
        self.start_time = datetime.now()
        self.is_alive = False # The endpoint is alive between open and close
        self.id = urandom(16)
        self.known_addresses = Set()
        self.added_peers = Set()
        self.downloads = {}
        
    def update(self):
        pass

class MultiEndpoint(Endpoint):
    '''
    MultiEndpoint holds a list of Endpoints, which can be added dynamically. 
    The status of each of these Endpoints will be checked periodically (push / pull?). 
    According to the available Endpoints and their status,
    data will be send via those as to provide the fastest means of delivering data. 
    '''

    def __init__(self):
        self._endpoints = []
        self._endpoint = None
        super(MultiEndpoint, self).__init__()
    
    def add_endpoint(self, endpoint):
        assert isinstance(endpoint, Endpoint), type(endpoint)
        self._endpoints.append(endpoint)
        if len(self._endpoints) == 1:
            self._endpoint = endpoint
            
    def remove_endpoint(self, endpoint):
        """
        Remove endpoint.
        """
        assert isinstance(endpoint, Endpoint), type(endpoint)
        for e in self._endpoints:
            if e == endpoint:
                e.close()
                self._endpoints.remove(e)
                if self._endpoint == e:
                    self.determine_endpoint()
                break
    
    def get_address(self):
        if self._endpoint is None:
            return ("0.0.0.0", -1)
        else:
            return self._endpoint.get_address()
        
    def get_all_addresses(self):
        return list(endpoint.get_address() for endpoint in self._endpoints)
    
    def send(self, candidates, packets):
        name = self._dispersy.convert_packet_to_meta_message(packets[0], load=False, auto_load=False).name
        if name == FILE_HASH_MESSAGE_NAME:
            for candidate in candidates:
                addr = candidate.get_destination_address(self._dispersy.wan_address)
                self.distribute_all_hashes_to_peer(addr)
        if name == "dispersy-introduction-request":
            for e in self._endpoints:
                e.send(candidates, packets)
        else:
            self.determine_endpoint(known_addresses=list(c.sock_addr for c in candidates), subset=True)
            self._endpoint.send(candidates, packets)
            
    def open(self, dispersy):
        self._dispersy = dispersy
        for x in self._endpoints:
            x.open(dispersy)
    
    def close(self, timeout=0.0):
        return all([x.close(timeout) for x in self._endpoints])
            
    def _lowest_sendqueue(self):
        """
        Return the endpoint with the lowest sendqueue.
        If the sendqueues are equally long, the first in the list is returned.
        """
        e = self._endpoints[0]
        for x in self._endpoints:
            if e.cur_sendqueue > x.cur_sendqueue: # First check is unnecessarily with itself 
                e = x
        return e
    
    def _next_endpoint(self):
        i = -1
        for x in self._endpoints:
            if x == self._endpoint:
                return self._endpoints[i % len(self._endpoints)]
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
        
        if (len(self._endpoints) == 0):
            self._endpoint = None
        elif (len(self._endpoints) > 1):
            self._endpoint = recur(Set(self._endpoints), swift, known_addresses, subset)
        else:
            self._endpoint = self._endpoints[0]
    
    def add_file(self, filename, roothash):
        """
        All endpoints are called with add_file
        """
        for e in self._endpoints:
            e.add_file(filename, roothash)
        
    def distribute_all_hashes_to_peer(self, addr):
        """
        All endpoints are called with add_peer
        """
        for e in self._endpoints:
            for h in e.downloads.keys():
                e.add_peer(addr, h)
            
    def start_download(self, filename, directories, roothash, dest_dir, addr=None):
        """
        All endpoints are called with start_download
        """
        for e in self._endpoints:
            e.start_download(filename, directories, roothash, dest_dir, addr)   
    
class SwiftEndpoint(TunnelEndpoint, EndpointStatistics):
    
    def __init__(self, swift_process, binpath):
        super(SwiftEndpoint, self).__init__(swift_process)
        EndpointStatistics.__init__(self)
        self._swift.set_on_swift_restart_callback(self.restart_swift)
        
        self._swift_path = binpath
        
        self._thread_stop_event = Event()
        self._resetting = False
        
    def open(self, dispersy):
        super(SwiftEndpoint, self).open(dispersy)
        self._swift.start_cmd_connection()
        self.is_alive = True
        
        self._thread_loop = Thread(target=self._loop)
        self._thread_loop.daemon = True
        self._thread_loop.start()
        
    def close(self, timeout=0.0):
        logger.info("TOTAL %s: down %d, send %d, up %d, cur %d", self.get_address(), self.total_down, self.total_send, self.total_up, self.cur_sendqueue)
        self._thread_stop_event.set()
        self._thread_loop.join()
        self.is_alive = False
        self._swift.remove_download(self, True, True)
        self._swift.early_shutdown()
        self._swift.network_shutdown() # Kind of harsh, so make sure downloads are handled
        return super(TunnelEndpoint, self).close(timeout)
        
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
    
    def get_address(self):
        # Dispersy retrieves the local ip
        if self._dispersy is not None:
            return (self._dispersy.lan_address[0],self._swift.get_listen_port())
        else:
            TunnelEndpoint.get_address(self)
    
    def send(self, candidates, packets):
        if self._swift.is_alive():
            TunnelEndpoint.send(self, candidates, packets)
            self.known_addresses.update(list(c.sock_addr for c in candidates if isinstance(c.sock_addr, tuple)))
        
    def add_file(self, filename, roothash):
        """
        This method lets the swiftprocess know that an additional file is available.
        
        @param filename: The absolute path of the file
        @param roothash: The roothash of this file
        """
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys() and len(roothash) == HASH_LENGTH / 2: # Check if not already added, and if the unhexlified roothash has the proper length
            d = self.create_download_impl(roothash)
            d.set_dest_dir(filename)

            self.downloads[roothash] = Download(roothash, filename, d, seed=True) # Know about all hashes that go through this endpoint
            self.downloads[roothash].moreinfo = True
            
            self._swift.start_download(d)
            self._swift.set_moreinfo_stats(d, True)
            
        
    def add_peer(self, addr, roothash=None):
        """
        Send message to the swift process to add a peer.
        
        @param addr: address of the peer: (ip, port)
        @param roothash: Must be unhexlified roothash
        """
        logger.debug("Add peer %s with roothash %s ", addr, roothash)
        if roothash is not None and not (addr, roothash) in self.added_peers:
            d = self.retrieve_download_impl(roothash)
            if d is not None:
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
        logger.info("Start download of %s with roothash %s", filename, roothash)
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys():
            dir = dest_dir + "/" + directories
            if not exists(dir):
                makedirs(dir)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(dir + basename(filename))
            self._swift.start_download(d)
            self._swift.set_moreinfo_stats(d, True)
            
            self.downloads[roothash] = Download(roothash, d.get_dest_dir(), d, download=True) # Know about all hashes that go through this endpoint
            self.downloads[roothash].moreinfo = True
            self.downloads[roothash].add_peer(addr)
        
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
        
    def i2ithread_data_came_in(self, session, sock_addr, data):
        if isinstance(sock_addr, tuple):
            self.known_addresses.update([sock_addr])
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
            
            # Make sure not to make the same mistake as what let to this
            # Any roothash added twice will create an error, leading to this. 
            # If so, that roothash will not cause another problem because only hashes that make it are in the downloads dictionary
            self._swift = MySwiftProcess(self._swift_path, self._swift.workdir, None, self._swift.listenport, None, None, None)
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
                    (status, stats, seeding_stats, _) = D.downloadimpl.network_get_stats(None)
                    logger.debug("INFO: %s, %s\r\nSEEDERS: %s\r\nPEERS: %s \r\nUPLOADED: %s\r\nDOWNLOADED: %s\r\nSEEDINGSTATS: %s" + 
                                "\r\nUPSPEED: %s\r\nDOWNSPEED: %s\r\nFRACTION: %s\r\nSPEW: %s", 
                                self.get_address(), D.roothash_as_hex(), stats["stats"].numSeeds, stats["stats"].numPeers, stats["stats"].upTotal, 
                                stats["stats"].downTotal, seeding_stats, stats["up"], stats["down"], stats["frac"], stats["spew"])
                    
                    
def get_hash(filename, swift_path):
    """
    Determine the roothash of this file
    
    @param filename: The absolute path of the file
    @param swift_path: The absolute path to the swift binary file
    """
    if isfile(filename):
        sdef = SwiftDef()
        sdef.add_content(filename)
        sdef.finalize(swift_path, destdir=dirname(filename))
        # returning get_roothash() gives an error somewhere (perhaps message?)
        return sdef.get_roothash_as_hex()
    