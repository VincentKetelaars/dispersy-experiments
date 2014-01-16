'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import binascii
import os
from datetime import datetime
from sets import Set

from src.address import Address
from src.logger import get_logger
from dispersy.destination import CommunityDestination, CandidateDestination

logger = get_logger(__name__)
    
class Peer(object):
    
    def __init__(self, addresses):
        self.addresses = Set()
        if addresses is not None:
            self.addresses = Set(addresses)
            
    def merge(self, peer):
        for a in peer.addresses:
            self.addresses.add(a)

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

class Download(object):
    '''
    This class represents a Download object
    Only the peers should be allowed to download this object.
    Peers are only added if allowed by the destination.
    '''

    def __init__(self, roothash, filename, downloadimpl, directories="", seed=False, download=False, moreinfo=True, destination=None, size=-1):
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
        self._peers = Set() # Set of Peers
        self._size = size
        
        self._start_time = datetime.utcnow()
        self._finished_time = datetime.max
        if not download:
            self._finished_time = self._start_time
            
        self.moreinfo = moreinfo
        self._destination = destination
        self.cleaned = False # True when this download has been cleaned up
        self._bad_swarm = False
        self._active_sockets = Set()
        self._active_addresses = Set()
        
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
    
    def roothash_as_hex(self):
        return None if self.roothash is None else binascii.hexlify(self.roothash)
    
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
    
    def is_bad_swarm(self):
        return self._bad_swarm
    
    def got_moreinfo(self):
        channels = []
        try:
            channels = self.downloadimpl.midict["channels"]
        except:
            pass
        for c in channels:
            self._active_addresses.add(Address(ip=c["ip"], port=c["port"])) # TODO: Add IPv6
            self._active_sockets.add(Address(ip=c["socket_ip"], port=c["socket_port"]))
    
    def started(self):
        return len(self._active_addresses) > 0
    
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
        return None
    
    def determine_seeding(self):
        """
        Only call this method if we received this information from another peer,
        because of |allowed_addresses| > 1
        """      
        # We should share if either community destination or if we are not the only on in the candidate destination
        share = self._destination is None or self.community_destination() or (self.candidate_destination() and len(self.allowed_addresses()) > 1)
        # TODO: We should use the relay distribution to figure out who's also entitled to this download
        self._seed = self._seed and share
        
    def _allow_peer(self, peer):
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
            diff = Set()
            for peer in self._peers:
                if any([a in peer.addresses for a in new_peer.addresses]):
                    diff.add(peer)
            self._peers.difference_update(diff)
            for p in diff:
                new_peer.merge(p) # Any other addresses belong to this new peer now as well
            self._peers.add(new_peer)
            
    def known_address(self, addr):
        assert isinstance(addr, Address)
        return addr in [a for p in self._peers for a in p.addresses]
    
    def speed(self, direction):
        try:
            return self.downloadimpl.get_current_speed(direction)
        except:
            logger.debug("Could not fetch speed %s", direction)
            return 0
    
    def total(self, direction, raw=False):
        try:
            return self.downloadimpl.midict[("raw_" if raw else "") + "bytes_" + direction] / 1024.0
        except:
            logger.debug("Could not fetch total %s %s", direction, raw)
            return 0
    
    def package(self):
        """
        @return dictionary with data from this class
        """
        data = {"filename" : self.filename, "roothash" : self.roothash_as_hex(), "seeding" : self.seeder(), "path" : self.path(), 
                "leeching" : not self.is_finished(), "dynasize" : self.downloadimpl.get_dynasize(),                        
                "progress" : self.downloadimpl.get_progress(),                             
                "current_down_speed" : self.downloadimpl.get_current_speed("down"),
                "current_up_speed" : self.downloadimpl.get_current_speed("up"),   
                "leechers" : self.downloadimpl.numleech, "seeders" : self.downloadimpl.numseeds,
                "moreinfo" : self.downloadimpl.network_create_spew_from_channels()}
        return data
        