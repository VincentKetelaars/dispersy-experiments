'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import binascii
from datetime import datetime
from sets import Set

class Download(object):
    '''
    This class is represents a Download object
    '''

    def __init__(self, roothash, filename, downloadimpl, directories="", seed=False, download=False):
        '''
        Constructor
        '''
        self._roothash = roothash
        self._filename = filename
        self._directories = directories
        self._seed = seed
        self._download = download
        self._downloadimpl = downloadimpl
        self._peers = Set()
        
        self._start_time = datetime.now()
        self._finished_time = None
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
        return self._finished_time is not None
    
    def set_finished(self):
        if self._finished_time is None:
            self._finished_time = datetime.now()
            return True
        else:
            return False
    
    def seeder(self):
        return self._seed
    
    def path(self):
        return self._directories + self._filename
        
    def add_peer(self, addr):
        if addr is not None:
            # TODO: Make sure that it is a proper address
            self._peers.add(addr)
        
    def peers(self):
        return self._peers
        