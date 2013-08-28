'''
Created on Aug 27, 2013

@author: Vincent Ketelaars
'''

from dispersy.endpoint import Endpoint

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
            
    
        
        