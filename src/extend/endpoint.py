'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''

from os.path import isfile

from dispersy.endpoint import Endpoint, TunnelEndpoint
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Swift.SwiftDownloadImpl import SwiftDownloadImpl
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.Swift.SwiftProcess import SwiftProcess

from src.extend.swift_download_config import FakeSession, FakeSessionSwiftDownloadImpl

import logging
logger = logging.getLogger()

class NoEndpointAvailableException(Exception):
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
        self._endpoints.append(endpoint);
        if len(self._endpoints) == 1:
            self._endpoint = endpoint
            
    def remove_endpoint(self, endpoint):
        """
        Remove endpoint. The endpoint needs some kind of identifier for this
        """
        assert isinstance(endpoint, Endpoint), type(endpoint)
        pass
    
    def get_address(self):
        if self._endpoint is None:
            return ("0.0.0.0", -1)
        else:
            return self._endpoint.get_address()
    
    def send(self, candidates, packets):
        if (len(self._endpoints) == 0):
            raise NoEndpointAvailableException()
        elif (len(self._endpoints) == 1):
            self._endpoint.send(candidates, packets)
        else:
            self._endpoint = self._next_endpoint()
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
            
    
class SwiftEndpoint(TunnelEndpoint):
    
    def __init__(self, swift_process):
        super(SwiftEndpoint, self).__init__(swift_process)
        
        # This object must have: get_def, get_selected_files, get_max_speed, get_swift_meta_dir
        d = FakeSessionSwiftDownloadImpl(FakeSession())
        d.setup()
        # get_selected_files is initialized to empty list
        # get_max_speed for UPLOAD and DOWNLOAD are set to 0 initially (infinite)
        d.set_swift_meta_dir("/home/vincent/Desktop/tests_dest")
        d.set_dest_dir("/home/vincent/Desktop/tests_dest")
        self._d = d
    
    def open(self, dispersy):
        super(SwiftEndpoint, self).open(dispersy)
        self._swift.start_cmd_connection()        
        
    def add_file(self, filename):
        """
        This method lets the swiftprocess know that an additional file is available. 
        It returns the roothash of this file
        """
        if isfile(filename):
            roothash = self.get_roothash(filename)
            tracker = None
            chunksize = None
            duration = None
            sd = SwiftDef(roothash, tracker, chunksize, duration)
            
            self._d.set_def(sd)
            self._swift.start_download(self._d)
            return roothash
        return None
        
    def get_roothash(self, filename):
        return "00000000000000000000"
    
    def start_download(self, filename, roothash, address):
        logger.info("Start download: " +  filename +" : "+ roothash + address)
        
    