'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''

from os import urandom, makedirs
from os.path import isfile, dirname, exists, basename, getmtime
from datetime import datetime
from threading import Thread, Event, RLock
from sets import Set
from errno import EADDRINUSE, EADDRNOTAVAIL
import binascii
import socket
import time
import logging
import Queue

from src.logger import get_logger
from src.swift.swift_process import MySwiftProcess # This should be imported first, or it will screw up the logs.
from dispersy.endpoint import Endpoint, TunnelEndpoint
from dispersy.statistics import Statistics
from dispersy.candidate import BootstrapCandidate, WalkCandidate

from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.Swift.SwiftProcess import DONE_STATE_EARLY_SHUTDOWN

from src.address import Address
from src.dispersy_extends.candidate import EligibleWalkCandidate
from src.swift.swift_download_config import FakeSession, FakeSessionSwiftDownloadImpl
from src.download import Download, Peer
from src.definitions import SLEEP_TIME, HASH_LENGTH, MESSAGE_KEY_RECEIVE_FILE,\
    MESSAGE_KEY_SWIFT_RESET, MESSAGE_KEY_SOCKET_ERROR, MESSAGE_KEY_SWIFT_PID
from src.dispersy_extends.payload import AddressesCarrier
from src.dispersy_extends.community import MyCommunity
from src.dispersy_contact import DispersyContact

logger = get_logger(__name__)

LOG_MESSAGES = True

class NoEndpointAvailableException(Exception):
    pass

class EndpointDownloads(object):
    
    def __init__(self):
        self.added_peers = Set()
        self.downloads = {}

class EndpointStatistics(Statistics):
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.is_alive = False # The endpoint is alive between open and close
        self.id = urandom(16)
        self.dispersy_contacts = Set() 
        self._socket_running = -1
        
    def update(self):
        pass
    
    @property
    def socket_running(self):
        return self._socket_running == 0
    
    @socket_running.setter
    def socket_running(self, errno):
        logger.debug("Socket running %s", errno)
        self._socket_running = errno
        
class CommonEndpoint(TunnelEndpoint, EndpointStatistics):
    
    def __init__(self, swift_process, api_callback=None):
        TunnelEndpoint.__init__(self, swift_process)
        EndpointStatistics.__init__(self)
        self._api_callback = api_callback
            
    def is_bootstrap_candidate(self, addr=None, candidate=None):
        if addr is not None:
            if self._dispersy._bootstrap_candidates.get(addr.addr()) is not None:
                return True
        if candidate is not None:
            if (isinstance(candidate, BootstrapCandidate) or 
                self._dispersy._bootstrap_candidates.get(candidate.sock_addr) is not None):
                return True
        return False
    
    def do_callback(self, key, *args, **kwargs):
        if self._api_callback is not None:
            self._api_callback(key, *args, **kwargs)

class MultiEndpoint(CommonEndpoint, EndpointDownloads):
    '''
    MultiEndpoint holds a list of Endpoints, which can be added dynamically. 
    The status of each of these Endpoints will be checked periodically (push / pull?). 
    According to the available Endpoints and their status,
    data will be send via those as to provide the fastest means of delivering data. 
    '''

    def __init__(self, swift_process, api_callback=None):
        self._thread_stop_event = Event()
        self._resetting = False
        self._waiting_on_cmd_connection = False
        self._endpoint = None
        self.swift_endpoints = []
        self.swift_queue = Queue.Queue()
        self._dequeueing = False
        # TODO: Make regular checks to make sure that nothing is left in the queue
        CommonEndpoint.__init__(self, swift_process, api_callback=api_callback)
        EndpointDownloads.__init__(self)
        
        self.lock = RLock() # Reentrant Lock
        
        if swift_process:
            self.do_callback(MESSAGE_KEY_SWIFT_PID, swift_process.get_pid())
            self.set_callbacks()
            for addr in self._swift.listenaddrs:
                self.add_endpoint(addr, api_callback=api_callback)
    
    def get_address(self):
        if self._endpoint is None:
            return ("0.0.0.0", 0)
        else:
            return self._endpoint.get_address()
        
    def get_all_addresses(self):
        return list(endpoint.get_address() for endpoint in self.swift_endpoints)
    
    def send(self, candidates, packets):
        self.lock.acquire();
        if not self._swift.is_ready() or not self.socket_running:
            if not self._dequeueing:
                self.swift_queue.put((self.send, (candidates, packets), {}))
                logger.debug("Send is queued")
            self.lock.release()
            return False
        logger.debug("Send %s %d", candidates, len(packets))
        self.update_dispersy_contacts_candidates_messages(candidates, packets, recv=False)
        for c in candidates:
            self.determine_endpoint(Address.tuple(c.sock_addr))
            send_success = self._endpoint.send([c], packets)
        self.lock.release()
        return send_success
            
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
        logger.info("CLOSE: address %s: down %d, send %d, up %d", self.get_address(), self.total_down, self.total_send, self.total_up)
        self.is_alive = False # Must be set before swift is shut down
        self._thread_stop_event.set()
        self._thread_loop.join()
        # We want to shutdown now, but if no connection to swift is available, we need to do it the hard way
        if self._swift is not None:
            if self._swift.is_ready():
                logger.debug("Closing softly")
                self._swift.remove_download(self, True, True)
                self._swift.early_shutdown()
            else:
                logger.debug("Closing harshly")
                self._swift.donestate = DONE_STATE_EARLY_SHUTDOWN
                self._swift.network_shutdown() # Kind of harsh, so make sure downloads are handled
            # Try the sockets to see if they are in use
            if not try_sockets(self._swift.listenaddrs, timeout=1.0):
                logger.warning("Socket(s) is/are still in use")
                self._swift.network_shutdown() # End it at all cost
        
        # Note that the swift_endpoints are still available after return, although closed
        return all([x.close(timeout) for x in self.swift_endpoints]) and super(TunnelEndpoint, self).close(timeout)
    
    def add_endpoint(self, addr, api_callback=None):
        logger.info("Add %s", addr)
        self.lock.acquire()
        new_endpoint = SwiftEndpoint(self._swift, addr, api_callback=api_callback)
        self.swift_endpoints.append(new_endpoint)
        if len(self.swift_endpoints) == 1:
            self._endpoint = new_endpoint
        # TODO: In case we have already send our local addresses around, now update this message with this new endpoint
        self.lock.release()
        return new_endpoint

    def remove_endpoint(self, endpoint):
        """
        Remove endpoint.
        """
        logger.info("Remove %s", endpoint)
        assert isinstance(endpoint, Endpoint), type(endpoint)
        self.lock.acquire()
        ret = False
        for e in self.swift_endpoints:
            if e == endpoint:
                e.close()
                self.swift_endpoints.remove(e)
                if self._endpoint == e:
                    self._endpoint = self._next_endpoint(e)
                ret = True
                break
        self.lock.release()
        return ret
    
    def get_endpoint(self, address):
        """
        Sockets are distinctly recognized by ip and port. Port can be initially 0 to let the system decide the port number.
        Even if multiple endpoints have the same ip with port 0, each will in turn get their port assigned.
        """
        for e in self.swift_endpoints:
            if e.address.ip == address.ip and (e.address.port == 0 or e.address.port == address.port):
                e.address.set_port(address.port)
                return e
        return None
    
    def _next_endpoint(self, current):
        """
        @param current: Endpoint
        @return the next endpoint in the swift_endpoints. If the current endpoint is not in the list,
        return the first in the list. If the list is empty return None
        """
        i = -1
        for x in self.swift_endpoints:
            if x == current:
                return self.swift_endpoints[i % len(self.swift_endpoints)]
            i+=1
            
        # Apparently the endpoint is not part of the list..
        # Return the first one if available
        if len(self.swift_endpoints) > 0:
            return self.swift_endpoints[0]
        return None
    
    def _last_endpoints(self, peer):
        """
        This function returns the endpoints that last had contact with this peer,
        sorted by time since the last contact, latest first
        
        @param peer: The address of the peer that a message will be sent to
        @type peer: Address
        @rtype SwiftEndpoint
        @return List(Endpoint) that last had contact with peer
        """
        last_contacts = []
        for e in self.swift_endpoints:
            for c in e.dispersy_contacts:
                if peer == c.address and c.last_contact() > datetime.min:
                    last_contacts.append((e, c.last_contact()))
        sorted(last_contacts, key=lambda x: x[1], reverse=True)
        return [lc[0] for lc in last_contacts]
    
    def determine_endpoint(self, peer):
        """
        The endpoint that will take care of the task at hand, will be chosen here. 
        The chosen endpoint will be assigned to self._endpoint
        If no appropriate endpoint is found, the current endpoint will remain.
        """
        
        def recur(endpoint):
            if not endpoint.is_alive or not endpoint.socket_running:
                recur(self._next_endpoint(endpoint))
            return endpoint
        
        def determine():
            endpoints = self._last_endpoints(peer)
            for e in endpoints:
                if e is not None and e.is_alive and e.socket_running:
                    return e
            return recur(self._endpoint)
        
        if (len(self.swift_endpoints) == 0):
            self._endpoint = None
        elif (len(self.swift_endpoints) > 1):
            self._endpoint = determine()
        else:
            self._endpoint = self.swift_endpoints[0]
    
    def add_file(self, filename, roothash):
        """
        This method lets the swiftprocess know that an additional file is available.
        
        @param filename: The absolute path of the file
        @param roothash: The roothash of this file
        """
        self.lock.acquire()
        if not self._swift.is_ready():
            self.swift_queue.put((self.add_file, (filename, roothash), {})) 
            logger.debug("Add file is queued")
            self.lock.release()
            return
        logger.debug("Add file, %s %s", filename, roothash)        
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys() and len(roothash) == HASH_LENGTH / 2: # Check if not already added, and if the unhexlified roothash has the proper length
            logger.info("Add file %s with roothash %s", filename, roothash)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(filename)

            self.update_known_downloads(roothash, filename, d, seed=True)
            
            self._swift.start_download(d)
            self._swift.set_moreinfo_stats(d, True)
            
            self.distribute_all_hashes_to_peers() # After adding the file, directly add the peer as well
        self.lock.release()
        
    def distribute_all_hashes_to_peers(self, sock_addr=None):
        """
        All known addresses and downloads are added.
        """
        logger.debug("Distribute all hashes")
        self.lock.acquire()
        for roothash in self.downloads.keys():
            if self.downloads[roothash].seeder(): # TODO: Is this a good idea?
                for peer in self.downloads[roothash].peers():
                    for addr in peer.addresses:
                        self.add_peer(addr, roothash, sock_addr)
        self.lock.release()
    
    def add_peer(self, addr, roothash, sock_addr=None):                
        """
        Send message to the swift process to add a peer.
        If necessary you can specify the socket that should connect to the peer
        Make sure it is not a bootstrap peer.
        
        @param addr: address of the peer: (ip, port)
        @param roothash: Must be unhexlified roothash
        @param sock_addr: Address of local socket
        """
        self.lock.acquire()
        if not self._swift.is_ready():
            self.swift_queue.put((self.add_peer, (addr, roothash), {}))
            logger.debug("Add peer is queued")
            self.lock.release()
            return
        logger.debug("Add peer %s %s", addr, roothash)
        if self.is_bootstrap_candidate(addr=addr):
            logger.debug("Add bootstrap candidate rejected")
            self.lock.release()
            return
        if roothash is not None and not any([addr == a and roothash == h and sock_addr == s for a, h, s in self.added_peers]):
            d = self.retrieve_download_impl(roothash)
            if d is not None:
                logger.info("Add peer %s with roothash %s to %s", addr, roothash, sock_addr)
                self._swift.add_peer(d, addr, sock_addr)
                self.downloads[roothash].add_address(addr)
                self.added_peers.add((addr, roothash, sock_addr))
                # TODO: Note somewhere which local sockets already have peers
        self.lock.release()
            
    def start_download(self, filename, directories, roothash, dest_dir, addresses):
        """
        This method lets the swift instance know that it should download the file that comes with this roothash.
        
        @param filename: The name the file will get
        @param roothash: hash to locate swarm
        @param dest_dir: The folder the file will be put
        """
        self.lock.acquire()
        if not self._swift.is_ready():
            self.swift_queue.put((self.start_download, (filename, directories, roothash, dest_dir, addresses), {}))
            logger.debug("Start download is queued")
            self.lock.release()
            return
        logger.debug("Start download %s %s %s %s %s", filename, directories, roothash, dest_dir, addresses)
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys():
            logger.info("Start download of %s with roothash %s", filename, roothash)
            dir_ = dest_dir + "/" + directories
            if not exists(dir_):
                makedirs(dir_)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(dir_ + basename(filename))
            # Add download first, because it might take while before swift process returns
            self.update_known_downloads(roothash, d.get_dest_dir(), d, addresses=addresses, download=True)
            self._swift.start_download(d)
            self._swift.set_moreinfo_stats(d, True)
        self.lock.release()
            
    def do_checkpoint(self, d):
        if not self._swift.is_ready():
            self.swift_queue.put((self.do_checkpoint, (d,), {}))
            logger.debug("Do checkpoint is queued")
            return
        logger.debug("Do checkpoint")
        if d is not None:
            self._swift.checkpoint_download(d)
        
    def download_is_ready_callback(self, roothash):
        """
        This method is called when a download is ready
        
        @param roothash: Identifier of the download
        """
        logger.debug("Download is ready %s", roothash)
        download = self.downloads[roothash]
        if download.set_finished() and not download.seeder():
            if not download.moreinfo:
                self.clean_up_files(roothash, False, False)
                
    def moreinfo_callback(self, roothash):
        """
        This method is called whenever more info comes in.
        In case the download is finished and not supposed to seed, clean up the files
        
        @param roothash: The roothash to which the more info is related
        """
        logger.debug("More info %s", roothash)
        download = self.downloads[roothash]
        if download.is_finished() and not download.seeder():
            self.clean_up_files(roothash, False, False)
        
    def i2ithread_data_came_in(self, session, sock_addr, data, incoming_addr=Address()):
        logger.debug("Data came in with %s on %s from %s", session, incoming_addr, sock_addr)
        
        e = self.get_endpoint(incoming_addr)
        if e is not None:
            e.i2ithread_data_came_in(session, sock_addr, data)
            return
        # In case the incoming_port number does not match any of the endpoints
        TunnelEndpoint.i2ithread_data_came_in(self, session, sock_addr, data)
        
        self.update_dispersy_contacts([(Address.tuple(sock_addr), [data])], recv=True)
        
    def dispersythread_data_came_in(self, sock_addr, data, timestamp):
        self._dispersy.on_incoming_packets([(EligibleWalkCandidate(sock_addr, True, sock_addr, sock_addr, u"unknown"), data)], True, timestamp)
        
    def create_download_impl(self, roothash):
        """
        Create DownloadImpl
        
        @param roothash: Roothash of a file
        """
        logger.debug("Create download implementation, %s", roothash)
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
        logger.debug("Retrieve download implementation, %s", roothash)
        self.lock.acquire()
        d = None
        try:
            d = self._swift.roothash2dl[roothash]
        except:
            logger.error("Could not retrieve downloadimpl from roothash2dl")
        finally:
            self.lock.release()
        return d
    
    def restart_swift(self, error=None):
        """
        Restart swift if the endpoint is still alive, generally called when an Error occurred in the swift instance
        After swift has been terminated, a new process starts and previous downloads and their peers are added.
        """
        logger.debug("Restart swift called")
        self.lock.acquire()
        # Don't restart on close, or if you are already resetting
        # TODO: In case a restart is necessary while restarting (e.g. can't bind to socket)
        if ((self.is_alive and not self._resetting and not self._waiting_on_cmd_connection and not self._swift.is_running()) 
            or not self._dispersy): # If open has not been called yet
            self._resetting = True
            logger.info("Resetting swift")
            self.do_callback(MESSAGE_KEY_SWIFT_RESET, error=error)
            # Make sure that the current swift instance is gone
            self._swift.donestate = DONE_STATE_EARLY_SHUTDOWN
            self.added_peers = Set() # Reset the peers added before shutdown
            
            # Try the sockets to see if they are in use
            if not try_sockets([e.address for e in self.swift_endpoints], timeout=1.0):
                logger.warning("Socket(s) is/are still in use")
                self._swift.network_shutdown() # Ensure that swift really goes down
                
            # TODO: Don't allow sockets that are in use to be tried by Libswift
            
            # Make sure not to make the same mistake as what let to this
            # Any roothash added twice will create an error, leading to this. 
            self._swift = MySwiftProcess(self._swift.binpath, self._swift.workdir, None, 
                                         [e.address for e in self.swift_endpoints], None, None, None)
            self.set_callbacks()
            self._swift.add_download(self) # Normally in open
            # First add all calls to the queue and then start the TCP connection
            # Be sure to put all current queued items at the back of the startup queue
            temp_queue = Queue.Queue();
            while not self.swift_queue.empty():
                temp_queue.put(self.swift_queue.get())
                
            for h, d in self.downloads.iteritems():
                if (not d.is_finished()) or d.seeder(): # No sense in adding a download that is finished, and not seeding
                    logger.debug("Enqueue start download %s", h)
                    self.swift_queue.put((self._swift.start_download, (d.downloadimpl,), {}))
                    for peer in self.downloads[h].peers():
                        for addr in peer.addresses:
                            if not (addr, h, None) in self.added_peers:
                                logger.debug("Enqueue add peer %s %s", addr, h)
                                self.swift_queue.put((self._swift.add_peer, (d.downloadimpl, addr, None), {}))                            
                                self.added_peers.add((addr, h, None))
                            
            while not temp_queue.empty():
                self.swift_queue.put(temp_queue.get())
            
            self._waiting_on_cmd_connection = True
            self._swift.start_cmd_connection() # Normally in open
            self._resetting = False
        self.lock.release()
    
    def _loop(self):
        while not self._thread_stop_event.is_set() and LOG_MESSAGES:
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
        if not self._swift.is_ready():
            self.swift_queue.put((self.clean_up_files, (roothash, rm_state, rm_download), {}))
            logger.debug("Clean up files is queued")
            return
        logger.debug("Clean up files, %s, %s, %s", roothash, rm_state, rm_download)
        d = self.retrieve_download_impl(roothash)
        if d is not None:
            if not (rm_state or rm_download):
                self.do_checkpoint(d)
            self._swift.remove_download(d, rm_state, rm_download)
            self.do_callback(MESSAGE_KEY_RECEIVE_FILE, self.downloads[roothash].filename)
        self.added_peers = Set([p for p in self.added_peers if p[1] != roothash])
        
    def update_dispersy_contacts_candidates_messages(self, candidates, packets, recv=True):
        self.update_dispersy_contacts([(Address.tuple(c.sock_addr), packets) for c in candidates], recv)
        
    def update_dispersy_contacts(self, contacts_and_messages, recv=True):
        """
        Update the list of known dispersy contacts (excluding bootstrappers), with addresses and messages
        Note that if the list grows, the new addresses will be called used for distributing
        local addresses and adding peers to swift
        @type contacts_and_messages: tuple(Address, Iterable(Packet))
        @type recv: boolean
        """
        logger.debug("Update known addresses, %s", [str(cam[0]) for cam in contacts_and_messages])
        self.lock.acquire()
        contacts = [DispersyContact(cam[0], recv_messages=cam[1]) if recv else DispersyContact(cam[0], send_messages=cam[1]) 
                    for cam in contacts_and_messages if isinstance(cam, tuple) 
                    and not self.is_bootstrap_candidate(addr=cam[0])]
        diff = Set(contacts).difference(self.dispersy_contacts)
        if len(diff) > 0:
            logger.debug("New dispersy contacts: %s", [str(dc.address) for dc in diff])
            self.dispersy_contacts.update(diff)
            self.send_addresses_to_communities([dc.address for dc in diff])
            for download in self.downloads.itervalues():
                # TODO: Protect against unreachable local addresses
                download.merge_peers(Peer([dc.address for dc in diff]))
            self.distribute_all_hashes_to_peers()
        self.lock.release()

    def update_known_downloads(self, roothash, filename, download_impl, addresses=None, seed=False, download=False, add_known=True):
        """
        @param roothash: Binary form of the roothash of filename
        @param filename: Absolute path of filename
        @param donwload_impl: Download implementation as created in create_download_impl
        @param addresses: List of Address objects
        @param seed: Boolean that determines if this download should seed after finishing download
        @param download: Boolean that determines if this file needs to be downloaded
        @param add_known: Boolean that determines if all known peers should be added to this download
        """
        logger.debug("Update known downloads, %s %s %s %s %s %s", binascii.hexlify(roothash), filename, addresses, seed, download, add_known)
        self.lock.acquire()
        d = Download(roothash, filename, download_impl, seed=seed, download=download)
        d.moreinfo = True
        d.add_peer(Peer(addresses))
        if add_known: # Add all known peers to this download
            for dc in self.dispersy_contacts:
                d.add_address(dc.address)
                # TODO: DC has both an address and a peer. What to do?
        self.downloads[roothash] = d
        logger.debug("Download %s has %s as peers", filename, [str(a) for a in [asets for asets in [p.addresses for p in d.peers()]]])
        self.lock.release()
        
    def swift_started_running_callback(self):
        logger.info("The TCP connection with Swift is up")
        self._waiting_on_cmd_connection = False
        self.dequeue_swift_queue()
        for e in self.swift_endpoints:
            e.swift_started_running_callback()
        
    def dequeue_swift_queue(self):
        self._dequeueing = True
        while not self.swift_queue.empty() and self._swift.is_ready():
            func, args, kargs = self.swift_queue.get()
            logger.debug("Dequeue %s %s %s", func, args, kargs)
            func(*args, **kargs)            
        self._dequeueing = False
    
    def interface_came_up(self, addr):
        logger.debug("%s came up", addr.interface)
        if addr.interface is None:
            return
        for e in self.swift_endpoints:
            if e.address.ip == addr.ip:
                addr.set_port(e.address.port)
                return e.swift_add_socket(addr) # If ip already exists, try adding it to swift (only if not already working)
        for e in self.swift_endpoints:
            # TODO: Determine if we are going to use interface name, or just device name
            if (e.address.interface.name == addr.interface.name or
                e.address.interface.device == addr.interface.device):
                e.socket_running = -1 # This new socket is not yet running, so initialize to -1
                return e.swift_add_socket(addr) # Replace with new address                
        e = self.add_endpoint(addr, api_callback=self._api_callback) # If it is new create endpoint
        e.open(self._dispersy) # Don't forget to open it...
        # Now that we have a new socket we should tell it about the files to disseminate
        self.distribute_all_hashes_to_peers(e.address)
    
    def send_addresses_to_communities(self, addresses):
        """
        The addresses should be reachable from the candidates point of view
        Local addresses will not benefit the candidate or us
        """
        logger.debug("Send address to %s", addresses)
        candidates = [WalkCandidate(a.addr(), False, a.addr(), a.addr(), u"unknown") for a in addresses]
        message = AddressesCarrier([e.address for e in self.swift_endpoints])
        for c in self._dispersy.get_communities():
            if isinstance(c, MyCommunity): # Ensure that the create_addresses_messages exists
                self._dispersy.callback.register(c.create_addresses_messages, (1,message,candidates), 
                                                 kargs={"update":False}, delay=0.0)
        
    def peer_addresses_arrived(self, addresses):
        logger.debug("Peer's addresses arrived %s", addresses)
        for download in self.downloads.itervalues():
            # TODO: Protect against unreachable local addresses
            download.merge_peers(Peer(addresses))
        for addr in addresses:
            for dc in self.dispersy_contacts:
                if addr == dc.address:
                    dc.set_peer(Peer(addresses))
        self.distribute_all_hashes_to_peers()
        
    def set_callbacks(self):
        self._swift.set_on_swift_restart_callback(self.restart_swift)
        self._swift.set_on_tcp_connection_callback(self.swift_started_running_callback)
        self._swift.set_on_sockaddr_info_callback(self.sockaddr_info_callback)
        
    def sockaddr_info_callback(self, address, errno):
        logger.debug("Socket info callback %s %d", address, errno)
        if errno < 0 or address.ip == "AF_UNSPEC":
            logger.debug("Something is going on, but don't know what.")
        elif errno == 0:
            logger.debug("Socket is bound and active")
            if address.resolve_interface():
                e = self.get_endpoint(address)
                if e is not None:
                    e.socket_running = errno
                else:
                    logger.warning("This %s is not in %s", address, [e.address for e in self.swift_endpoints])
                self.dequeue_swift_queue()
            else:
                logger.debug("Might have been able to bind to something, but unable to resolve interface")
        elif errno > 0:
            e = self.get_endpoint(address)
            if e is not None:
                e.socket_running = errno
            if not address.resolve_interface():
                logger.debug("Cannot resolve interface")
            if try_socket(address):
                logger.debug("Yelp, socket is gone!")
        self.do_callback(MESSAGE_KEY_SOCKET_ERROR, address, errno)
                
    @property
    def socket_running(self):
        return any([e.socket_running for e in self.swift_endpoints])
    
class SwiftEndpoint(CommonEndpoint):
    
    def __init__(self, swift_process, address, api_callback=None):
        super(SwiftEndpoint, self).__init__(swift_process, api_callback=api_callback) # Dispersy and session code 
        self.waiting_queue = Queue.Queue()
        self.address = address
        if self.address.resolve_interface():
            if not address in self._swift.listenaddrs:
                self.swift_add_socket()
            elif address in self._swift.confirmedaddrs:
                self.socket_running = 0
            else:
                logger.debug("Socket is not ready yet!")
        else:
            logger.debug("This address can not be resolved to an interface")
        
    def open(self, dispersy):
        self.is_alive = True
        return Endpoint.open(self, dispersy) # Dispersy, but not add_download(self)
        
    def close(self, timeout=0.0):
        self.is_alive = False
        self._swift = None
        return super(TunnelEndpoint, self).close(timeout)
    
    def get_address(self):
        # Dispersy retrieves the local ip
        return self.address.addr()
    
    def send(self, candidates, packets):
        if self._swift is not None and self._swift.is_alive():
            if any(len(packet) > 2**16 - 60 for packet in packets):
                raise RuntimeError("UDP does not support %d byte packets" % len(max(len(packet) for packet in packets)))

            self._total_up += sum(len(data) for data in packets) * len(candidates)
            self._total_send += (len(packets) * len(candidates))
    
            self._swift.splock.acquire()
            try:
                for candidate in candidates:
                    sock_addr = candidate.sock_addr
                    assert self._dispersy.is_valid_address(sock_addr), sock_addr
    
                    for data in packets:
                        if logger.isEnabledFor(logging.DEBUG):
                            try:
                                name = self._dispersy.convert_packet_to_meta_message(data, load=False, auto_load=False).name
                            except:
                                name = "???"
                            logger.debug("%30s -> %15s:%-5d %4d bytes", name, sock_addr[0], sock_addr[1], len(data))
                            self._dispersy.statistics.dict_inc(self._dispersy.statistics.endpoint_send, name)
                        self._swift.send_tunnel(self._session, sock_addr, data, self.address)
    
                # return True when something has been send
                return candidates and packets
    
            finally:
                self._swift.splock.release()
                
            self.dispersy_contacts.update([DispersyContact(Address.tuple(c.sock_addr), send_messages=packets)
                                           for c in candidates if isinstance(c.sock_addr, tuple)
                                           and not self.is_bootstrap_candidate(addr=Address.tuple(c.sock_addr), candidate=c)])
        
    def i2ithread_data_came_in(self, session, sock_addr, data):
        if isinstance(sock_addr, tuple):
            self.dispersy_contacts.add(DispersyContact(Address.tuple(sock_addr), recv_messages=[data]))
        TunnelEndpoint.i2ithread_data_came_in(self, session, sock_addr, data)
            
    def dispersythread_data_came_in(self, sock_addr, data, timestamp):
        self._dispersy.on_incoming_packets([(EligibleWalkCandidate(sock_addr, True, sock_addr, sock_addr, u"unknown"), 
                                             data)], True, timestamp)
        
    def swift_add_socket(self, addr=None):
        logger.debug("SwiftEndpoint add socket %s", addr)
        if addr is not None:
            try:
                self._swift.listenaddrs.remove(self.address) # Remove old value
            except:
                logger.exception("Why can't we remove this address? %s", self.address)
            self.address = addr
        if not self._swift.is_ready():
            self._enqueue(self.swift_add_socket, (addr,), {})
        else:
            if not self.socket_running:
                self._swift.add_socket(self.address, True)
        
    def _enqueue(self, func, args, kwargs):
        self.waiting_queue.put((func, args, kwargs))
    
    def _dequeue(self):
        while self._swift.is_ready() and not self.waiting_queue.empty():
            f, a, k = self.waiting_queue.get()
            f(*a, **k)
            
    def swift_started_running_callback(self):
        self._dequeue()

                    
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
    
def try_sockets(addrs, timeout=1.0, log=True):
    """
    This method returns when all UDP sockets are free to use, or if the timeout is reached
    
    @param ports: List of local socket addresses
    @param timeout: Try until timeout time has been exceeded
    @param log: Log the logger.exception
    @return: True if the sockets are free
    """
    event = Event()
    t = time.time()        
    while not event.is_set() and t + timeout > time.time():
        # TODO: There is not point in doing this over and over if the interface is gone
        if all([try_socket(a, log) for a in addrs]):
            event.set()
        event.wait(0.1)
        
    return all([try_socket(a, log) for a in addrs])
    
def try_socket(addr, log=True):
    """
    This methods tries to bind to an UDP socket.
    
    @param port: Local socket address
    @param log: Log the logger.exception
    @return: True if socket is free to use
    """
    try:
        s = socket.socket(addr.family, socket.SOCK_DGRAM)
        s.bind(addr.addr())
        return True
    except Exception, ex:
        (error_number, error_message) = ex
        if error_number == EADDRINUSE: # Socket is already bound
            if log:
                logger.exception("Bummer, %s is already bound!", str(addr))
            return False
        if error_number == EADDRNOTAVAIL: # Interface is most likely gone so nothing on this ip can be bound
            if log:
                logger.exception("Shit, %s can't be bound! Interface gone?", str(addr))
            return False
        if log:
            logger.exception("He, we haven't taken into account this error yet!!\n%s", error_message)
        return False
    finally:
        s.close()
    