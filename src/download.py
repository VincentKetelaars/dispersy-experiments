'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import binascii
import os
from datetime import datetime
from sets import Set

from src.address import Address
    
class Peer(object):
    
    def __init__(self, addresses):
        self.addresses = Set()
        if addresses is not None:
            self.addresses = Set(addresses)

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
    '''

    def __init__(self, roothash, filename, downloadimpl, directories="", seed=False, download=False):
        '''
        Constructor
        '''
        self._roothash = roothash
        self._filename = os.path.basename(filename)
        self._directories = directories
        if directories == "":
            self._directories = os.path.split(filename)[0] # Everything before the final slash
        self._seed = seed
        self._download = download
        self._downloadimpl = downloadimpl
        self._peers = Set() # Set of Peers
        
        self._start_time = datetime.utcnow()
        self._finished_time = datetime.max
        if not download:
            self._finished_time = self._start_time
            
        self.moreinfo = True
        
    @property
    def roothash(self):
        return self._roothash
    
    @property
    def filename(self):
        return self._filename
    
    @property
    def downloadimpl(self):
        return self._downloadimpl
    
    def roothash_as_hex(self):
        return binascii.hexlify(self.roothash)
    
    def is_finished(self):
        return self._finished_time < datetime.max
    
    def set_finished(self):
        if self._finished_time == datetime.max:
            self._finished_time = datetime.utcnow()
            return True
        else:
            return False
    
    def seeder(self):
        return self._seed
    
    def path(self):
        return self._directories + self._filename
    
    def add_address(self, address):
        if address is not None and isinstance(address, Address):
            for peer in self._peers:
                if address in peer.addresses:
                    return
            self._peers.add(Peer([address]))
        
    def add_peer(self, peer):
        if peer is not None and isinstance(peer, Peer) and len(peer.addresses) > 0:
            self._peers.add(peer)
        
    def peers(self):
        return self._peers
    
    def merge_peers(self, new_peer):
        if new_peer is not None and len(new_peer.addresses) > 0 and not new_peer in self._peers:
            diff = Set()
            for peer in self._peers:
                if any([a in peer.addresses for a in new_peer.addresses]):
                    diff.add(peer)
            self._peers.difference_update(diff)
            self._peers.add(new_peer)
    
    def package(self):
        """
        @return dictionary with data from this class
        """
        data = {"filename" : self.filename, "roothash" : self.roothash_as_hex(), "seeding" : self.seeder(), "path" : self.path(), 
                "leeching" : self.is_finished(), "dynasize" : self.downloadimpl.get_dynasize(),                        
                "progress" : self.downloadimpl.get_progress(),                             
                "current_down_speed" : self.downloadimpl.get_current_speed("down"),
                "current_up_speed" : self.downloadimpl.get_current_speed("up"),   
                "leechers" : self.downloadimpl.numleech, "seeders" : self.downloadimpl.numseeds,                                   
                "total_up" : self.downloadimpl.get_total_up(), "total_down" : self.downloadimpl.get_total_down(),
                "channels" : self.downloadimpl.network_create_spew_from_channels()}
        return data
        