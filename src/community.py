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

from conversion import MyConversion
from payload import MyPayload

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
            print x.payload.data + " : " + self._short_member_id()
        
    def create_my_messages(self, count):
        meta = self.get_meta_message(u"mymessage")
        mymessage = self._short_member_id()+": mymessage!!!!"
        messages = [meta.impl(authentication=(self.my_member,), distribution=(self.claim_global_time(), 1), payload=(mymessage,)) for x in xrange(count)]
        self.dispersy.store_update_forward(messages, True, True, True)
    