'''
Created on Oct 11, 2013

@author: Vincent Ketelaars
'''

from dispersy.candidate import WalkCandidate
from src.logger import get_logger

logger = get_logger(__name__)

class EligibleWalkCandidate(WalkCandidate):
    '''
    classdocs
    '''
    def __init__(self, sock_addr, tunnel, lan_address, wan_address, connection_type):
        WalkCandidate.__init__(self, sock_addr, tunnel, lan_address, wan_address, connection_type)
        self.update_bloomfilter = -1
        self.timeout = None
        self.intro_response_recv = False
        
    def introduction_response_received(self):
        return self.intro_response_recv
    
    def send_bloomfilter_update(self):
        return self.update_bloomfilter > 0
    
    def set_update_bloomfilter(self, update):
        self.update_bloomfilter = update
        
    def set_timeout(self, timeout):
        self.timeout = timeout
        
    def walk_response(self):
        logger.debug("Introduction response received %s", self.sock_addr)
        self.intro_response_recv = True
        if self.timeout is not None:
            self.timeout.stop()
        WalkCandidate.walk_response(self)
    