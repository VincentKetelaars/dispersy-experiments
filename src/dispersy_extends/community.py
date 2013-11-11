'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''
from threading import Event
from os.path import isfile, basename

from dispersy.logger import get_logger
from dispersy.community import Community
from dispersy.conversion import DefaultConversion
from dispersy.message import Message
from dispersy.authentication import MemberAuthentication
from dispersy.resolution import PublicResolution
from dispersy.distribution import FullSyncDistribution
from dispersy.destination import CommunityDestination

from src.dispersy_extends.candidate import EligibleWalkCandidate
from src.timeout import IntroductionRequestTimeout
from src.dispersy_extends.conversion import SimpleFileConversion, FileHashConversion
from src.dispersy_extends.payload import SimpleFilePayload, FileHashPayload, AddressesPayload

from src.definitions import DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, NUMBER_OF_PEERS_TO_SYNC, HASH_LENGTH, \
    FILE_HASH_MESSAGE_NAME, SIMPLE_MESSAGE_NAME, ADDRESSES_MESSAGE_NAME

logger = get_logger(__name__)    
    
class MyCommunity(Community):
    '''
    classdocs
    '''

    def __init__(self, dispersy, master_member, enable=False):
        '''
        Constructor
        '''
        self._enable_candidate_walker = enable # Needs to be set before call to Community
        super(MyCommunity, self).__init__(dispersy, master_member)
        self._dest_dir = None
        self._update_bloomfilter = -1
        self._intro_request_updates = {}
        
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
        self._addresses_distribution = FullSyncDistribution(DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, True)
        return [Message(self, SIMPLE_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._simple_distribution, CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), SimpleFilePayload(), 
                        self.simple_message_check, self.simple_message_handle),
                Message(self, FILE_HASH_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._file_hash_distribution, CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), FileHashPayload(), 
                         self.file_hash_check, self.file_hash_handle),
                Message(self, ADDRESSES_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._addresses_distribution, CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), AddressesPayload(), 
                        self.addresses_message_check, self.addresses_message_handle)]
        
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
                self.dispersy.endpoint.start_download(x.payload.filename, x.payload.directories, x.payload.roothash, 
                                                      self._dest_dir, x.payload.addresses)
    
    def addresses_message_check(self, messages):
        """
        Check Callback
        """
        for x in messages:
            yield x
    
    def addresses_message_handle(self, messages):
        """
        Handle Callback
        """
        for x in messages:
            # Make sure that someone know that these addresses are one device
            pass
    
    def _short_member_id(self):
        return str(self.my_member.mid.encode("HEX"))[0:5]     
    
    def _addresses(self):
        return [s.address for s in self.dispersy.endpoint.swift_endpoints]
            
    def _port(self):
        return str(self.dispersy.endpoint.get_address()[1])       
     
    def create_simple_messages(self, count, simple_message=None, store=True, update=True, forward=True):
        if simple_message is not None:
            meta = self.get_meta_message(SIMPLE_MESSAGE_NAME)
            messages = [meta.impl(authentication=(self.my_member,), 
                                  distribution=(self.claim_global_time(), self._simple_distribution.claim_sequence_number()), 
                                  payload=(simple_message.filename, simple_message.data)) for _ in xrange(count)]
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
                messages = [meta.impl(authentication=(self.my_member,), 
                                      distribution=(self.claim_global_time(), self._file_hash_distribution.claim_sequence_number()), 
                                      payload=(basename(file_hash_message.filename), file_hash_message.directories, 
                                               file_hash_message.roothash, self._addresses()))
                            for _ in xrange(count)]
                self.dispersy.store_update_forward(messages, store, update, forward)
                
    def create_addresses_messages(self, count, addresses_message, store=True, update=True, forward=True):
        meta = self.get_meta_message(ADDRESSES_MESSAGE_NAME)
        messages = [meta.impl(authentication=(self.my_member,), 
                              distribution=(self.claim_global_time(), self._addresses_distribution.claim_sequence_number()), 
                              payload=(addresses_message.addresses,)) for _ in xrange(count)]
        self.dispersy.store_update_forward(messages, store, update, forward)
                
    def create_candidate(self, sock_addr, tunnel, lan_address, wan_address, connection_type):
        """
        Creates and returns a new WalkCandidate instance.
        """
        assert not sock_addr in self._candidates
        assert isinstance(tunnel, bool)
        candidate = EligibleWalkCandidate(sock_addr, tunnel, lan_address, wan_address, connection_type)
        self.add_candidate(candidate)
        return candidate
    
    def _add_candidate_intro_requests_update(self, candidate, send_request):
        """
        @param candidate: Add candidate to list
        @param send_request: Callback function assigned to IntroductionRequestTimeout
        @return: True if candidate already existed, False otherwise
        """
        # find existing candidates that are likely to be the same candidate
        others = [other.candidate for other in self._intro_request_updates.itervalues()
                  if (other.candidate.wan_address[0] == candidate.wan_address[0] and
                      other.candidate.lan_address == candidate.lan_address)]
        
        l = len(others)
        if l == 0:
            logger.debug("Add new %s", candidate)
        elif l == 1:
            logger.debug("Merge existing %s with %s", others[0], candidate)
            candidate.merge(others[0])
        else: # len(others) > 1
            logger.debug("Merge first of list, %s with %s", others[0], candidate)
            candidate.merge(others[0])
                
        for o in others:
            del self._intro_request_updates[o.sock_addr]
        
        self._intro_request_updates.update({candidate.sock_addr : IntroductionRequestTimeout(candidate, send_request)})
        
        return l > 0
                
    def add_candidate(self, candidate):
        Community.add_candidate(self, candidate)
        # Each candidate should only create one IntroductionRequestTimeout
        if not candidate.sock_addr in self._intro_request_updates:
            self.send_introduction_request(candidate) 
        
    def send_introduction_request(self, walker):
        logger.debug("Send introduction request %s", walker)
        if isinstance(walker, EligibleWalkCandidate):
            walker.set_update_bloomfilter(self._update_bloomfilter)
        
            def send_request():
                self._dispersy.callback.register(self._dispersy.create_introduction_request, 
                                    (self, walker, True,True),callback=callback)
            
            def callback(result):
                if isinstance(result, Exception):
                    # Somehow the introduction request did not work
                    Event().wait(1)
                    send_request()
    
            if self.update_bloomfilter > 0:
                # First add the IntroductionRequestTimeout to the list, then send request. 
                # Otherwise this method is recursively called to often
                if not self._add_candidate_intro_requests_update(walker, send_request):                    
                    send_request()
        else:
            if self.dispersy.endpoint.is_bootstrap_candidate(candidate=walker):
                logger.debug("This is a BootstrapCandidate: %s", walker)
            else:
                logger.debug("This is not a EligibleWalkCandidate: %s", walker)
            
        
    @property
    def dispersy_enable_candidate_walker(self):
        return self._enable_candidate_walker
    
    @property
    def dispersy_enable_candidate_walker_responses(self):
        # initialization and nat meta messages will still be created
        return True
    
    @property
    def dispersy_sync_skip_enable(self):
        # Skip the creation of the bloomfilter
        return Community.dispersy_sync_skip_enable
    
    @property
    def dispersy_sync_cache_enable(self):
        # Reuse the last bloomfilter
        return Community.dispersy_sync_cache_enable
    
    @property
    def dest_dir(self):
        return self._dest_dir
    
    @dest_dir.setter
    def dest_dir(self, dest_dir):
        self._dest_dir = dest_dir
    
    @property
    def update_bloomfilter(self):
        return self._update_bloomfilter
    
    @update_bloomfilter.setter
    def update_bloomfilter(self, update_bloomfilter):
        self._update_bloomfilter = update_bloomfilter    
    