'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import binascii
import os
from datetime import datetime
from random import randint

from src.address import Address
from src.logger import get_logger
from dispersy.destination import CommunityDestination, CandidateDestination

logger = get_logger(__name__)
    
class Peer(object):
    
    def __init__(self, lan_addresses, wan_addresses=[], ids=[]):
        if len(lan_addresses) == len(ids): # This should ensure that wan_addresses is also equal
            self._lan_addresses = dict(zip(ids, lan_addresses))
            self._wan_addresses = dict(zip(ids, wan_addresses))
        else: # Assume no wan_addresses and no ids
            # Fake IDs shouldn't be a problem, because we are not going to look for fake ids either
            # Understand that the fake ids are ints, whereas the real ones are raw bytes
            self._lan_addresses = dict(zip(self._random_keys(len(lan_addresses)), lan_addresses))
            self._wan_addresses = self._lan_addresses
            
    def _random_keys(self, length):
        return [randint(0, 1000000) for _ in range(length)]
            
    @property
    def addresses(self):
        return self._wan_addresses.values()
    
    def get(self, id_):
        return (self._lan_addresses.get(id_, None), self._wan_addresses.get(id_, None))
    
    def get_id(self, address):
        for i, a in self._lan_addresses.iteritems():
            if a == address:
                return i
        for i, a in self._wan_addresses.iteritems():
            if a == address:
                return i
        return None
    
    def matches(self, peer):
        assert isinstance(peer, Peer)
        return self.has_any(peer._lan_addresses.values(), peer._lan_addresses.keys())
            
    def merge(self, peer):
        self._lan_addresses.update(peer._lan_addresses)
        self._wan_addresses.update(peer._wan_addresses)

    def __eq__(self, other):
        if not isinstance(other, Peer):
            return False
        # Only if each address in other matches an address in this, do they match
        return len(self.addresses) == len(other.addresses) and all([o in self.addresses for o in other.addresses])
    
    def __hash__(self):
        h = hash(None)
        for a in self.addresses:
            h |= hash(a)
        return h
    
    def has_any(self, addrs=[], ids=[]):
        """
        Return whether any of these addresses is the same as any of this _peers'
        @param addrs: List(Address)
        """
        for i, a in self._lan_addresses.iteritems():
            if i in ids or a in addrs:
                return True
        for i, a, in self._wan_addresses.iteritems():
            if i in ids or a in addrs:
                return True
        return False

class Download(object):
    '''
    This class represents a Download object
    Only the _peers should be allowed to download this object.
    Peers are only added if allowed by the destination.
    '''

    def __init__(self, roothash, filename, downloadimpl, size, timestamp, directories="", seed=False, download=False, moreinfo=True, destination=None, priority=0):
        '''
        Constructor
        '''
        self._roothash = roothash        
        self._filename = None if filename is None else os.path.basename(filename)
        self._directories = directories
        if directories == "":
            self._directories = "" if filename is None else os.path.split(filename)[0] # Everything before the final slash
        self._seed = seed
        self._download = download
        self._downloadimpl = downloadimpl
        self._peers = set() # Set of Peers
        self._size = size
        self._timestamp = timestamp
        self._priority = priority
        
        self._start_time = datetime.max
        self._finished_time = datetime.max
            
        self._destination = destination
        self._swift_running = False
        self._bad_swarm = False
        self._active_channels = set()
        
    @property
    def roothash(self):
        return self._roothash
    
    @property
    def filename(self):
        return self._filename
    
    @property
    def downloadimpl(self):
        return self._downloadimpl
    
    @property
    def size(self):
        return self._size
    
    @property
    def timestamp(self):
        return self._timestamp
    
    @property
    def priority(self):
        return self._priority
        
    def roothash_as_hex(self):
        return None if self.roothash is None else binascii.hexlify(self.roothash)
    
    def has_started(self):
        return self._start_time < datetime.max
    
    def set_started(self):
        if self._start_time == datetime.max:
            self._start_time = datetime.utcnow()
            return True
        else:
            return False
    
    def is_finished(self):
        return self._finished_time < datetime.max
    
    def set_finished(self):
        if self._finished_time == datetime.max:
            self._finished_time = datetime.utcnow()
            return True
        else:
            return False
        
    def is_download(self):
        return self._download
    
    def seeder(self):
        return self._seed
    
    def path(self):
        return os.path.join(self._directories, self._filename)
    
    def set_bad_swarm(self, bad):
        self._bad_swarm = bad
        self._swift_running = False # Should not be necessary, because no moreinfo will get through
    
    def is_bad_swarm(self):
        return self._bad_swarm
    
    def got_moreinfo(self):
        if self.set_started():
            self._swift_running = True
        # TODO: Handle paused downloads
        for c in self.downloadimpl.midict.get("channels", []):
            self._active_channels.add((Address(ip=c["socket_ip"], port=int(c["socket_port"])), 
                                       Address(ip=c["ip"], port=int(c["port"])))) # TODO: Add IPv6
    
    def add_address(self, address):
        assert isinstance(address, Address)
        if self.known_address(address):
            return
        self.add_peer(Peer([address]))
            
    def community_destination(self):
        return isinstance(self._destination, CommunityDestination.Implementation)
    
    def candidate_destination(self):
        return isinstance(self._destination, CandidateDestination.Implementation)
    
    def allowed_addresses(self):
        if isinstance(self._destination, CandidateDestination.Implementation):
            return [Address.tuple(c.sock_addr) for c in self._destination._candidates]
        return None # We're not returning a list if this is not a candidatedestination.. Deal with it
    
    def determine_seeding(self):
        """
        Only call this method if we received this information from another peer,
        because of |allowed_addresses| > 1
        """      
        # We should share if either community destination or if we are not the only on in the candidate destination
        share = self._destination is None or self.community_destination() or (self.candidate_destination() and 
                                                                              len(self.allowed_addresses()) > 1)
        # TODO: We should use the relay distribution to figure out who's also entitled to this download
        self._seed = self._seed and share
        
    def _allow_peer(self, peer):
        """
        Allow _peers when we're seeding and if at least one of their addresses corresponds to the candidate destination
        """
        assert isinstance(peer, Peer)
        if len(peer.addresses) == 0 or not self._seed: # If we're not seeding, we're not allowing!
            return False
        if self.community_destination():
        # TODO: Verify that the peer actually is part of this community
            return True
        elif self.candidate_destination():
            allowed = self.allowed_addresses()
            for a in peer.addresses:
                if a in allowed:
                    return True
        return False # Destination is None, unknown or none of the addresses are in allowed_addresses
    
    def add_peers(self, peers):
        for p in peers:
            self.add_peer(p)
        
    def add_peer(self, peer):
        if peer is not None and self._allow_peer(peer):
            self._peers.add(peer)
        else:
            logger.debug("Peer %s is not allowed", peer)
        
    def peers(self):
        return self._peers
    
    def merge_peers(self, new_peer):
        if new_peer is not None and self._allow_peer(new_peer) and not new_peer in self._peers:
            diff = set([p for p in self._peers if p.matches(new_peer)]) # If any addresses or endpoints are the same
            self._peers.difference_update(diff)
            for p in diff:
                new_peer.merge(p) # Any other addresses belong to this new peer now as well
            self._peers.add(new_peer)
            
    def known_address(self, addr):
        assert isinstance(addr, Address)
        return addr in [a for p in self._peers for a in p.addresses]
    
    def running_on_swift(self):
        return self._swift_running

    def removed_from_swift(self):
        self._swift_running = False
        
    def active(self):
        return self._swift_running and len(self._active_channels) > 0
    
    def active_sockets(self):
        return [c[0] for c in self._active_channels]
    
    def active_addresses(self):
        return [c[1] for c in self._active_channels]
    
    def inactive_addresses(self):
        return set([a for p in self._peers for a in p.addresses]).difference(self.active_addresses())
        
    def active_peers(self):
        return [p for p in self._peers if p.has_any(self.active_addresses())]
        
    def package(self):
        """
        @return dictionary with data from this class
        """
        data = {"filename" : self.filename, "roothash" : self.roothash_as_hex(), "seeding" : self.seeder(), "path" : self.path(), 
                "leeching" : not self.is_finished(), "dynasize" : self.downloadimpl.get_dynasize(),                        
                "progress" : self.downloadimpl.get_progress(),                             
                "current_speed_down" : self.downloadimpl.speed("down"),
                "current_speed_up" : self.downloadimpl.speed("up"),   
                "leechers" : self.downloadimpl.numleech, "seeders" : self.downloadimpl.numseeds,
                "channels" : len(self._active_channels),
                "moreinfo" : self.downloadimpl.network_create_spew_from_channels()}
        return data
    
    def channel_closed(self, socket_addr, peer_addr):
        try:
            self._active_channels.remove((socket_addr, peer_addr))
        except KeyError:
            logger.warning("%s, %s channel should have been in the active channels set", socket_addr, peer_addr)
        