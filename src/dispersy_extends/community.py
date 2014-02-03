'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''
from threading import Event
from os.path import isfile

from src.logger import get_logger
from dispersy.community import Community
from dispersy.conversion import DefaultConversion
from dispersy.message import Message
from dispersy.authentication import MemberAuthentication
from dispersy.resolution import PublicResolution
from dispersy.distribution import FullSyncDistribution, DirectDistribution
from dispersy.destination import CommunityDestination, CandidateDestination

from src.dispersy_extends.candidate import EligibleWalkCandidate
from src.timeout import IntroductionRequestTimeout
from src.dispersy_extends.conversion import SmallFileConversion, FileHashConversion,\
    AddressesConversion, APIMessageConversion, PunctureConversion
from src.dispersy_extends.payload import SmallFilePayload, FileHashPayload, AddressesPayload,\
    APIMessagePayload, PuncturePayload

from src.definitions import DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, NUMBER_OF_PEERS_TO_SYNC, HASH_LENGTH, \
    FILE_HASH_MESSAGE_NAME, SMALL_FILE_MESSAGE_NAME, ADDRESSES_MESSAGE_NAME,\
    MESSAGE_KEY_API_MESSAGE, API_MESSAGE_NAME, PUNCTURE_MESSAGE_NAME
from src.tools.periodic_task import Looper, PeriodicIntroductionRequest
from src.swift.swift_community import SwiftCommunity
from dispersy.candidate import WalkCandidate
from src.address import Address

logger = get_logger(__name__)    
    
class MyCommunity(Community):
    '''
    classdocs
    '''

    def __init__(self, dispersy, master_member, enable=False, api_callback=None):
        '''
        Constructor
        '''
        logger.debug("I will %swalk today", "" if enable else "not ")
        self._enable_candidate_walker = enable # Needs to be set before call to Community
        super(MyCommunity, self).__init__(dispersy, master_member)
        self._dest_dir = None
        self._update_bloomfilter = -1
        self._intro_request_updates = {}
        self._api_callback = api_callback
        self._looper = Looper(sleep=0.1, name="MyCommunity_looper")
        self._looper.start()
        self.swift_community = SwiftCommunity(self, self.dispersy.endpoint, api_callback=api_callback)
        
    def initiate_conversions(self):
        """
        Overwrite
        """
        return [DefaultConversion(self), SmallFileConversion(self), FileHashConversion(self), 
                AddressesConversion(self), PunctureConversion(self), APIMessageConversion(self)]
    
    def initiate_meta_messages(self):
        """
        Overwrite
        """
        self._small_file_distribution = FullSyncDistribution(DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, True)
        self._file_hash_distribution = FullSyncDistribution(DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, True)
        self._addresses_distribution = DirectDistribution()
        self._puncture_distribution = DirectDistribution()
        self._api_message_distribution = DirectDistribution()
        return [Message(self, SMALL_FILE_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._small_file_distribution, CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), SmallFilePayload(), 
                        self.small_file_message_check, self.small_file_message_handle),
                Message(self, FILE_HASH_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._file_hash_distribution, CommunityDestination(NUMBER_OF_PEERS_TO_SYNC), FileHashPayload(), 
                         self.file_hash_check, self.file_hash_handle),
                Message(self, ADDRESSES_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._addresses_distribution, CandidateDestination(), AddressesPayload(), 
                        self.addresses_message_check, self.addresses_message_handle),
                Message(self, PUNCTURE_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._puncture_distribution, CandidateDestination(), PuncturePayload(), 
                        self.puncture_check, self.puncture_handle),
                Message(self, API_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._api_message_distribution, CandidateDestination(), APIMessagePayload(), 
                        self.api_message_check, self.api_message_handle)]
        
    def small_file_message_check(self, messages):
        """
        Check Callback
        """
        for x in messages:
            yield x
    
    def small_file_message_handle(self, messages):
        """
        Handle Callback
        """
        for x in messages:
            self.swift_community.file_received(x.payload.filename, x.payload.data)
            
    def file_hash_check(self, messages):
        for x in messages:
            yield x
    
    def file_hash_handle(self, messages):
        for x in messages:
            if len(x.payload.filename) >= 1 and x.payload.directories is not None and len(x.payload.roothash) == HASH_LENGTH:
                self.swift_community.filehash_received(x.payload.filename, x.payload.directories, 
                                                       x.payload.roothash, x.payload.size, x.payload.timestamp,
                                                       x.payload.addresses, x.destination)
    
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
            addresses = [Address.unknown(a) for a in x.payload.addresses]
            self.swift_community.peer_endpoints_received(addresses)
            self.dispersy.endpoint.peer_endpoints_received(self, addresses)
            
    def puncture_check(self, messages):
        for x in messages:
            yield x
            
    def puncture_handle(self, messages):
        for x in messages:
            logger.debug("Puncture message!")
        
    def api_message_check(self, messages):
        """
        Check Callback
        """
        for x in messages:
            yield x
    
    def api_message_handle(self, messages):
        """
        Handle Callback
        """
        for x in messages:
            if self._api_callback:
                self._api_callback(MESSAGE_KEY_API_MESSAGE, x.payload.message)
    
    def _short_member_id(self):
        return str(self.my_member.mid.encode("HEX"))[0:5]     
    
    def _addresses(self):
        return [s.address for s in self.dispersy.endpoint.swift_endpoints]
            
    def _port(self):
        return str(self.dispersy.endpoint.get_address()[1])       
     
    def create_small_file_messages(self, count, simple_message=None, store=True, update=True, forward=True):
        """
        @param count: Number of messages
        @type simple_message: SimpleFileCarrier
        """
        meta = self.get_meta_message(SMALL_FILE_MESSAGE_NAME)
        messages = [meta.impl(authentication=(self.my_member,), 
                              distribution=(self.claim_global_time(), self._small_file_distribution.claim_sequence_number()), 
                              payload=(simple_message.filename, simple_message.data)) for _ in xrange(count)]
        self.dispersy.store_update_forward(messages, store, update, forward)
        
    def create_file_hash_messages(self, count, file_hash_message, store=True, update=True, forward=True):
        """
        @param count: Number of messages
        @type file_hash_message: FileHashCarrier
        """
        # Make sure you have the filename, and a proper hash
        if isfile(file_hash_message.filename) and file_hash_message.roothash is not None and len(file_hash_message.roothash) == HASH_LENGTH:
            meta = self.get_meta_message(FILE_HASH_MESSAGE_NAME)
            # Send this hash to candidates (probably do the prior stuff out of the candidates loop)
            messages = [meta.impl(authentication=(self.my_member,), 
                                  distribution=(self.claim_global_time(), self._file_hash_distribution.claim_sequence_number()), 
                                  payload=(file_hash_message.filename, file_hash_message.directories, 
                                           file_hash_message.roothash, file_hash_message.size, 
                                           file_hash_message.timestamp, self._addresses()))
                        # TODO: Perhaps only send active sockets?
                        for _ in xrange(count)]
            self.dispersy.store_update_forward(messages, store, update, forward)
                
            # Let Swift know that it should seed this file
            self.swift_community.add_file(file_hash_message.filename, file_hash_message.roothash, messages[0].destination,
                                          file_hash_message.size, file_hash_message.timestamp)
                
    def create_addresses_messages(self, count, addresses_message, candidates, store=True, update=True, forward=True):
        """
        @param count: Number of messages
        @type addresses_message: AddressesCarrier
        @param candidates: list of candidates
        """
        meta = self.get_meta_message(ADDRESSES_MESSAGE_NAME)
        messages = [meta.impl(authentication=(self.my_member,),
                              distribution=(self.claim_global_time(),),
                              destination=tuple(candidates), 
                              payload=(addresses_message.addresses,)) for _ in xrange(count)]
        self.dispersy.store_update_forward(messages, store, update, forward)
        
    def create_api_messages(self, count, api_message, store=True, update=True, forward=True):
        """
        @param count: Number of messages
        @type api_message: APIMessageCarrier
        """
        meta = self.get_meta_message(API_MESSAGE_NAME)
        candidates = [WalkCandidate(a.addr(), True, a.addr(), a.addr(), u"unknown") for a in api_message.addresses]
        if len(candidates) == 0:
            candidates = self._candidates.values()
        messages = [meta.impl(authentication=(self.my_member,),
                              distribution=(self.claim_global_time(),),
                              destination=tuple(candidates), 
                              payload=(api_message.message,)) for _ in xrange(count)]
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
        The candidate will be added to the list of known candidates, that will be sent introduction requests.
        In case self._update_bloomfilter is a positive number, every so many seconds an introduction request will be send.
        If it does not, the single request that will be send will be accompanied by a timeout, 
        which will force resend upon failure.
        
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
            logger.debug("Merge only first of list, %s with %s", others[0], candidate)
            candidate.merge(others[0])
        
        # Remove all similar candidates
        for o in others:
            o.stop()
            del self._intro_request_updates[o.sock_addr]
        
        request_update = None
        if self._update_bloomfilter > 0: # Use our own looper to ensure that requests are sent periodically
            request_update = PeriodicIntroductionRequest(send_request, self._update_bloomfilter, candidate, 
                                                         delay=self._update_bloomfilter) # Wait because one is already sent
            self._looper.add_task(request_update)
        
        else: # Only add a timeout regardless if walker is enabled or not
            request_update = IntroductionRequestTimeout(candidate, send_request)
        
        # request_update should have a candidate field
        self._intro_request_updates.update({candidate.sock_addr : request_update})
        
        return l > 0
                
    def add_candidate(self, candidate):
        Community.add_candidate(self, candidate)
        # Each candidate should only do send_introduction_request once
        if not candidate.sock_addr in self._intro_request_updates.iterkeys():
            self.send_introduction_request(candidate) 
        
    def send_introduction_request(self, walker):
        if isinstance(walker, EligibleWalkCandidate):
            logger.debug("Send introduction request %s", walker)
            walker.set_update_bloomfilter(self.update_bloomfilter)
        
            def send_request():
                self._dispersy.callback.register(self._dispersy.create_introduction_request, 
                                    (self, walker, True,True),callback=callback)
            
            def callback(result):
                if isinstance(result, Exception):
                    # Somehow the introduction request did not work
                    Event().wait(1)
                    send_request()
    
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
    