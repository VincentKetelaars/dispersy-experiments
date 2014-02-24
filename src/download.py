'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import binascii
import os
from datetime import datetime, timedelta

from dispersy.destination import CommunityDestination, CandidateDestination
from src.address import Address
from src.definitions import DOWNLOAD_MOREINFO_UPDATE

from src.logger import get_logger
logger = get_logger(__name__)

class Download(object):
    '''
    This class represents a Download object
    Only the _peers should be allowed to download this object.
    Peers are only added if allowed by the destination.
    '''

    def __init__(self, roothash, filename, downloadimpl, size, timestamp, community_id, directories="", seed=False, 
                 download=False, moreinfo=True, destination=None, priority=0):
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
        self._size = size
        self._timestamp = timestamp
        self._priority = priority
        self._communit_id = community_id
        
        self._start_time = datetime.max
        self._finished_time = datetime.max
            
        self._destination = destination
        self._last_moreinfo = datetime.min
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
    
    def is_usefull(self):
        return self.downloadimpl.is_usefull()
    
    def seeder(self):
        return self._seed
    
    def path(self):
        return os.path.join(self._directories, self._filename)
    
    def is_bad_swarm(self):
        return self.downloadimpl.bad_swarm
    
    def got_moreinfo(self):
        self.set_started()
        self._last_moreinfo = datetime.utcnow()
        for c in self.downloadimpl.midict.get("channels", []):
            self._active_channels.add((Address.tuple((c["socket_ip"], c["socket_port"])), 
                                       Address.tuple((c["ip"], c["port"])))) # Tuple can handle both ipv4 and ipv6 (port can be string)
            
    def community_destination(self):
        return isinstance(self._destination, CommunityDestination.Implementation)
    
    def candidate_destination(self):
        return isinstance(self._destination, CandidateDestination.Implementation)
    
    def allowed_addresses(self):
        if isinstance(self._destination, CandidateDestination.Implementation):
            return [Address.tuple(c.sock_addr) for c in self._destination._candidates]
        return None # We're not returning a list if this is not a candidatedestination.. Deal with it
    
    def running_on_swift(self):
        return self._last_moreinfo + timedelta(seconds=DOWNLOAD_MOREINFO_UPDATE * 2) > datetime.utcnow()
        
    def active(self):
        return self.running_on_swift() and len(self._active_channels) > 0
    
    def active_sockets(self):
        return [c[0] for c in self._active_channels]
    
    def active_addresses(self):
        return [c[1] for c in self._active_channels]
        
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
        