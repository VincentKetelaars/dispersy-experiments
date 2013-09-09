'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

from os.path import isfile

from dispersy.community import Community
from dispersy.conversion import DefaultConversion
from dispersy.message import Message
from dispersy.authentication import MemberAuthentication
from dispersy.resolution import PublicResolution
from dispersy.distribution import FullSyncDistribution
from dispersy.destination import CommunityDestination

from src.extend.conversion import SimpleFileConversion, FileHashConversion
from src.extend.payload import SimpleFileCarrier, SimpleFilePayload, FileHashPayload

import logging
logger = logging.getLogger()    

DISTRIBUTION_DIRECTION = u"ASC" # "ASC" or "DESC"
DISTRIBUTION_PRIORITY = 127
NUMBER_OF_PEERS_TO_SYNC = 3
HASH_LENGTH = 40
    
class MyCommunity(Community):
    '''
    classdocs
    '''

    SIMPLE_MESSAGE_NAME = u"simple_message"
    FILE_HASH_MESSAGE = u"file_hash_message"

    def __init__(self, dispersy, master_member):
        '''
        Constructor
        '''
        super(MyCommunity, self).__init__(dispersy, master_member)
        self._dest_dir = None
        
    def initiate_conversions(self):
        """
        Overwrite
        """
        return [DefaultConversion(self), SimpleFileConversion(self), FileHashConversion(self)]
    
    def initiate_meta_messages(self):
        """
        Overwrite
        """
        self._simple_distribution = FullSyncDistribution(DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, True)
        self._file_hash_distribution = FullSyncDistribution(DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, True)
        return [Message(self, self.SIMPLE_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), self._simple_distribution,
                         CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), SimpleFilePayload(), self.simple_message_check, self.simple_message_handle),
                Message(self, self.FILE_HASH_MESSAGE, MemberAuthentication(encoding="sha1"), PublicResolution(), self._file_hash_distribution,
                         CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), FileHashPayload(), self.file_hash_check, self.file_hash_handle)]
        
    def simple_message_check(self, messages):
        """
        Check Callback
        """
        for x in messages:
            yield x
    
    def simple_message_handle(self, messages):
        """
        Handle Callback
        """
        for x in messages:
            print x.payload.filename +": "+x.payload.data
            
    def file_hash_check(self, messages):
        for x in messages:
            yield x
    
    def file_hash_handle(self, messages):
        for x in messages:
            self.dispersy.endpoint.start_download(x.payload.filename, x.payload.hash, x.payload.address, self._dest_dir)
            
    def _short_member_id(self):
        return str(self.my_member.mid.encode("HEX"))[0:5]     
    
    def _address(self):
        return self.dispersy.endpoint.get_address()     
            
    def _port(self):
        return str(self.dispersy.endpoint.get_address()[1])       
     
    def create_simple_messages(self, count, message=None):
        if message is not None:
            meta = self.get_meta_message(self.SIMPLE_MESSAGE_NAME)
            messages = [meta.impl(authentication=(self.my_member,), distribution=(self.claim_global_time(), self._simple_distribution.claim_sequence_number()), 
                                  payload=(message.filename, message.data)) for _ in xrange(count)]
            self.dispersy.store_update_forward(messages, True, False, True)
        
    def create_file_hash_messages(self, count, file_hash_message):
        # Make sure you have the filename, and a proper hash
        if isfile(file_hash_message.filename):
            # Let Swift know that it should seed this file
            # Get a hash of the file 
            roothash = self.dispersy.endpoint.get_hash(file_hash_message.filename)
            self.dispersy.endpoint.add_file(file_hash_message.filename, roothash)
            
            if roothash is not None and len(roothash) == HASH_LENGTH:
                # Send this hash to candidates (probably do the prior stuff out of the candidates loop)
                meta = self.get_meta_message(self.FILE_HASH_MESSAGE)
                messages = [meta.impl(authentication=(self.my_member,), distribution=(self.claim_global_time(), self._file_hash_distribution.claim_sequence_number()), 
                                      payload=(file_hash_message.filename, roothash, self._address())) for _ in xrange(count)]
                self.dispersy.store_update_forward(messages, True, False, True)
        
    @property
    def dispersy_enable_candidate_walker(self):
        return False
    
    @property
    def dispersy_enable_candidate_walker_responses(self):
        # initialization and nat meta messages will still be created
        return True
    
    @property
    def dest_dir(self):
        return self._dest_dir
    
    @dest_dir.setter
    def dest_dir(self, dest_dir):
        self._dest_dir = dest_dir
    