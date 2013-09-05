'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''

from os import makedirs, urandom
from os.path import isfile, isdir, dirname, basename
from time import time
import binascii

from dispersy.endpoint import Endpoint, TunnelEndpoint
from dispersy.statistics import Statistics
from Tribler.Core.Swift.SwiftDef import SwiftDef

from src.extend.swift_download_config import FakeSession, FakeSessionSwiftDownloadImpl

import logging
logger = logging.getLogger()

class NoEndpointAvailableException(Exception):
    pass

class EndpointStatistics(Statistics):
    
    def __init__(self):
        self._start_time = time()
        self._is_alive = False # The endpoint is alive between open and close
        self._id = urandom(16)
        
    def update(self):
        pass
    
    @property
    def is_alive(self):
        return self._is_alive
    
    @is_alive.setter
    def is_alive(self, is_alive):
        self._is_alive = is_alive
        
    @property
    def id(self):
        self._id

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
        self._endpoints.append(endpoint);
        if len(self._endpoints) == 1:
            self._endpoint = endpoint
            
    def remove_endpoint(self, endpoint):
        """
        Remove endpoint.
        """
        assert isinstance(endpoint, Endpoint), type(endpoint)
        for e in self._endpoints:
            if e == endpoint:
                if e.is_alive:
                    e.close()
                self._endpoints.remove(e)
                if len(self._endpoints) == 0:
                    self._endpoint = None
                break
    
    def get_address(self):
        if self._endpoint is None:
            return ("0.0.0.0", -1)
        else:
            return self._endpoint.get_address()
    
    def send(self, candidates, packets):
        self.determine_endpoint(False)
        self._endpoint.send(candidates, packets)
            
    def open(self, dispersy):
        for x in self._endpoints:
            x.open(dispersy)
    
    def close(self, timeout=0.0):
        for x in self._endpoints:
            x.close(timeout)
            
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
    
    def determine_endpoint(self, swift):
        """
        The endpoint that will take care of the task at hand, will be chosen here. 
        The chosen endpoint will be assigned to self._endpoint
        No recursion fail safe mechanism. Make sure that if you ask for swift, such an endpoint is available
        """
        if (len(self._endpoints) == 0):
            raise NoEndpointAvailableException()
        elif (len(self._endpoints) > 1):
            self._endpoint = self._next_endpoint()
            if swift and not isinstance(self._endpoint, SwiftEndpoint):
                self.determine_endpoint(swift)
        else:
            pass # Number of endpoints is 1, self._endpoint stays employed!
    
    def add_file(self, filename):
        self.determine_endpoint(True)
        return self._endpoint.add_file(filename)
        
    def add_peer(self, addr):
        self.determine_endpoint(True)
        self._endpoint.add_peer(addr)
            
    def start_download(self, filename, roothash, address, dest_dir):
        self.determine_endpoint(True)
        self._endpoint.start_download(filename, roothash, address, dest_dir)    
    
class SwiftEndpoint(TunnelEndpoint, EndpointStatistics):
    
    def __init__(self, swift_process, binpath):
        super(SwiftEndpoint, self).__init__(swift_process)
        EndpointStatistics.__init__(self)
        
        self._swift_path = binpath
        
        # This object must have: get_def, get_selected_files, get_max_speed, get_swift_meta_dir
        d = FakeSessionSwiftDownloadImpl(FakeSession())
        d.setup()
        # get_selected_files is initialized to empty list
        # get_max_speed for UPLOAD and DOWNLOAD are set to 0 initially (infinite)
        d.set_swift_meta_dir(None)
        self._d = d
        
    def send(self, candidates, packets):
        TunnelEndpoint.send(self, candidates, packets)
    
    def open(self, dispersy):
        super(SwiftEndpoint, self).open(dispersy)
        self._swift.start_cmd_connection()
        self.is_alive = True
        
    def close(self, timeout=0.0):
        self._swift.remove_download(self, True, True)
        self._swift.early_shutdown()
        super(TunnelEndpoint, self).close(timeout)
        self.is_alive = False
    
    def get_address(self):
        # Dispersy retrieves the local ip
        return (self._dispersy.lan_address[0],self._swift.get_listen_port())
        
    def add_file(self, filename):
        """
        This method lets the swiftprocess know that an additional file is available. 
        It returns the roothash of this file
        """
        if isfile(filename):
            sdef = SwiftDef()
            sdef.add_content(filename)
            sdef.finalize(self._swift_path, destdir=dirname(filename))
            self._d.set_def(sdef)
            self._d.set_dest_dir(filename)
            self._swift.start_download(self._d)
            
            # returning get_roothash() gives an error somewhere (perhaps message?)
            return sdef.get_roothash_as_hex()
        return None
    
    def add_peer(self, addr):
        self._swift.add_peer(self._d, addr)        
    
    def start_download(self, filename, roothash, address, dest_dir):
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        self._d.set_dest_dir(dest_dir + "/" + basename(filename))
        self._d.set_def(SwiftDef(roothash=roothash))
        self._swift.start_download(self._d)
    