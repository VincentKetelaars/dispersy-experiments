'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

from dispersy.community import Community
from dispersy.conversion import DefaultConversion
from dispersy.message import Message
from dispersy.authentication import MemberAuthentication
from dispersy.resolution import PublicResolution
from dispersy.distribution import FullSyncDistribution
from dispersy.destination import CommunityDestination

from src.extend.conversion import MyConversion
from src.extend.payload import MyPayload

import logging
logger = logging.getLogger()

class MyCommunity(Community):
    '''
    classdocs
    '''


    def __init__(self, dispersy, master_member):
        '''
        Constructor
        '''
        super(MyCommunity, self).__init__(dispersy, master_member)
        
    def initiate_conversions(self):
        """
        Overwrite
        """
        return [DefaultConversion(self), MyConversion(self)]
    
    def initiate_meta_messages(self):
        """
        Overwrite
        """
        self._distribution = FullSyncDistribution(u"ASC", 127, True)
        return [Message(self, u"mymessage", MemberAuthentication(encoding="sha1"), PublicResolution(), self._distribution,
                         CommunityDestination(2), MyPayload(), self.check_callback, self.handle_callback)]
        
    def check_callback(self, messages):
        """
        Check Callback
        """
        for x in messages:
            yield x
    
    def handle_callback(self, messages):
        """
        Handle Callback
        """
        for x in messages:
            print x.payload.data    
            
    def _short_member_id(self):
        return str(self.my_member.mid.encode("HEX"))[0:5]            
            
    def _port(self):
        return str(self.dispersy.endpoint.get_address()[1])       
     
    def create_my_messages(self, count, message=None):
        if message is None:
            logger.info("The message is empty!")
            message = "Message! sender_member_id: " + self._short_member_id()+", sender_port: " + self._port()
        meta = self.get_meta_message(u"mymessage")
        messages = [meta.impl(authentication=(self.my_member,), distribution=(self.claim_global_time(), self._distribution.claim_sequence_number()), 
                              payload=(message,)) for _ in xrange(count)]
        self.dispersy.store_update_forward(messages, True, False, True)
        
    @property
    def dispersy_enable_candidate_walker(self):
        return False
    
    @property
    def dispersy_enable_candidate_walker_responses(self):
        # initialization and nat meta messages will still be created
        return True
    