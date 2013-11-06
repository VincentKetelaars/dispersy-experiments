'''
Created on Oct 11, 2013

@author: Vincent Ketelaars
'''

from dispersy.candidate import WalkCandidate

class EligibleWalkCandidate(WalkCandidate):
    '''
    classdocs
    '''
    def __init__(self, sock_addr, tunnel, lan_address, wan_address, connection_type):
        WalkCandidate.__init__(self, sock_addr, tunnel, lan_address, wan_address, connection_type)
        self.update_bloomfilter = -1
        
    def introduction_response_received(self):
        return self._timeout_adjustment == 0.0 and self._last_walk > 0.0
    
    def send_bloomfilter_update(self):
        return self.update_bloomfilter > 0
    
    def set_update_bloomfilter(self, update):
        self.update_bloomfilter = update
    