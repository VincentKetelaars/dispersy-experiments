'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''
import socket
import time
import logging
import Queue
import random
from os import urandom
from os.path import isfile, dirname, getmtime
from datetime import datetime, timedelta
from threading import Thread, Event, RLock
from errno import EADDRINUSE, EADDRNOTAVAIL, EWOULDBLOCK
from _mysql_exceptions import ProgrammingError

from src.logger import get_logger
from src.swift.swift_process import MySwiftProcess # This should be imported first, or it will screw up the logs.
from dispersy.endpoint import Endpoint, TunnelEndpoint
from dispersy.candidate import BootstrapCandidate, WalkCandidate
from src.swift.tribler.SwiftProcess import DONE_STATE_EARLY_SHUTDOWN
from src.swift.tribler.SwiftDef import SwiftDef

from src.address import Address
from src.dispersy_extends.candidate import EligibleWalkCandidate
from src.definitions import MESSAGE_KEY_SWIFT_STATE, MESSAGE_KEY_SOCKET_STATE, MESSAGE_KEY_SWIFT_PID,\
     STATE_RESETTING, STATE_RUNNING, STATE_STOPPED,\
    REPORT_DISPERSY_INFO_TIME, MESSAGE_KEY_DISPERSY_INFO, \
    MAX_CONCURRENT_DOWNLOADING_SWARMS, ALMOST_DONE_DOWNLOADING_TIME,\
    BUFFER_DRAIN_TIME, MAX_SOCKET_INITIALIZATION_TIME, ENDPOINT_SOCKET_TIMEOUT,\
    SWIFT_ERROR_TCP_FAILED, PUNCTURE_MESSAGE_NAME, ADDRESSES_MESSAGE_NAME,\
    ENDPOINT_CONTACT_TIMEOUT, ENDPOINT_CHECK, ENDPOINT_ID_LENGTH,\
    MAX_CONCURRENT_SEEDING_SWARMS, MESSAGE_KEY_UPLOAD_STACK, DELETE_CONTENT,\
    ADDRESSES_REQUEST_MESSAGE_NAME, MIN_TIME_BETWEEN_PUNCTURE_REQUESTS,\
    MIN_TIME_BETWEEN_ADDRESSES_MESSAGE, REACHABLE_ENDPOINT_MAX_MESSAGES,\
    REACHABLE_ENDPOINT_RETRY_ADDRESSES, PUNCTURE_RESPONSE_MESSAGE_NAME
from src.dispersy_contact import DispersyContact
from src.peer import Peer
from src.tools.priority_stack import PriorityStack

logger = get_logger(__name__)

def _swift_runnable_decorator(func):
    """
    Ensure that swift is running before calling it by queuing it when necessary.
    """
    def dec(self, *args, **kwargs):
        with self.lock:
            # We can't go putting stuff on swift when it isn't working
            if not self._swift.is_ready(): 
                self.enqueue_swift_queue(func, self, *args, **kwargs)
                return
            return func(self, *args, **kwargs)
    return dec
     
class SwiftHandler(TunnelEndpoint):
    
    def __init__(self, swift_process, api_callback=None):
        TunnelEndpoint.__init__(self, swift_process)
        self._api_callback = api_callback
        self._socket_running = (-1, datetime.utcnow())
        self._resetting = False
        self._waiting_on_cmd_connection = False
        self._swift_cmd_queue = Queue.Queue()
        self._dequeueing_cmd_queue = False
        self._started_downloads = {}
        self._swift_download_stack = PriorityStack()
        self._swift_upload_stack = PriorityStack()
        self._added_peers = {} # Dictionary of sets (paddr, saddr)
        self._closing = False
        
        self.lock = RLock() # Reentrant Lock
        
    @property
    def swift(self):
        return self._swift
    
    @property
    def socket_running(self):
        return self._socket_running[0] == 0 or (self._socket_running[0] == EWOULDBLOCK and 
                                                self._socket_running[1] > datetime.utcnow() - timedelta(seconds=BUFFER_DRAIN_TIME))
    
    @socket_running.setter
    def socket_running(self, state):
        self._socket_running = (state, datetime.utcnow())
        self.do_callback(MESSAGE_KEY_SOCKET_STATE, self.address, state)
    
    def do_callback(self, key, *args, **kwargs):
        if self._api_callback is not None:
            self._api_callback(key, *args, **kwargs)
            
    def close(self, timeout=0.0):
        self._closing = True
        # We want to shutdown now, but if no connection to swift is available, we need to do it the hard way
        if self._swift is not None:
            if self._swift.is_ready():
                logger.debug("Closing softly")
                self._swift.remove_download(self, True, True)
                self._swift.early_shutdown()
                # Upon closing, checkpoints are created for those downloads that need it
            else:
                logger.debug("Closing harshly")
                self._swift.donestate = DONE_STATE_EARLY_SHUTDOWN
                self._swift.network_shutdown() # Kind of harsh, so make sure downloads are handled
            # Try the sockets to see if they are in use
            # TODO: IPv6 addresses in working_sockets will have not have the appropriate scopeid!
            if not try_sockets(self._swift.working_sockets, timeout=1.0):
                logger.warning("Socket(s) is/are still in use")
                self._swift.network_shutdown() # End it at all cost
            
            self.do_callback(MESSAGE_KEY_SWIFT_STATE, STATE_STOPPED)
        return super(TunnelEndpoint, self).close()
    
    @_swift_runnable_decorator
    def swift_add_peer(self, d, addr, sock_addr=None):
        """
        @type d: SwiftDownloadImpl
        @type addr: Address
        @type sock_addr: Address
        """
        if d is None or d.bad_swarm:
            return
        roothash = d.get_def().get_roothash()
        if not roothash in self._started_downloads.keys():
            return
        peer_set = self._added_peers.get(roothash, set())
        if not any([addr == a and sock_addr == s for a, s in peer_set]):
            # It could very well be that this endpoint has no way of reaching this peer's endpoint
            # We open the channel up regardless and rely on swift and regularly checking to kill this channel if it doesn't work out
            self._swift.add_peer(d, addr, sock_addr)
            peer_set.add((addr, sock_addr))
            self._added_peers[roothash] = peer_set
        else:
            logger.debug("We already have the %s %s in %s", str(addr), str(sock_addr), d.get_def().get_roothash_as_hex())
    
    @_swift_runnable_decorator    
    def swift_checkpoint(self, d):
        """
        @type d: SwiftDownloadImpl
        """
        if d is not None and d.get_def().get_roothash() in self._started_downloads.keys() and not d.bad_swarm:
            self._swift.checkpoint_download(d)
            d.checkpointing()
    
    @_swift_runnable_decorator  
    def swift_start(self, d, cid):
        """
        @type d: SwiftDownloadImpl
        """
        if not d.get_def().get_roothash() in self._started_downloads.keys():
            if d.bad_swarm:
                return logger.debug("%s is a bad swarm", d.get_def().get_roothash_as_hex())
            self._started_downloads[d.get_def().get_roothash()] = cid
            self._swift.start_download(d)
            self.add_peers_to_download(d, cid)
        else:
            logger.warning("This roothash %s was already started!", d.get_def().get_roothash_as_hex())
    
    @_swift_runnable_decorator  
    def swift_moreinfo(self, d, yes):
        """
        @type d: SwiftDownloadImpl
        @type yes: boolean
        """
        if d is not None and d.get_def().get_roothash() in self._started_downloads.keys() and not d.bad_swarm:
            self._swift.set_moreinfo_stats(d, yes)
    
    @_swift_runnable_decorator
    def swift_remove_download(self, d, rm_state, rm_content):
        """
        @type d: SwiftDownloadImpl
        @type rm_state: boolean
        @type rm_content: boolean
        """
        if d is not None and d.get_def().get_roothash() in self._started_downloads.keys() and not d.bad_swarm:
            del self._started_downloads[d.get_def().get_roothash()]
            del self._added_peers[d.get_def().get_roothash()]
            self._swift.remove_download(d, rm_state, rm_content)
    
    @_swift_runnable_decorator
    def swift_pex(self, d, enable):
        """
        @type d: SwiftDownloadImpl
        @type enable: boolean
        """
        if d is not None and d.get_def().get_roothash() in self._started_downloads.keys() and not d.bad_swarm:
            self._swift.set_pex(d.get_def().get_roothash_as_hex(), enable)
            
    @_swift_runnable_decorator
    def swift_add_socket(self, saddr):
        """
        @type address: 
        """
        self._swift.add_socket(saddr)   
    
    def restart_swift(self, error_code=-1):
        """
        Restart swift if the endpoint is still alive, generally called when an Error occurred in the swift instance
        After swift has been terminated, a new process starts and previous downloads and their peers are added.
        """
        logger.debug("Restart swift called")
        self.lock.acquire()
        # Don't restart on close, or if you are already resetting
        if (not self._closing and not self._resetting and 
            (not self._waiting_on_cmd_connection or error_code == SWIFT_ERROR_TCP_FAILED) 
            and not self._swift.is_running()):
            self._resetting = True # Probably not necessary because of the lock
            logger.info("Resetting swift")
            self.do_callback(MESSAGE_KEY_SWIFT_STATE, STATE_RESETTING, error_code=error_code)
            self._added_peers = {} # Reset the peers added before restarting
            
            # Try the sockets to see if they are in use
            if not try_sockets(list(self._swift.working_sockets), timeout=1.0):
                logger.warning("Socket(s) is/are still in use")
                self._swift.donestate = DONE_STATE_EARLY_SHUTDOWN
                self._swift.network_shutdown() # Ensure that swift really goes down
                
            # We now assume that all sockets have been killed
            
            # Make sure not to make the same mistake as what let to this
            # Only add the addresses of sockets that have proven to be working
            # FIXME: In case the first of multiple sockets cannot be bound, the others won't be added either
            self._swift = MySwiftProcess(self._swift.binpath, self._swift.workdir, None, 
                                         self._swift.working_sockets, None, None, None)
            self.set_callbacks()
            self._swift.add_download(self) # Normally in open
            self.do_callback(MESSAGE_KEY_SWIFT_PID, self._swift.get_pid())
            
            # First add all calls to the queue and then start the TCP connection
            # Be sure to put all current queued items at the back of the startup queue
            temp_queue = Queue.Queue();
            while not self._swift_cmd_queue.empty():
                temp_queue.put(self._swift_cmd_queue.get())
            
            try:
                self._dispersy.on_swift_restart(temp_queue, self._started_downloads.keys())    
            except AttributeError:
                pass                
            self._started_downloads = {} # Reset the started downloads before restarting
                            
            while not temp_queue.empty():
                self._swift_cmd_queue.put(temp_queue.get())
            
            self._waiting_on_cmd_connection = True
            self._swift.start_cmd_connection() # Normally in open
            self._resetting = False
        self.lock.release()
        
    def swift_started_running_callback(self):
        self.dequeue_swift_queue()
        
    def enqueue_swift_queue(self, func, *args, **kwargs):
        logger.debug("%s is queued", func.__name__)
        self._swift_cmd_queue.put((func, args, kwargs))
        
    def dequeue_swift_queue(self):
        self._dequeueing_cmd_queue = True
        while not self._swift_cmd_queue.empty() and self._swift.is_ready():
            func, args, kargs = self._swift_cmd_queue.get()
            logger.debug("Dequeue %s", func.__name__)
            func(*args, **kargs)            
        self._dequeueing_cmd_queue = False        

    def set_callbacks(self):
        self._swift.set_on_swift_restart_callback(self.restart_swift)
        self._swift.set_on_tcp_connection_callback(self.swift_started_running_callback)
        self._swift.set_on_sockaddr_info_callback(self.sockaddr_info_callback)
        self._swift.set_on_channel_closed_callback(self.channel_closed_callback)
        
    def sockaddr_info_callback(self, address, state):
        self.socket_running = state
        
    def put_swift_upload_stack(self, func, size, timestamp, priority=0, args=(), kwargs={}):
        """
        Put (func, size, timestamp, args, kwargs) on upload stack
        Sort by increasing priority first then increasing timestamp
        @param func: Function that will be executed when popped of the stack
        @param size: Size of the file
        @param timestamp: Modification / creation time of file
        @type timestamp: float (Important that it is comparable)
        @param priority: priority of the file
        @type priority: int
        """
        if not (func, size, timestamp, args, kwargs) in self._swift_upload_stack:
            self._swift_upload_stack.put((priority, timestamp), (func, size, timestamp, args, kwargs))
            self.evaluate_swift_swarms() # Evaluate directly (That is, don't wait for the loop thread to do this)
                
    def put_swift_download_stack(self, func, size, timestamp, priority=0, args=(), kwargs={}):
        """
        Put (func, size, timestamp, args, kwargs) on download stack
        Sort by increasing priority first then increasing timestamp
        @param func: Function that will be executed when popped of the stack
        @param size: Size of the file
        @param timestamp: Modification / creation time of file
        @type timestamp: float (Important that it is comparable)
        @param priority: priority of the file
        @type priority: int
        """
        if not (func, size, timestamp, args, kwargs) in self._swift_download_stack:
            self._swift_download_stack.put((priority, timestamp), (func, size, timestamp, args, kwargs))
            self.evaluate_swift_swarms() # Evaluate directly (That is, don't wait for the loop thread to do this)
        
    def pop_swift_upload_stack(self):
        """
        Pop (func, size, timestamp, args, kwargs) from upload stack
        """
        item = self._swift_upload_stack.pop()
        if item is not None:
            logger.debug("Pop file of size %d with timestamp %f and function arguments %s %s of upload stack", 
                         item[1], item[2], item[3], item[4])
            item[0](*item[3], **item[4]) # Call function
        
    def pop_swift_download_stack(self):
        """
        Pop (func, size, timestamp, args, kwargs) from download stack
        """
        item = self._swift_download_stack.pop()
        if item is not None:
            logger.debug("Pop file of size %d with timestamp %f and function arguments %s %s of download stack", 
                         item[1], item[2], item[3], item[4])
            item[0](*item[3], **item[4]) # Call function
    
    def evaluate_swift_swarms(self):
        """
        This function determines the state of all downloading swarms.
        It determines the number of swarms (almost) done, 
        and subsequently pops new swarms to be created of the stack if there is room
        @return: The swarms that should be removed
        """
        if not self.socket_running:
            return []
        seeding_swarms = 0
        downloading_swarms = 0
        almost_done_swarms = 0
        swarms_to_be_removed = []
        for d in self.swift.roothash2dl.values():
            if not isinstance(d, MultiEndpoint):
                if d.downloading():
                    downloading_swarms += 1
                    speed = d.speed("down")
                    if speed != 0:
                        # The estimated number of seconds left before download is finished
                        dw_time_left = d.dynasize * (1 - d.progress) / 1024 / speed
                        if dw_time_left < ALMOST_DONE_DOWNLOADING_TIME:
                            almost_done_swarms += 1
                            logger.debug("Estimate %s to be done downloading in %f", 
                                         d.get_def().get_roothash_as_hex(), dw_time_left)
                    if len(self._swift_download_stack) > 0 and not d.has_peer():
                        swarms_to_be_removed.append(d)
                elif d.seeding() or d.initialized(): # Seeding or initializing
                    seeding_swarms += 1
                    if len(self._swift_upload_stack) > 0 and not d.has_peer():
                        swarms_to_be_removed.append(d)
        # Start new swarms if there is room
        for _ in range(downloading_swarms - almost_done_swarms, MAX_CONCURRENT_DOWNLOADING_SWARMS):
            self.pop_swift_download_stack()
        for _ in range(seeding_swarms, MAX_CONCURRENT_SEEDING_SWARMS):
            self.pop_swift_upload_stack()
        self.do_callback(MESSAGE_KEY_UPLOAD_STACK, len(self._swift_upload_stack), sum([f[1] for f in self._swift_upload_stack]))
        return swarms_to_be_removed
            
    def retrieve_download_impl(self, roothash):
        """
        Retrieve SwiftDownloadImpl with roothash
        
        @return: SwiftDownloadImpl, otherwise None
        """
        logger.debug("Retrieve download implementation, %s", roothash)
        self.lock.acquire()
        d = None
        try:
            d = self._swift.roothash2dl[roothash]
        except KeyError:
            logger.error("Could not retrieve downloadimpl from roothash2dl")
        finally:
            self.lock.release()
        return d
    
    def add_peers_to_download(self, downloadimpl, cid):
        pass
    
    def channel_closed_callback(self, roothash, saddr, paddr):
        try:
            self._added_peers[roothash].remove((paddr, saddr))
        except KeyError:
            logger.exception("Channel %s %s %s could not be removed", roothash, str(paddr), str(saddr))
            
        
class CommonEndpoint(SwiftHandler):
    
    def __init__(self, swift_process, api_callback=None, address=Address()):
        SwiftHandler.__init__(self, swift_process, api_callback)
        self.start_time = datetime.utcnow()
        self.id = urandom(ENDPOINT_ID_LENGTH)
        self.dispersy_contacts = set()
        self.is_alive = False # The endpoint is alive between open and close
        self.address = address
        self._wan_voters = {}
        self._wan_address = { address : 0 } # Initialize zero vote
        self.bootstrap_last_received = {} # Last time received message from bootstrapper
        
    @property
    def wan_address(self):
        return max(self._wan_address, key=self._wan_address.get) # Return the address with the highest vote
    
    def vote_wan_address(self, address, sender_lan, sender_wan):
        """
        Use the vote to determine the wan address. Endpoints can only vote once
        Only allowed to vote for wan address when outside of our local network. I.e.
        wan is not private
        @type address: Address
        @type sender_lan: Address
        @type sender_wan: Address 
        """
        # Wan addresses can change over time for an endpoint
        # We assume the lan address to be unique
        # FIX: Weird ass assumption
        if self._wan_voters.get(sender_lan) == address:
            return  # Same vote as last time
        if self._wan_voters.get(sender_lan) is not None: # So we have a new vote
            self._wan_address[address] = self._wan_address.get(self._wan_voters.get(sender_lan), 0) - 1 # Get rid of the old vote
        # We're not going to give the private or wildcard addresses more votes
        if not (address.is_private_address() or address.is_wildcard_ip()): 
            self._wan_address[address] = self._wan_address.get(address, 0) + 1 # Increment
            self._wan_voters[sender_lan] = address # Update vote
            logger.info("Got a vote for %s to %s from %s", str(self.address), str(address), str(sender_lan))
            
    def is_bootstrap_candidate(self, addr=None, candidate=None):
        if addr is not None:
            if self._dispersy._bootstrap_candidates.get(addr.addr()) is not None:
                return True
        if candidate is not None:
            if (isinstance(candidate, BootstrapCandidate) or 
                self._dispersy._bootstrap_candidates.get(candidate.sock_addr) is not None):
                return True
        return False
    
    def peers(self, cid):
        """
        Get all peers that live in this community represented by the community id
        @param cid: community id
        """
        return [dc.peer for dc in self.dispersy_contacts if dc.has_community(cid) and dc.peer is not None]
        
    def update_dispersy_contacts(self, sock_addr, packets, recv=True):
        """
        Update the list of known dispersy contacts (excluding bootstrappers), with addresses and packet info
        Recv is used to determine whether the messages are incoming or outgoing
        It returns the community the packets are for/from and a DispersyCandidate if it is the first time we receive from it
        @type sock_addr: tuple(str, int)
        @type packets: List(str)
        @type recv: boolean
        @rtype: Community, DispersyContact
        """
        community = self.get_community(packets[0][2:22]) # Packet of first tuple
        if community is None:
            return None, None
        address = Address.tuple(sock_addr)
        if self.is_bootstrap_candidate(addr=address):
            if recv:
                self.bootstrap_last_received[sock_addr[0]] = datetime.utcnow()
            return None, None
        _bytes = sum([len(p) for p in packets])
        contact = DispersyContact(address, community_id=community.cid)
        if recv:
            contact.rcvd(len(packets), _bytes, address=address)
        else:
            contact.sent(len(packets), _bytes, address=address)
        for dc in self.dispersy_contacts:
            if dc.has_address(contact.address):
                dc.merge(contact)
                if recv and dc.total_rcvd() == contact.total_rcvd(): # First time receiving anything
                    return community, dc
                return community, None
        self.dispersy_contacts.add(contact)
        if recv:
            return community, contact
        return community, None
        
    def peer_endpoints_received(self, community, mid, lan_addresses, wan_addresses, ids):
        same_contacts = []
        for dc in self.dispersy_contacts:
            if dc.member_id == mid or dc.has_any(lan_addresses + wan_addresses, ids=ids): # Both lan and wan can have arrived
                same_contacts.append(dc)
        # Quite possibly some of these addresses are not public, and may therefore not be reachable by each local address
        if len(same_contacts) == 0: # Can happen with endpoints that have not had contact yet
            dc = DispersyContact(lan_addresses[0], community_id=community.cid, 
                                 addresses_received=True, member_id=mid)
            self.dispersy_contacts.add(dc)
        elif len(same_contacts) == 1: # The normal case
            dc = same_contacts[0]
        else: # Merge same_contacts into one
            self.dispersy_contacts.difference_update(set(same_contacts)) # Remove all but first from set
            for c in same_contacts:
                if c.address in lan_addresses + wan_addresses: # At least one of them matches the description
                    dc = c
            for c in same_contacts:
                if c != dc: # Merge with the others
                    dc.merge(c) # Merge
            self.dispersy_contacts.add(dc)
        dc.member_id = mid # Set member id
        dc.set_peer(Peer(lan_addresses, wan_addresses, ids, mid), True) # update the peer to include all addresses
        return dc
    
    def get_community(self, community_id):
        try:
            return self._dispersy.get_community(community_id, load=False, auto_load=False)
        except (KeyError, ProgrammingError):
            logger.warning("Unknown community %s", community_id)
        return None
    
    def get_contact(self, address, mid=None):
        for dc in self.dispersy_contacts:
            if dc.member_id == mid or dc.has_address(address):
                return dc
        return None
                
    def last_contact(self):
        return max([dc.last_contact() for dc in self.dispersy_contacts])
    
    def __str__(self):
        return str(self.address)

class MultiEndpoint(CommonEndpoint):
    '''
    MultiEndpoint holds a list of Endpoints, which can be added dynamically. 
    The status of each of these Endpoints will be checked periodically (push / pull?). 
    According to the available Endpoints and their status,
    data will be send via those as to provide the fastest means of delivering data. 
    '''

    def __init__(self, swift_process, api_callback=None):
        self._thread_stop_event = Event()
        self._endpoint = None
        self.swift_endpoints = []
        self._interfaces_that_came_up = {}
        CommonEndpoint.__init__(self, swift_process, api_callback=api_callback)
        
        if swift_process:
            self.do_callback(MESSAGE_KEY_SWIFT_PID, swift_process.get_pid())
            self.set_callbacks()
    
    def get_address(self):
        if self._endpoint is None:
            return self.address.addr()
        else:
            return self._endpoint.get_address()
        
    def get_all_addresses(self):
        return list(endpoint.get_address() for endpoint in self.swift_endpoints)
    
    def send(self, candidates, packets):
        with self.lock:
            if not self._swift.is_ready() or not self.socket_running:
                if not self._dequeueing_cmd_queue: # Functions are dequeued when swift is running, hence we're not keeping messages to be send
                    self.enqueue_swift_queue(self.send, candidates, packets)
                return False
            logger.debug("Send %s %d", [c.sock_addr for c in candidates], len(packets))
            
            for c in candidates:
                new_c = self.determine_endpoint(c, packets)
                send_success = self._endpoint.send(new_c, packets)
                self.update_dispersy_contacts(new_c.sock_addr, packets, recv=False)
        return send_success
            
    def open(self, dispersy):
        ret = TunnelEndpoint.open(self, dispersy)
        self._swift.start_cmd_connection()
        ret = ret and all([x.open(dispersy) for x in self.swift_endpoints])
                    
        self.is_alive = True
        
        self._thread_loop = Thread(target=self._loop, name="MultiEndpoint_periodic_loop")
        self._thread_loop.daemon = True
        self._thread_loop.start()
        return ret
    
    def close(self, timeout=0.0):
        self._thread_stop_event.wait(timeout)
        logger.info("CLOSE: address %s: down %d, send %d, up %d", self.get_address(), self.total_down, self.total_send, self.total_up)
        self.is_alive = False # Must be set before swift is shut down
        self._thread_stop_event.set()
        self._thread_loop.join()
        
        SwiftHandler.close(self)
        # Note that the swift_endpoints are still available after return, although closed
        return all([x.close(timeout) for x in self.swift_endpoints])
    
    def add_endpoint(self, addr):
        logger.info("Add %s", addr)
        with self.lock:
            new_endpoint = SwiftEndpoint(self._swift, addr, api_callback=self._api_callback, device=self._interfaces_that_came_up.get(addr.ip))
            new_endpoint.dispersy_contacts = set([DispersyContact.shallow_copy(dc) for dc in self.dispersy_contacts]) # Initialize
            try:
                new_endpoint.open(self._dispersy)
            except AttributeError:
                pass
            self.swift_endpoints.append(new_endpoint)
            if len(self.swift_endpoints) == 1:
                self._endpoint = new_endpoint
        self._send_socket_information()
        return new_endpoint

    def remove_endpoint(self, endpoint):
        """
        Remove endpoint.
        """
        assert isinstance(endpoint, Endpoint), type(endpoint)
        with self.lock:
            endpoint.close()
            if self._endpoint == endpoint:
                if len(self.swift_endpoints) == 1:
                    self._endpoint = None
                else:
                    self._endpoint = self._next_endpoint(endpoint)                    
            try:
                self.swift_endpoints.remove(endpoint)                
                logger.info("Removed %s", endpoint)
                if len(self.swift_endpoints):
                    self._send_socket_information()
                return True
            except KeyError:
                logger.info("%s is not part of the SwiftEndpoints", endpoint)
        return False
    
    def get_endpoint(self, address):
        """
        Sockets are distinctly recognized by ip and port. Port can be initially 0 to let the system decide the port number.
        Even if multiple endpoints have the same ip with port 0, each will in turn get their port assigned.
        @type address: Address
        """
        for e in self.swift_endpoints:
            if e.address.ip == address.ip and (e.address.port == 0 or e.address.port == address.port):
                e.address.set_port(address.port)
                return e
        return None
    
    def _next_endpoint(self, current):
        """
        @type current: SwiftEndpoint
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
    
    def _last_endpoints(self, address, endpoints=[]):
        """
        This function returns the endpoints that last had contact with this peer,
        sorted by time since the last contact, latest first
        
        @type address: Address
        @param endpoints: List of endpoints to use (defaults to self.swift_endpoints)
        @return: List((SwiftEndpoint, peer Address, datetime)) that last had contact with peer
        """
        if not endpoints:
            endpoints = self.swift_endpoints
        last_contacts = []
        for e in endpoints:
            contact = e.get_contact(address)
            if contact is None:
                continue
            for paddr in contact.get_peer_addresses(self.address, self.wan_address):
                if contact.last_rcvd(paddr) > datetime.min: # If we use received, we are sure that it is actually reachable
                    last_contacts.append((e, paddr, contact.last_contact(paddr)))
        return sorted(last_contacts, key=lambda x: x[2], reverse=True)
    
    def _subnet_endpoints(self, contact, endpoints=[]):
        """
        This function returns the endpoints that reside in the same subnet.
        These are either point to point or local connections, which will likely be fastest(?).
        
        @type contact: DispersyContact 
        @param endpoints: List of endpoints to use (defaults to self.swift_endpoints)
        @return: List((SwiftEndpoint, peer Address))
        """
        if not endpoints:
            endpoints = self.swift_endpoints
        same_subnet = []
        for e in endpoints:
            for paddr in contact.get_peer_addresses(self.address, self.wan_address):
                if e.address.same_subnet(paddr.ip):
                    same_subnet.append((e, paddr))
        return same_subnet
    
    def _get_channels(self, contact):
        """
        Retrieve channels from DownloadImpls
        Include the socket and peer address as well
        @type contact: DispersyContact
        @rtype List((Dict, Address, Address))
        """
        channels = []
        for d in self.swift.roothash2dl.values():
            if not isinstance(d, MultiEndpoint) and "channels" in d.midict:
                for c in d.midict.get("channels", []):
                    saddr = Address.unknown(c["socket_ip"].encode("ascii", "ignore") + ":" + str(c["socket_port"]))
                    paddr = Address.unknown(c["ip"].encode("ascii", "ignore") + ":" + str(c["port"]))
                    if contact.has_address(paddr):
                        channels.append((c, saddr, paddr))
        return channels
    
    def _get_channel_speeds(self, contact):
        """
        Returns the list of (sock_addr, peer_addr, upspeed, downspeed), where speeds are in bytes/s
        @type contact: DispersyContact
        @rtype: List((Address, Address, float, float))
        """
        r = []
        for c, saddr, paddr in self._get_channels(contact):
            r.append((saddr, paddr, c.get("cur_speed_up", 0.0), c.get("cur_speed_down", 0.0)))
        return r
    
    def _maximum_speed_endpoints(self, contact, endpoints=[]):
        """
        Determine which endpoints have a channel with this peer (or if None, all channels of this socket), 
        and sort them by combined up/download speed, returning only those with positive speeds
        
        @type contact: DispersyContact
        @param endpoints: List of endpoints to use (defaults to self.swift_endpoints)
        @rtype: List((SwiftEndpoint, Address, float))
        """
        if not endpoints: # []
            endpoints = self.swift_endpoints
        speeds = self._get_channel_speeds(contact)
        r = []
        for e in endpoints:
            for saddr, paddr, up, down in speeds:
                if e.address == saddr and up + down > 0:
                    r.append((e, paddr, up + down))
        return sorted(r, key=lambda x: x[2], reverse=True) # Largest speed first
    
    def _minimum_send_queue_endpoints(self, contact, endpoints=[]):
        """
        Determine the size of the send queue for each endpoint with a connection with peer
        and return the list of these sorted from low to high.
        @type contact: DispersyContact
        @rtype: List((SwiftEndpoint, int))
        """
        if not endpoints: # []
            endpoints = self.swift_endpoints
        channels = self._get_channels(contact)
        r = [(e, c["send_queue"]) for e in endpoints for c, saddr, _ in channels if e.address == saddr]
        return sorted(r, key=lambda x: x[1]) # Lowest sendqueue first
    
    def _sort_endpoints_by_estimated_response_time(self, contact, packet_size, endpoints=[]):
        """
        The endpoints will be sorted by: 
        estimated send time = send_queue / upload_speed (socket total) + packet_size / upload_speed(channel) 
        or if channel upspeed is 0                                     + round trip time / 2
        Only nonzero total upspeeds will be added to the list.
        @type contact: DispersyContact
        @param packet_size = Total amount of bytes that need to be sent
        @rtype: List((SwiftEndpoint, Address, float))
        """
        if not endpoints:
            endpoints = self.swift_endpoints
        channels = self._get_channels(contact)
        upspeeds ={}
        for c, saddr, _ in channels:
            upspeeds[saddr] = upspeeds.get(saddr, 0) + c["cur_speed_up"]
        r = []
        for e in endpoints:
            for c, saddr, paddr in channels:
                if e.address == saddr and upspeeds[saddr] > 0: # Only add if we have measured speed                    
                    est = c["send_queue"] / float(upspeeds[saddr]) # send_queue (bytes) / total upload_speed (bytes/s)  
                    if c["cur_speed_up"] > 0:
                        est += packet_size / float(c["cur_speed_up"]) # packet_size (bytes) / upload_speed (bytes/s)
                    else:
                        est += c["avg_rtt"] / float(10**6) / 2 # avg_rtt (us) / 10^6 / 2
                    r.append((e, paddr, est))
        return sorted(r, key=lambda x: x[2]) # From low to high
    
    def _pick_public_endpoints_at_random(self, contact, endpoints=[]):
        """
        Determine public endpoints and public contact addresses, choose from these at random
        """
        if not endpoints:
            endpoints = self.swift_endpoints
        public_endpoints = [e for e in endpoints if not e.wan_address.is_private_address()]
        random.shuffle(public_endpoints)
        addresses = [a for a in contact.addresses if not a.is_private_address()]
        random.shuffle(addresses)
        return [(e, p) for e in public_endpoints for p in addresses]
        
    def determine_endpoint(self, candidate, packets):
        """
        The endpoint that will take care of the task at hand, will be chosen here. 
        The chosen endpoint will be assigned to self._endpoint
        If no appropriate endpoint is found, the current endpoint will remain.
        Using self.dispersy_contacts it will also be determined which socket is best suited for this task,
        and this socket will be returned as Candidate
        
        @type peer: Candidate
        @rtype: Candidate
        """
        total_size = sum([len(packet) for packet in packets])
        
        def recur(endpoint, max_it):
            if max_it > 0 and not endpoint.is_alive or not endpoint.socket_running:
                return recur(self._next_endpoint(endpoint), max_it - 1)
            return (endpoint, candidate.sock_addr)
        
        def determine(addr):
            # Find the peer addresses
            contact = DispersyContact(addr) # Default to the address supplied
            for dc in self.dispersy_contacts:
                if dc.address == addr:
                    contact = dc
                    break
            # Choose the endpoint that currently has the highest transfer speed with this peer
            for e, paddr, ert in self._sort_endpoints_by_estimated_response_time(contact, total_size):
                if e is not None and e.is_alive and e.socket_running:
                    logger.debug("%d bytes will be sent %s to %s with estimated response time of %f ms", total_size, 
                                 e, paddr, ert * 1000)
                    return (e, paddr.addr())
            # Choose the endpoint that was the last to receive anything from this contact
            for e, paddr, last_contact in self._last_endpoints(contact.address):
                if e is not None and e.is_alive and e.socket_running:
                    logger.debug("%d bytes will be sent with %s that had contact with %s at %s", total_size, e, paddr, 
                                 last_contact.strftime("%H:%M:%S"))
                    return (e, paddr.addr())
            # In case no contact has been made with this peer (or those endpoint are not available)
            for e, paddr in self._subnet_endpoints(contact):
                if e is not None and e.is_alive and e.socket_running:
                    logger.debug("%d bytes will be sent with %s in the same subnet as %s", total_size, e, paddr)
                    return (e, paddr.addr())
            # Pick one endpoint at random and one of the peer's endpoints as long as they are public
            for e, paddr in self._pick_public_endpoints_at_random(contact):
                if e is not None and e.is_alive and e.socket_running:
                    logger.debug("%d bytes will be sent with public endpoint %s and public peer %s", total_size, e, paddr)
                    return (e, paddr.addr())
            return recur(self._next_endpoint(self._endpoint), len(self.swift_endpoints)) # Make sure there is some change
        
        if (len(self.swift_endpoints) == 0):
            self._endpoint = None
        elif (len(self.swift_endpoints) > 1):
            self._endpoint, sock_addr = determine(Address.tuple(candidate.sock_addr))
            candidate = WalkCandidate(sock_addr, True, sock_addr, sock_addr, u"unknown")
        else:
            self._endpoint = self.swift_endpoints[0]
        return candidate
        
    def i2ithread_data_came_in(self, session, sock_addr, data, incoming_addr=Address()):
        try:
            name = self._dispersy.convert_packet_to_meta_message(data, load=False, auto_load=False).name
        except:
            name = "???"
        logger.debug("%20s <- %15s:%-5d %30s %4d bytes", str(incoming_addr), sock_addr[0], sock_addr[1], name, len(data))
        self._dispersy.statistics.dict_inc(self._dispersy.statistics.endpoint_recv, name)
        
        # Spoof sock_addr. Dispersy knows only about the first socket address of a peer, 
        # to keep things clean.
        self.update_dispersy_contacts(sock_addr, [data], recv=True)
        
        e = self.get_endpoint(incoming_addr)
        if e is not None:
            e.i2ithread_data_came_in(session, sock_addr, data) # Ensure that you fool the SwiftEndpoint as well
            if name == ADDRESSES_REQUEST_MESSAGE_NAME: # Apparently someone does not know us yet (Perhaps my wan is not what I think it is)
                try:
                    message = self._dispersy.convert_packet_to_message(data, load=False, auto_load=False)
                    e.vote_wan_address(message.payload.wan_address, message.payload.sender_lan, message.payload.sender_wan)
                except:
                    logger.exception("Could not convert packet to message")
            return
        logger.warning("This %s should be represented by an endpoint", incoming_addr)
        # In case the incoming_addr does not match any of the endpoints
        TunnelEndpoint.i2ithread_data_came_in(self, session, sock_addr, data)        
        
    def dispersythread_data_came_in(self, sock_addr, data, timestamp):
        self._dispersy.on_incoming_packets([(EligibleWalkCandidate(sock_addr, True, sock_addr, sock_addr, u"unknown"), data)], True, timestamp)
    
    def _loop(self):
        while not self._thread_stop_event.is_set():
            self.dequeue_swift_queue()
            swarms_to_be_removed = self.evaluate_swift_swarms()
            for d in swarms_to_be_removed:
                # Keeping state if keeping content (Because it would have been seeding at some point then)
                self.swift_remove_download(d, DELETE_CONTENT, DELETE_CONTENT) 
            if int(time.time()) % ENDPOINT_CHECK == 0:
                self.check_endpoints()
            self._thread_stop_event.wait(REPORT_DISPERSY_INFO_TIME)
            data = []
            for e in self.swift_endpoints:
                data.append({"address" : e.address, "contacts" : len(e.dispersy_contacts),
                             "num_sent" : sum([dc.num_sent() for dc in e.dispersy_contacts]), 
                             "bytes_sent" : sum([dc.total_sent() for dc in e.dispersy_contacts]), 
                             "num_rcvd" : sum([dc.num_rcvd() for dc in e.dispersy_contacts]),
                             "bytes_rcvd" : sum([dc.total_rcvd() for dc in e.dispersy_contacts])})
            self.do_callback(MESSAGE_KEY_DISPERSY_INFO, {"multiendpoint" : data})
            
    def check_endpoints(self):
        marked_remove = []
        for e in self.swift_endpoints:
            # In case an error has persisted for more than ENDPOINT_SOCKET_TIMEOUT seconds, remove endpoint
            if e._socket_running[0] > 0 and e._socket_running[1] < datetime.utcnow() - timedelta(seconds=ENDPOINT_SOCKET_TIMEOUT):
                marked_remove.append(e)
        for e in marked_remove:
            self.remove_endpoint(e)
            
        def send_puncture(endpoint, cid, address, id_):
            if not id_ is None:
                endpoint.send_puncture_message(self.get_community(cid), address, id_)
        
        # In case an endpoint has not done any sending or receiving (Tunnelled or not), ensure the socket is still working
        for e in self.swift_endpoints:
            for dc in e.dispersy_contacts:
                if not dc.addresses_received:
                    continue
                addrs = set(dc.no_contact_since(expiration_time=ENDPOINT_CONTACT_TIMEOUT, 
                                                lan=self.address, wan=self.wan_address)).difference(set([c[1] for c in self._get_channels(dc)]))
                if len(addrs) > 0:
                    [logger.info("%s has %s received and %s sent from/to %s in communities %s", str(e.address), dc.last_rcvd(a), 
                                 dc.last_sent(a), str(a), dc.community_ids) for a in addrs]
                    [self._dispersy.callback.register(send_puncture, args=(e, dc.community_ids[0], a, dc.get_id(a))) 
                     for a in addrs]
        
        # We aim to alleviate the stress of continuously sending puncture messages to non responding hosts
        # First determine if the address has been confirmed by any of the endpoints
        confirmed_addrs = set([a for dc in self.dispersy_contacts for a in dc.confirmed_addresses])
        need_addresses_message = [] # List of contacts that need addresses messages
        for e in self.swift_endpoints:
            for dc in e.dispersy_contacts:
                # Find the confirmed addresses that have not been confirmed for this endpoint
                addrs = set([a for a in dc.reachable_addresses if dc.last_rcvd(a) == datetime.min]).intersection(confirmed_addrs)
                unreachable = set([a for a in addrs if dc.count_sent.get(a, 0) >= REACHABLE_ENDPOINT_MAX_MESSAGES])
                for a in unreachable:
                    logger.debug("%s is unreachable for %s", str(a), str(e))
                    dc.add_unreachable_address(a) # Set address unreachable after 10 puncture message tries
                addrs = addrs.difference(unreachable) # Update not reached (but potentially reachable) addresses
                if len([a for a in addrs if dc.count_sent.get(a, 0) == REACHABLE_ENDPOINT_RETRY_ADDRESSES]) > 0: # When 5 messages have been sent to this address
                    need_addresses_message.append(dc)
                    
        def send_addresses(cid, contact):
            self.send_addresses_to_communities(self.get_community(cid), contact)
        # Send an addresses message to the peer's main address to retry puncture messages
        for dc in need_addresses_message:
            self._dispersy.callback.register(send_addresses, args=(dc.community_ids[0], dc))         
        
        def send_request(cid, contact):
            self.request_addresses(self.get_community(cid), contact)
        
        for dc in self.dispersy_contacts:
            if (not dc.addresses_received and dc.num_rcvd() > 1 and # Let's wait till we receive more than one message
                dc.addresses_requested + timedelta(seconds=MIN_TIME_BETWEEN_ADDRESSES_MESSAGE) < datetime.utcnow()): 
                logger.debug("We have not received an addresses message from %s yet, so we request it", str(dc.address))
                self._dispersy.callback.register(send_request, args=(dc.community_ids[0], dc))
                dc.requested_addresses()
                         
    def interface_came_up(self, addr):
        logger.debug("%s came up", addr.interface)
        if addr.interface is None or addr.ip in self._interfaces_that_came_up.keys():
            return
        self._interfaces_that_came_up[addr.ip] = addr.interface.device
        for e in self.swift_endpoints:
            if (e.address.ip == addr.ip or e.address.interface.name == addr.interface.name or
                e.address.interface.device == addr.interface.device):
                # Don't try and overwrite this endpoint if it is working or trying to work
                if e.socket_running or e.socket_initializing():
                    logger.debug("Interface is already up and running")
                    return
                e.socket_running = -1 # This new socket is not yet running, so initialize to -1
                if addr.port <= 0:
                    addr.set_port(e.address.port) # Use the old port
                old_ip = e.address.ip
                e.swift_add_socket(addr) # If ip already exists, try adding it to swift (only if not already working)
                if old_ip != addr.ip: # New address
                    self._send_socket_information() # This assumes that the port number is settled
                    for dc in e.dispersy_contacts: 
                        # Reset unreachable addresses, because they might be reachable with this new ip
                        dc.reset_unreachable_addresses()
                return
        self.swift_add_socket(addr) # If it is new send address to swift
        
    def update_dispersy_contacts(self, sock_addr, packets, recv=True):
        """
        Note that if we have received a message from a new contact, the new addresses will be send a list of local sockets        
        """
        community, new_recv = CommonEndpoint.update_dispersy_contacts(self, sock_addr, packets, recv=recv)
        if new_recv is not None:
            self.send_addresses_to_communities(community, new_recv)
            self.add_peer_to_started_downloads(new_recv)
        return community, new_recv
            
    def send_addresses_to_communities(self, community, contact):
        """
        The addresses should be reachable from the candidates point of view
        Local addresses will not benefit the candidate or us
        """
        if community is None or contact is None: # Possible if we couldn't retrieve community from the incoming packet
            return
        candidate = WalkCandidate(contact.address.addr(), True, contact.address.addr(), contact.address.addr(), u"unknown")
        sockets = [(e.id, e.address, e.wan_address) for e in self.swift_endpoints if e.socket_running]
        logger.debug("Send endpoint addresses %s to %s", [str(s[1]) + ":" + str(s[2]) for s in sockets], str(contact))
        meta_puncture = community.get_meta_message(ADDRESSES_MESSAGE_NAME)
        message = meta_puncture.impl(authentication=(community.my_member,), distribution=(community.claim_global_time(),), 
                                     destination=(candidate,), payload=(sockets,))
        self.send([candidate], [message.packet])
        contact.sent_addresses()
        for e in self.swift_endpoints:
            e.determine_puncture_messages_to_send(contact)
            
    def request_addresses(self, community, contact):
        if community is None or contact is None:
            return
        candidate = WalkCandidate(contact.address.addr(), True, contact.address.addr(), contact.address.addr(), u"unknown")
        meta_puncture = community.get_meta_message(ADDRESSES_REQUEST_MESSAGE_NAME)
        message = meta_puncture.impl(authentication=(community.my_member,), distribution=(community.claim_global_time(),), 
                                     destination=(candidate,), payload=(self._endpoint.address, self._endpoint.wan_address, 
                                                                        self._endpoint.id, contact.address))
        self.send([candidate], [message.packet])
                
    def sockaddr_info_callback(self, address, state):
        logger.debug("Socket info callback %s %d", address, state)
        if state < 0 or address.ip == "AF_UNSPEC":
            return logger.warning("Something is going on, but don't know what.")        
        e = self.get_endpoint(address)
        if e is not None:
            e.sockaddr_info_callback(address, state)
        else:
            if state == 0:
                self.add_endpoint(address)
        self.dequeue_swift_queue()
        if state == 0:
            self.add_socket_to_started_downloads(address)
                
    def swift_started_running_callback(self):
        logger.info("The TCP connection with Swift is up")
        self._waiting_on_cmd_connection = False
        self.dequeue_swift_queue()
        for e in self.swift_endpoints:
            e.swift_started_running_callback()
        self.do_callback(MESSAGE_KEY_SWIFT_STATE, STATE_RUNNING)
        
    @property
    def socket_running(self):
        return any([e.socket_running for e in self.swift_endpoints])
    
    def restart_swift(self, error_code=-1):
        SwiftHandler.restart_swift(self, error_code)
        for e in self.swift_endpoints: # We need to add the reference to the new swift to each endpoint
            e._swift = self._swift
        
    def peer_endpoints_received(self, community, member, addresses, wan_addresses, ids):
        logger.debug("Addresses of peer arrived %s, %s, %s", community, 
                     [str(a[0]) +":"+ str(a[1]) for a in zip(addresses, wan_addresses)], [str(i) for i in ids])
        dc = CommonEndpoint.peer_endpoints_received(self, community, member.mid, addresses, wan_addresses, ids)
        self.add_peer_to_started_downloads(dc)
        for e in self.swift_endpoints:
            e.peer_endpoints_received(community, member, addresses, wan_addresses, ids)
            
    def add_socket_to_started_downloads(self, sock_addr):
        logger.debug("Adding socket %s to our %d downloads", str(sock_addr), len(self._started_downloads))
        for h, cid in list(self._started_downloads.items()):
            self.add_peers_to_download(self.retrieve_download_impl(h), cid, sock_addr)
            
    def add_peer_to_started_downloads(self, contact):
        logger.debug("Adding contact %s to our %d downloads", str(contact), len(self._started_downloads))
        for h, cid in list(self._started_downloads.items()):
            if contact.has_community(cid):
                downloadimpl = self.retrieve_download_impl(h)
                for addr in contact.reachable_addresses:
                    self.swift_add_peer(downloadimpl, addr, None)
                
    def add_peers_to_download(self, downloadimpl, cid, sock_addr=None):
        logger.debug("Adding peers to new download %s", downloadimpl.get_def().get_roothash_as_hex())
        for contact in self.dispersy_contacts:
            if contact.has_community(cid):
                for addr in contact.reachable_addresses:
                    self.swift_add_peer(downloadimpl, addr, sock_addr)
            
    def swift_add_peer(self, d, addr, sock_addr=None):
        if self.is_bootstrap_candidate(addr=addr):
            return 
        for e in self.swift_endpoints:
            if sock_addr is None or e.address == sock_addr:
                if e.socket_running and addr in [a for dc in e.dispersy_contacts 
                                                 for a in dc.get_peer_addresses(self.address, self.wan_address)]:
                    SwiftHandler.swift_add_peer(self, d, addr, sock_addr=e.address)
                    
    def _send_socket_information(self):
        logger.info("Preparing for addresses to be send to %s with communities %s", 
                    [dc.address for dc in self.dispersy_contacts], [dc.community_ids for dc in self.dispersy_contacts])
        for dc in self.dispersy_contacts:
            self.send_addresses_to_communities(self.get_community(dc.community_ids[0]), dc)
                
    def incoming_puncture_message(self, community, member, sender_lan, sender_wan, sender_id, vote_address, endpoint_id):
        """
        @param local_address: The origin of the message
        @param vote_address: The address the origin votes for
        @param endpoint_id: id of the endpoint it casts it vote for
        """
        valid_endpoint_id = True
        for e in self.swift_endpoints:
            if e.id == endpoint_id:
                e.vote_wan_address(vote_address, sender_lan, sender_wan)
#                 e.send_puncture_response_message(community, sender_wan, sender_id) # TODO send actual wan
                valid_endpoint_id = True
        if not valid_endpoint_id:
            return logger.warning("Unknown endpoint id %s, by voter %s,%s voting for %s", endpoint_id.encode("base-64"), 
                           str(sender_lan), str(sender_wan), str(vote_address))
        # Update the wan address according to the lan address
        for e in self.swift_endpoints + [self]:
            dc = e.get_contact(sender_lan, mid=member.mid)
            if dc is not None:
                dc.update_address(sender_lan, sender_wan, sender_id, member.mid)
                
    def incoming_puncture_response_message(self, member, sender_lan, sender_wan, vote_address, endpoint_id):
        pass
        
    def addresses_requested(self, community, member, sender_lan, sender_wan, endpoint_id, wan_address):
        dc = DispersyContact(sender_wan)
        for e in self.swift_endpoints + [self]:
            edc = e.get_contact(sender_lan, mid=member.mid)
            if edc is not None:
                edc.update_address(sender_lan, sender_wan, endpoint_id, member.mid)
                dc = edc
        if dc.addresses_sent + timedelta(seconds=MIN_TIME_BETWEEN_ADDRESSES_MESSAGE) < datetime.utcnow():
            self.send_addresses_to_communities(community, dc)
    
    def channel_closed_callback(self, roothash, saddr, paddr):
        CommonEndpoint.channel_closed_callback(self, roothash, saddr, paddr)
        d = self.retrieve_download_impl(roothash)
        if roothash in self._started_downloads.keys() and self._swift.is_running() and d.downloading():
            self.add_peers_to_download(d, self._started_downloads[roothash], saddr)
            
    def wan_address_vote(self, wan_address, candidate):
        candidate_address = Address.unknown(candidate.sock_addr)
        last_bootstrap_contacts = sorted([(e, e.bootstrap_last_received.get(candidate.sock_addr[0], datetime.min)) for e in self.swift_endpoints], key=lambda x: x[1], reverse=True)
        if not last_bootstrap_contacts == [] and last_bootstrap_contacts[0][1] != datetime.min:
            last_bootstrap_contacts[0][0].vote_wan_address(Address.unknown(wan_address), candidate_address, candidate_address)
    
class SwiftEndpoint(CommonEndpoint):
    
    def __init__(self, swift_process, address, api_callback=None, device=None):
        super(SwiftEndpoint, self).__init__(swift_process, api_callback=api_callback, address=address) # Dispersy and session code
        logger.debug("Creating SwiftEndpoint %s %s %s %s", swift_process, address, api_callback, device)
        self.waiting_queue = Queue.Queue()
        if self.address.resolve_interface():
            if not address in self._swift.working_sockets:
                self.swift_add_socket(self.address)
            else:
                self.socket_running = 0
            self.address.interface.set_device(device)
        else:
            logger.warning("This address can not be resolved to an interface")
        
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
    
    def send(self, candidate, packets):
        if self._swift is not None and self._swift.is_ready():
            if any(len(packet) > 2**16 - 60 for packet in packets):
                raise RuntimeError("UDP does not support %d byte packets" % len(max(len(packet) for packet in packets)))

            self._swift.splock.acquire()
            try:
                sock_addr = candidate.sock_addr
                assert self._dispersy.is_valid_address(sock_addr), sock_addr

                for data in packets:
                    if logger.isEnabledFor(logging.DEBUG):
                        try:
                            name = self._dispersy.convert_packet_to_meta_message(data, load=False, auto_load=False).name
                        except:
                            name = "???"
                        logger.debug("%20s -> %15s:%-5d %30s %4d bytes", str(self.address), sock_addr[0], sock_addr[1], name, len(data))
                        self._dispersy.statistics.dict_inc(self._dispersy.statistics.endpoint_send, name)
                    self._swift.send_tunnel(self._session, sock_addr, data, self.address)
                    
                # This contact may be spoofed by MultiEndpoint, which ensures that we don't have DispersyContacts
                # that resolve to the same peer
                self.update_dispersy_contacts(candidate.sock_addr, packets, recv=False)
    
                # return True when something has been send
                return candidate and packets
    
            finally:
                self._swift.splock.release()
        
    def i2ithread_data_came_in(self, session, sock_addr, data):
        self.update_dispersy_contacts(sock_addr, [data], recv=True)
        self._total_down += len(data)
        
        # Spoof the contact address for the benefit of Dispersy
        for dc in self.dispersy_contacts:
            if dc.has_address(Address.tuple(sock_addr)):
                sock_addr = dc.address.addr()    
        self._dispersy.callback.register(self.dispersythread_data_came_in, (sock_addr, data, time.time()))        
            
    def dispersythread_data_came_in(self, sock_addr, data, timestamp):
        self._dispersy.on_incoming_packets([(EligibleWalkCandidate(sock_addr, True, sock_addr, sock_addr, u"unknown"), 
                                             data)], True, timestamp)
    
    def socket_initializing(self):
        return (self._socket_running[0] == -1 and 
                self._socket_running[1] > datetime.utcnow() - timedelta(seconds=MAX_SOCKET_INITIALIZATION_TIME))
        
    def swift_add_socket(self, addr):
        logger.debug("SwiftEndpoint add socket %s", addr)
        if not self.socket_running:
            self.address = addr
            SwiftHandler.swift_add_socket(self, self.address)
                
    def sockaddr_info_callback(self, address, state):
        if self.address == address: # Should be redundant
            self.socket_running = state
        else:
            logger.warning("Socket info callback for %s is at %s", address, self.address)
        if state == EWOULDBLOCK:
            logger.info("%s has buffer issues", self.address)
        # MultiEndpoint takes care of the downloads and peers for Swift
        
    def peer_endpoints_received(self, community, member, lan_addresses, wan_addresses, ids):
        dc = CommonEndpoint.peer_endpoints_received(self, community, member.mid, lan_addresses, wan_addresses, ids)        
        # We need to establish connections. At least ensure that we can contact each address.
        self.determine_puncture_messages_to_send(dc)
            
    def determine_puncture_messages_to_send(self, contact=None):
        contacts = []
        if contact is None:
            contacts = self.dispersy_contacts
        elif contact in self.dispersy_contacts:
            contacts = [contact]
        else:
            contact = self.get_contact(contact.address)
            if contact is not None:
                contacts = [contact] # The contact better be there
            
        def send_puncture(cid, address, id_):
            if id_ is not None:
                self.send_puncture_message(self.get_community(cid), address, id_)
            
        for dc in contacts:
            for addr in dc.no_contact_since(expiration_time=ENDPOINT_SOCKET_TIMEOUT, lan=self.address, wan=self.wan_address):
                if dc.last_sent(addr) + timedelta(seconds=MIN_TIME_BETWEEN_PUNCTURE_REQUESTS) < datetime.utcnow():
                    self._dispersy.callback.register(send_puncture, args=(dc.community_ids[0], addr, dc.get_id(addr)))
                
    def send_puncture_message(self, community, address, id_):
        logger.debug("Creating puncture message for %s %s %s", community.cid, str(address), str(id_))
        if community is None or isinstance(id_, int):
            return
        candidate = WalkCandidate(address.addr(), True, address.addr(), address.addr(), u"unknown")        
        meta_puncture = community.get_meta_message(PUNCTURE_MESSAGE_NAME)
        message = meta_puncture.impl(authentication=(community.my_member,), distribution=(community.claim_global_time(),), 
                                     destination=(candidate,), payload=(self.address, self.wan_address, self.id, address, id_))
        self.send(candidate, [message.packet]) # In case this one fails, there will be others later if necessary
        
    def send_puncture_response_message(self, community, address, id_):
        logger.debug("Creating puncture response message for %s %s %s", community.cid, str(address), str(id_))
        if community is None or isinstance(id_, int):
            return
        candidate = WalkCandidate(address.addr(), True, address.addr(), address.addr(), u"unknown")        
        meta_puncture = community.get_meta_message(PUNCTURE_RESPONSE_MESSAGE_NAME)
        message = meta_puncture.impl(authentication=(community.my_member,), distribution=(community.claim_global_time(),), 
                                     destination=(candidate,), payload=(self.address, self.wan_address, address, id_))
        self.send(candidate, [message.packet]) # In case this one fails, there will be others later if necessary
                    
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
            except (IndexError, IOError):
                logger.exception("Reading mbinmap from %s failed", filename)
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
        results = [try_socket(a, log) for a in addrs]
        if all([r[0] or not r[1] == EADDRINUSE for r in results]): # Only when it is in use do we expect things to change suddenly
            event.set()
        event.wait(0.1)
        
    return all([try_socket(a, log)[0] for a in addrs])
    
def try_socket(addr, log=True):
    """
    This methods tries to bind to an UDP socket.
    The method reports whether it was successfull in binding the address,
    and the error number in case it fails
    @param port: Local socket address
    @param log: Log the logger.exception
    @return: (Successful bind, error_number)
    """
    try:
        s = socket.socket(addr.family, socket.SOCK_DGRAM)
        s.bind(addr.socket())
        return (True, 0)
    except socket.error, ex:
        (error_number, error_message) = ex
        if log:
            if error_number == EADDRINUSE: # Socket is already bound
                logger.debug("Bummer, %s is already bound!", str(addr))
            elif error_number == EADDRNOTAVAIL: # Interface is most likely gone so nothing on this ip can be bound
                logger.debug("Shit, %s can't be bound! Interface gone?", str(addr))
            else:
                logger.debug("He, we haven't taken into account '%s', which happens on %s", error_message, str(addr.socket()))
        return (False, error_number)
    finally:
        s.close()
    