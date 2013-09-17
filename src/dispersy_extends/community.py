'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''

from os.path import isfile, basename

from dispersy.community import Community
from dispersy.conversion import DefaultConversion
from dispersy.message import Message
from dispersy.authentication import MemberAuthentication
from dispersy.resolution import PublicResolution
from dispersy.distribution import FullSyncDistribution
from dispersy.destination import CommunityDestination

from src.dispersy_extends.conversion import SimpleFileConversion, FileHashConversion
from src.dispersy_extends.payload import SimpleFilePayload, FileHashPayload

from src.definitions import DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, NUMBER_OF_PEERS_TO_SYNC, HASH_LENGTH, FILE_HASH_MESSAGE_NAME, SIMPLE_MESSAGE_NAME

import logging
logger = logging.getLogger(__name__)    
    
class MyCommunity(Community):
    '''
    classdocs
    '''

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
        return [Message(self, SIMPLE_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), self._simple_distribution,
                         CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), SimpleFilePayload(), self.simple_message_check, self.simple_message_handle),
                Message(self, FILE_HASH_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), self._file_hash_distribution,
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
            if len(x.payload.filename) >= 1 and x.payload.directories is not None and len(x.payload.roothash) == HASH_LENGTH:
                self.dispersy.endpoint.start_download(x.payload.filename, x.payload.directories, x.payload.roothash, self._dest_dir)
            
    def _short_member_id(self):
        return str(self.my_member.mid.encode("HEX"))[0:5]     
    
    def _address(self):
        return self.dispersy.endpoint.get_address()     
            
    def _port(self):
        return str(self.dispersy.endpoint.get_address()[1])       
     
    def create_simple_messages(self, count, message=None, store=True, update=True, forward=True):
        if message is not None:
            meta = self.get_meta_message(SIMPLE_MESSAGE_NAME)
            messages = [meta.impl(authentication=(self.my_member,), distribution=(self.claim_global_time(), self._simple_distribution.claim_sequence_number()), 
                                  payload=(message.filename, message.data)) for _ in xrange(count)]
            self.dispersy.store_update_forward(messages, store, update, forward)
        
    def create_file_hash_messages(self, count, file_hash_message, store=True, update=True, forward=True):
        # Make sure you have the filename, and a proper hash
        if isfile(file_hash_message.filename):
            # Let Swift know that it should seed this file
            # Get a hash of the file 
            self.dispersy.endpoint.add_file(file_hash_message.filename, file_hash_message.roothash)
            
            if file_hash_message.roothash is not None and len(file_hash_message.roothash) == HASH_LENGTH:
                # Send this hash to candidates (probably do the prior stuff out of the candidates loop)
                meta = self.get_meta_message(FILE_HASH_MESSAGE_NAME)
                messages = [meta.impl(authentication=(self.my_member,), distribution=(self.claim_global_time(), self._file_hash_distribution.claim_sequence_number()), 
                                      payload=(basename(file_hash_message.filename), file_hash_message.directories, file_hash_message.roothash, self._address())) 
                            for _ in xrange(count)]
                self.dispersy.store_update_forward(messages, store, update, forward)
        
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
    