'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''

from os import urandom
from os.path import isfile, dirname, getmtime
from datetime import datetime
from threading import Thread, Event, RLock
from sets import Set
from errno import EADDRINUSE, EADDRNOTAVAIL
import socket
import time
import logging
import Queue

from src.logger import get_logger
from src.swift.swift_process import MySwiftProcess # This should be imported first, or it will screw up the logs.
from dispersy.endpoint import Endpoint, TunnelEndpoint
from dispersy.statistics import Statistics
from dispersy.candidate import BootstrapCandidate, WalkCandidate

from Tribler.Core.Swift.SwiftProcess import DONE_STATE_EARLY_SHUTDOWN
from Tribler.Core.Swift.SwiftDef import SwiftDef

from src.address import Address
from src.dispersy_extends.candidate import EligibleWalkCandidate
from src.definitions import MESSAGE_KEY_SWIFT_STATE, MESSAGE_KEY_SOCKET_STATE, MESSAGE_KEY_SWIFT_PID,\
     STATE_RESETTING, STATE_RUNNING, STATE_STOPPED,\
    REPORT_DISPERSY_INFO_TIME, MESSAGE_KEY_DISPERSY_INFO, FILE_HASH_MESSAGE_NAME
from src.dispersy_extends.payload import AddressesCarrier
from src.dispersy_extends.community import MyCommunity
from src.dispersy_contact import DispersyContact
from src.download import Peer

logger = get_logger(__name__)

class NoEndpointAvailableException(Exception):
    pass

class EndpointStatistics(Statistics):
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self.is_alive = False # The endpoint is alive between open and close
        self.id = urandom(16)
        self.dispersy_contacts = Set()
        
    def update(self):
        pass

def _swift_runnable_decorator(func):
    """
    Ensure that swift is running before calling it by queuing it when necessary.
    """
    def dec(self, *args, **kwargs):
        self.lock.acquire()
        if not self._swift.is_ready():
            self.enqueue_swift_queue(func, self, *args, **kwargs)
            logger.debug("%s is queued", func)
            self.lock.release()
            return
        return func(self, *args, **kwargs)
        self.lock.release()
    return dec
     
class SwiftHandler(TunnelEndpoint):
    
    def __init__(self, swift_process, api_callback=None):
        TunnelEndpoint.__init__(self, swift_process)
        self._api_callback = api_callback
        self._socket_running = -1
        self._resetting = False
        self._waiting_on_cmd_connection = False
        self.swift_queue = Queue.Queue()
        self._dequeueing = False
        self.started_downloads = Set()
        self.added_peers = Set()
        self.lock = RLock() # Reentrant Lock
        
    @property
    def swift(self):
        return self._swift
    
    @property
    def socket_running(self):
        return self._socket_running == 0
    
    @socket_running.setter
    def socket_running(self, state):
        self._socket_running = state
        self.do_callback(MESSAGE_KEY_SOCKET_STATE, self.address, state)
    
    def do_callback(self, key, *args, **kwargs):
        if self._api_callback is not None:
            self._api_callback(key, *args, **kwargs)
    
    @_swift_runnable_decorator
    def swift_add_peer(self, d, addr, sock_addr=None):
        """
        @type d: SwiftDownloadImpl
        @type addr: Address
        @type sock_addr: Address
        """
        if d is not None and not any([addr == a and d.get_def().get_roothash() == h and sock_addr == s for a, h, s in self.added_peers]):
            self._swift.add_peer(d, addr, sock_addr)
            self.added_peers.add((addr, d.get_def().get_roothash(), sock_addr))
    
    @_swift_runnable_decorator    
    def swift_checkpoint(self, d):
        """
        @type d: SwiftDownloadImpl
        """
        if d is not None:
            self._swift.checkpoint_download(d)
    
    @_swift_runnable_decorator  
    def swift_start(self, d):
        """
        @type d: SwiftDownloadImpl
        """
        if not d.get_def().get_roothash() in self.started_downloads:
            self.started_downloads.add(d.get_def().get_roothash())
            self._swift.start_download(d)
        else:
            logger.warning("This roothash %s was already started!", d.get_def().get_roothash_as_hex())
    
    @_swift_runnable_decorator  
    def swift_moreinfo(self, d, yes):
        """
        @type d: SwiftDownloadImpl
        @type yes: boolean
        """
        self._swift.set_moreinfo_stats(d, yes)
    
    @_swift_runnable_decorator
    def swift_remove_download(self, d, rm_state, rm_content):
        """
        @type d: SwiftDownloadImpl
        @type rm_state: boolean
        @type rm_content: boolean
        """
        if d.get_def().get_roothash() in self.started_downloads:
            self.started_downloads.remove(d.get_def().get_roothash())
            self._swift.remove_download(d, rm_state, rm_content)
    
    @_swift_runnable_decorator
    def swift_pex(self, d, enable):
        """
        @type d: SwiftDownloadImpl
        @type enable: boolean
        """
        self._swift.set_pex(d.get_def().get_roothash_as_hex(), enable)
        
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
            self.do_callback(MESSAGE_KEY_SWIFT_STATE, STATE_RESETTING, error=error)
            self.added_peers = Set() # Reset the peers added before restarting
            self.started_downloads = Set() # Reset the started downloads before restarting
            
            # Try the sockets to see if they are in use
            if not try_sockets([e.address for e in self.swift_endpoints], timeout=1.0):
                logger.warning("Socket(s) is/are still in use")
                self._swift.donestate = DONE_STATE_EARLY_SHUTDOWN
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
                
            self._dispersy.on_swift_restart(temp_queue)               
                            
            while not temp_queue.empty():
                self.swift_queue.put(temp_queue.get())
            
            self._waiting_on_cmd_connection = True
            self._swift.start_cmd_connection() # Normally in open
            self._resetting = False
        self.lock.release()
        
    def swift_started_running_callback(self):
        self.dequeue_swift_queue()
        
    def enqueue_swift_queue(self, func, *args, **kwargs):
        self.swift_queue.put((func, args, kwargs))
        
    def dequeue_swift_queue(self):
        self._dequeueing = True
        while not self.swift_queue.empty() and self._swift.is_ready():
            func, args, kargs = self.swift_queue.get()
            logger.debug("Dequeue %s %s %s", func, args, kargs)
            func(*args, **kargs)            
        self._dequeueing = False        

    def set_callbacks(self):
        self._swift.set_on_swift_restart_callback(self.restart_swift)
        self._swift.set_on_tcp_connection_callback(self.swift_started_running_callback)
        self._swift.set_on_sockaddr_info_callback(self.sockaddr_info_callback)
        
    def sockaddr_info_callback(self, address, state):
        logger.debug("Socket info callback %s %d", address, state)
        if state < 0 or address.ip == "AF_UNSPEC":
            logger.debug("Something is going on, but don't know what.")
        elif state == 0:
            logger.debug("Socket is bound and active")
            if address.resolve_interface():
                e = self.get_endpoint(address)
                if e is not None:
                    e.socket_running = state
                else:
                    logger.warning("This %s is not in %s", address, [e.address for e in self.swift_endpoints])
                self.dequeue_swift_queue()
            else:
                logger.debug("Might have been able to bind to something, but unable to resolve interface")
        elif state == 11: # We're overloading the buffer        
            logger.debug("Buffer overload!")
        elif state > 0:
            e = self.get_endpoint(address)
            if e is not None:
                e.socket_running = state
            if not address.resolve_interface():
                logger.debug("Cannot resolve interface")
            if try_socket(address):
                logger.debug("Yelp, socket is gone!")                
        
class CommonEndpoint(SwiftHandler, EndpointStatistics):
    
    def __init__(self, swift_process, api_callback=None):
        SwiftHandler.__init__(self, swift_process, api_callback)
        EndpointStatistics.__init__(self)
        self.address = Address()
            
    def is_bootstrap_candidate(self, addr=None, candidate=None):
        if addr is not None:
            if self._dispersy._bootstrap_candidates.get(addr.addr()) is not None:
                return True
        if candidate is not None:
            if (isinstance(candidate, BootstrapCandidate) or 
                self._dispersy._bootstrap_candidates.get(candidate.sock_addr) is not None):
                return True
        return False
    
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
        CommonEndpoint.__init__(self, swift_process, api_callback=api_callback)
        
        if swift_process:
            self.do_callback(MESSAGE_KEY_SWIFT_PID, swift_process.get_pid())
            self.set_callbacks()
            for addr in self._swift.listenaddrs:
                self.add_endpoint(addr, api_callback=api_callback)
    
    def get_address(self):
        if self._endpoint is None:
            return self.address.addr()
        else:
            return self._endpoint.get_address()
        
    def get_all_addresses(self):
        return list(endpoint.get_address() for endpoint in self.swift_endpoints)
    
    def send(self, candidates, packets):
        self.lock.acquire();
        if not self._swift.is_ready() or not self.socket_running:
            if not self._dequeueing:
                self.enqueue_swift_queue(self.send, candidates, packets)
                logger.debug("Send is queued")
            self.lock.release()
            return False
        logger.debug("Send %s %d", candidates, len(packets))
        
        # If filehash message, let SwiftCommunity know the peers!
        name = self._dispersy.convert_packet_to_meta_message(packets[0], load=False, auto_load=False).name
        # TODO: Should we only check packet 0? I.e. can packets of different kinds go together?
        if name == FILE_HASH_MESSAGE_NAME:
            self._dispersy.notify_filehash_peers([Address.tuple(c.sock_addr) for c in candidates])
        
        for c in candidates:
            new_c = self.determine_endpoint(c)
            send_success = self._endpoint.send([new_c], packets)
            self.update_dispersy_contacts_candidates_messages([new_c], packets, recv=False)
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
                # Upon closing, checkpoints are created for those downloads that need it
            else:
                logger.debug("Closing harshly")
                self._swift.donestate = DONE_STATE_EARLY_SHUTDOWN
                self._swift.network_shutdown() # Kind of harsh, so make sure downloads are handled
            # Try the sockets to see if they are in use
            if not try_sockets(self._swift.listenaddrs, timeout=1.0):
                logger.warning("Socket(s) is/are still in use")
                self._swift.network_shutdown() # End it at all cost
            
            self.do_callback(MESSAGE_KEY_SWIFT_STATE, STATE_STOPPED)
        
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
    
    def _last_endpoints(self, peer, endpoints=[]):
        """
        This function returns the endpoints that last had contact with this peer,
        sorted by time since the last contact, latest first
        
        @param peer: The address of the peer that a message will be sent to
        @type peer: Address
        @param endpoints: List of endpoints to use (defaults to self.swift_endpoints)
        @rtype: SwiftEndpoint
        @return: List(Endpoint) that last had contact with peer
        """
        if not endpoints:
            endpoints = self.swift_endpoints
        last_contacts = []
        for e in endpoints:
            for c in e.dispersy_contacts:
                if peer == c.address and c.last_contact() > datetime.min:
                    last_contacts.append((e, c.last_contact()))
        sorted_last_contacts = sorted(last_contacts, key=lambda x: x[1], reverse=True)
        return [lc[0] for lc in sorted_last_contacts]
    
    def _subnet_endpoints(self, peer, endpoints=[]):
        """
        This function returns the endpoints that reside in the same subnet.
        These are either point to point or local connections, which will likely be fastest(?).
        
        @type peer: Address 
        @param endpoints: List of endpoints to use (defaults to self.swift_endpoints)
        """
        if not endpoints:
            endpoints = self.swift_endpoints
        same_subnet = []
        for e in endpoints:
            if e.address.same_subnet(peer.ip):
                same_subnet.append(e)
        return same_subnet
    
    def _get_channel_speeds(self):
        """
        Get up/downspeed of each swift channel
        
        @rtype: List of ((socket_ip, socket_port), (peer_ip, peer_port), upspeed, downspeed)
        """
        r = []
        for d in self.swift.roothash2dl.values():
            if not isinstance(d, MultiEndpoint) and len(d.midict.values()) > 0: # Ensure there is something to get
                r.append(((d.midict.get("socket_ip", None), int(d.midict.get("socket_port", -1))),
                         (d.midict.get("ip", None), int(d.midict.get("port", -1))),
                         float(d.midict.get("cur_speed_up", 0)), float(d.midict.get("cur_speed_down", 0))))
        return r
    
    def _top_speed_endpoints(self, peer=None, endpoints=[]):
        """
        Determine which endpoints have a channel with this peer (or if None, all channels of this socket), 
        and sort them by combined up/download speed, returning only those with positive speeds
        
        @type peer: Address
        @param endpoints: List of endpoints to use (defaults to self.swift_endpoints)
        """
        if not endpoints: # []
            endpoints = self.swift_endpoints
        speeds = self._get_channel_speeds()
        r = []
        for e in endpoints:
            total = 0
            for saddr, paddr, up, down in speeds:
                if e.address.addr() == saddr and (peer is None or peer.addr() == paddr):
                    total += up + down
            if total > 0: # No point in adding endpoints with zero speed
                r.append((e, total))
        sorted_endpoints = sorted(r, key=lambda x: x[1], reverse=True) # Biggest first
        return [se[0] for se in sorted_endpoints] # Only return endpoints
        
    def determine_endpoint(self, candidate):
        """
        The endpoint that will take care of the task at hand, will be chosen here. 
        The chosen endpoint will be assigned to self._endpoint
        If no appropriate endpoint is found, the current endpoint will remain.
        Using self.dispersy_contacts it will also be determined which socket is best suited for this task,
        and this socket will be returned as Candidate
        
        @type peer: Candidate
        @rtype: Candidate
        """
        
        def recur(endpoint):
            if not endpoint.is_alive or not endpoint.socket_running:
                recur(self._next_endpoint(endpoint))
            return endpoint
        
        def determine(peer):
            # Choose the endpoint that currently has the highest transfer speed with this peer
            for e in self._top_speed_endpoints(peer):
                if e is not None and e.is_alive and e.socket_running:
                    logger.debug("Package will be sent with fastest endpoint %s", e)
                    return e
            # Choose the endpoint that had contact last with the peer
            for e in self._last_endpoints(peer):
                if e is not None and e.is_alive and e.socket_running:
                    logger.debug("Package will be sent with the last contacted endpoint %s", e)
                    return e
            # In case no contact has been made with this peer (or those endpoint are not available)
            for e in self._subnet_endpoints(peer):
                if e is not None and e.is_alive and e.socket_running:
                    logger.debug("Package will be sent with an endpoint, %s, in the same subnet", e)
                    return e            
            return recur(self._endpoint)
        
        if (len(self.swift_endpoints) == 0):
            self._endpoint = None
        elif (len(self.swift_endpoints) > 1):
            self._endpoint = determine(Address.tuple(candidate.sock_addr))
        else:
            self._endpoint = self.swift_endpoints[0]
        # TODO: Determine the best candidate for the job!
        return candidate
        
    def i2ithread_data_came_in(self, session, sock_addr, data, incoming_addr=Address()):
        logger.debug("Data came in with %s on %s from %s", session, incoming_addr, sock_addr)
        
        # Spoof sock_addr. Dispersy knows only about the first socket address of a peer, 
        # to keep things clean.
        contact = Address.tuple(sock_addr)
        for dc in self.dispersy_contacts:
            if dc.has_address(contact):
                sock_addr = dc.address.addr()
        
        e = self.get_endpoint(incoming_addr)
        if e is not None:
            e.i2ithread_data_came_in(session, sock_addr, data) # Ensure that you fool the SwiftEndpoint as well
            return
        # In case the incoming_addr does not match any of the endpoints
        TunnelEndpoint.i2ithread_data_came_in(self, session, sock_addr, data)
        
        self.update_dispersy_contacts([(contact, [data])], recv=True)
        
    def dispersythread_data_came_in(self, sock_addr, data, timestamp):
        self._dispersy.on_incoming_packets([(EligibleWalkCandidate(sock_addr, True, sock_addr, sock_addr, u"unknown"), data)], True, timestamp)
    
    def _loop(self):
        while not self._thread_stop_event.is_set():
            self.dequeue_swift_queue()
            self._thread_stop_event.wait(REPORT_DISPERSY_INFO_TIME)
            data = []
            for e in self.swift_endpoints:
                data.append({"address" : e.address, "total_send" : e._total_send, "total_up" : e._total_up, 
                             "total_down" : e._total_down})
            info = {"multiendpoint" : data}
            # TODO: List the data from DispersyContacts as well
            self.do_callback(MESSAGE_KEY_DISPERSY_INFO, info)
        
    def update_dispersy_contacts_candidates_messages(self, candidates, packets, recv=True):
        self.update_dispersy_contacts([(Address.tuple(c.sock_addr), packets) for c in candidates], recv)
        
    def update_dispersy_contacts(self, contacts_and_messages, recv=True):
        """
        Update the list of known dispersy contacts (excluding bootstrappers), with addresses and messages
        Note that if the list grows, the new addresses will be send a list of local sockets        
        Recv is used to determine wether the messages are incoming or outgoing
        @type contacts_and_messages: tuple(Address, Iterable(Packet))
        @type recv: boolean
        """
        logger.debug("Update known dispersy contacts, %s", [str(cam[0]) for cam in contacts_and_messages])
        self.lock.acquire()
        contacts = [DispersyContact(cam[0], recv_messages=cam[1]) if recv else DispersyContact(cam[0], send_messages=cam[1]) 
                    for cam in contacts_and_messages if isinstance(cam, tuple) 
                    and not self.is_bootstrap_candidate(addr=cam[0])]
        diff = []
        for c in contacts:
            if not any([dc.has_address(c.address) for dc in self.dispersy_contacts]): # Don't know this address
                diff.append(c)
                logger.info("New dispersy contact %s", c.address)
        self.dispersy_contacts.update(diff) # First update before sending them messages, just to be sure we don't start looping
        if diff: # Only useful if non empty
            self.send_addresses_to_communities([dc.address for dc in diff])
        self.lock.release()
    
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
                # TODO: Note that it is kind of superfluous to send when we have only one socket
                # TODO: Note also that we should consider only using active sockets
                self._dispersy.callback.register(c.create_addresses_messages, (1,message,candidates), 
                                                 kargs={"update":False}, delay=0.0)
                
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
    
    def restart_swift(self, error):
        SwiftHandler.restart_swift(self, error)
        for e in self.swift_endpoints: # We need to add the reference to the new swift to each endpoint
            e._swift = self._swift
        # TODO: This wasn't always necessary, what changed??
        
    def peer_endpoints_received(self, messages):
        for x in messages:
            addresses = [Address.unknown(a) for a in x.payload.addresses]
            for dc in self.dispersy_contacts:
                if dc.address in addresses:
                    dc.set_peer(Peer(addresses))
                    break # There should be only one dispersy endpoint with this address
    
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
            elif address.port == 0: # In case the port is zero, check for any confirmed address not in listenaddrs
                s = Set(self._swift.confirmedaddrs).difference(Set(self._swift.listenaddrs))
                for a in s:
                    if a.ip == self.address.ip: # If any matches the ip then claim this address as your own
                        self.address.set_port(a.port)
                        self.socket_running = 0
                        break 
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
        if self._swift is not None and self._swift.is_ready():
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
            
            # This contact may be spoofed by MultiEndpoint, which ensures that we don't have DispersyContacts
            # that resolve to the same peer
            self.dispersy_contacts.update([DispersyContact(Address.tuple(c.sock_addr), send_messages=packets)
                                           for c in candidates if isinstance(c.sock_addr, tuple)
                                           and not self.is_bootstrap_candidate(addr=Address.tuple(c.sock_addr), candidate=c)])
        
    def i2ithread_data_came_in(self, session, sock_addr, data):
        if isinstance(sock_addr, tuple):
            # This contact may be spoofed by MultiEndpoint, which ensures that we don't have DispersyContacts
            # that resolve to the same peer
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
            self.enqueue_swift_queue(self.swift_add_socket, addr)
        else:
            if not self.socket_running:
                self._swift.add_socket(self.address, True)
                    
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
                logger.debug("Bummer, %s is already bound!", str(addr))
            return False
        if error_number == EADDRNOTAVAIL: # Interface is most likely gone so nothing on this ip can be bound
            if log:
                logger.debug("Shit, %s can't be bound! Interface gone?", str(addr))
            return False
        if log:
            logger.debug("He, we haven't taken into account this error yet!!\n%s", error_message)
        return False
    finally:
        s.close()
    