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
        return [Message(self, u"mymessage", MemberAuthentication(encoding="sha1"), PublicResolution(), FullSyncDistribution(u"ASC", 127, True),
                         CommunityDestination(2), MyPayload(), self.check_callback, self.handle_callback)]
        
    def _short_member_id(self):
        return str(self.my_member.mid.encode("HEX"))[0:5]            
            
    def _port(self):
        return str(self.dispersy.endpoint.get_address()[1])
        
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
            print x.payload.data + "\n\treceiver_member_id: " + self._short_member_id() + ", receiver_port: " + self._port()
        #self.dispersy.callback.register(self.create_my_messages, (1,), delay=1.0 )
        
    def create_my_messages(self, count):
        meta = self.get_meta_message(u"mymessage")
        mymessage = "Message! sender_member_id: " + self._short_member_id()+", sender_port: " + self._port()
        messages = [meta.impl(authentication=(self.my_member,), distribution=(self.claim_global_time(), 1), payload=(mymessage,)) for _ in xrange(count)]
        self.dispersy.store_update_forward(messages, True, False, True)
        
    @property
    def dispersy_enable_candidate_walker(self):
        return False
    