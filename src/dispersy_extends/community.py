'''
Created on Aug 7, 2013

@author: Vincent Ketelaars
'''
from threading import Event, Lock
from os.path import isfile

from dispersy.community import Community
from dispersy.conversion import DefaultConversion
from dispersy.message import Message
from dispersy.authentication import MemberAuthentication
from dispersy.resolution import PublicResolution
from dispersy.distribution import FullSyncDistribution, DirectDistribution
from dispersy.destination import CommunityDestination, CandidateDestination
from dispersy.candidate import WalkCandidate

from src.dispersy_extends.candidate import EligibleWalkCandidate
from src.timeout import IntroductionRequestTimeout
from src.dispersy_extends.conversion import SmallFileConversion, FileHashConversion,\
    AddressesConversion, APIMessageConversion, PunctureConversion,\
    AddressesRequestConversion, PunctureResponseConversion
from src.dispersy_extends.payload import SmallFilePayload, FileHashPayload, AddressesPayload,\
    APIMessagePayload, PuncturePayload, AddressesRequestPayload,\
    PunctureResponsePayload
from src.definitions import DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, NUMBER_OF_PEERS_TO_SYNC, HASH_LENGTH, \
    FILE_HASH_MESSAGE_NAME, SMALL_FILE_MESSAGE_NAME, ADDRESSES_MESSAGE_NAME,\
    MESSAGE_KEY_API_MESSAGE, API_MESSAGE_NAME, PUNCTURE_MESSAGE_NAME,\
    ADDRESSES_REQUEST_MESSAGE_NAME, PUNCTURE_RESPONSE_MESSAGE_NAME
from src.tools.periodic_task import Looper, PeriodicIntroductionRequest
from src.swift.swift_community import SwiftCommunity

from src.logger import get_logger
logger = get_logger(__name__)    
    
class MyCommunity(Community):
    '''
    For the most part this Community is designed around the messages that are allowed to be used by its members.
    The SmallFile message is a container for a filename and the file's data. It has to be small enough to fit in a single packet.
    The FileHash message is designed to convey the information necessary for Swift to create a swarm for the file 
    you want to disseminate.
    The Addresses message allows you to send information about your endpoints (the sockets your have available)
    The AddressesRequest message is merely a request for an Addresses message.
    The Puncture message is used to ensure that contact between two endpoints is feasible. 
    Additionally it conveys the address it thinks it's talking for NAT purposes.
    The PunctureResponse message is not currently in use and is very much like the Puncture message.
    The API message is simply a message limited by packet size.
    
    Moreover this Community also instantiates the SwiftCommunity which is an abstraction of this community 
    with respect to Swift.
    On top of this the Community has the option of not using the bootstrappers and the walker,
    but instead use a more aggressive form of keeping in contact with peers by periodically sending 
    introduction requests to each of them.  
    '''

    def __init__(self, dispersy, master_member, enable=False, api_callback=None):
        '''
        @param enable: Enable the candidate walker
        @param api_callback: Callback function
        '''
        logger.info("I will %swalk today", "" if enable else "not ")
        self._enable_candidate_walker = enable # Needs to be set before call to Community
        super(MyCommunity, self).__init__(dispersy, master_member)
        self._dest_dir = None
        self._update_bloomfilter = -1
        self._intro_request_updates = {}
        self._api_callback = api_callback
        self._looper = Looper(sleep=0.1, name="MyCommunity_looper")
        self._looper.start()
        self._lock = Lock()
        self.swift_community = SwiftCommunity(self, self.dispersy.endpoint, api_callback=api_callback)
        
    def initiate_conversions(self):
        """
        Overwrite
        """
        return [DefaultConversion(self), SmallFileConversion(self), FileHashConversion(self), 
                AddressesConversion(self), AddressesRequestConversion(self), PunctureConversion(self), 
                PunctureResponseConversion(self), APIMessageConversion(self)]
    
    def initiate_meta_messages(self):
        """
        Overwrite
        """
        self._small_file_distribution = FullSyncDistribution(DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, True)
        self._file_hash_distribution = FullSyncDistribution(DISTRIBUTION_DIRECTION, DISTRIBUTION_PRIORITY, True)
        self._addresses_distribution = DirectDistribution()
        self._addresses_request_distribution = DirectDistribution()
        self._puncture_distribution = DirectDistribution()
        self._puncture_response_distribution = DirectDistribution()
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
                Message(self, ADDRESSES_REQUEST_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._addresses_request_distribution, CandidateDestination(), AddressesRequestPayload(), 
                        self.addresses_request_message_check, self.addresses_request_message_handle),
                Message(self, PUNCTURE_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._puncture_distribution, CandidateDestination(), PuncturePayload(), 
                        self.puncture_check, self.puncture_handle),
                Message(self, PUNCTURE_RESPONSE_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._puncture_response_distribution, CandidateDestination(), PunctureResponsePayload(), 
                        self.puncture_response_check, self.puncture_response_handle),
                Message(self, API_MESSAGE_NAME, MemberAuthentication(encoding="sha1"), PublicResolution(), 
                        self._api_message_distribution, CandidateDestination(), APIMessagePayload(), 
                        self.api_message_check, self.api_message_handle)]
        
    def small_file_message_check(self, messages):
        for x in messages:
            yield x
    
    def small_file_message_handle(self, messages):
        for x in messages:
            self.swift_community.file_received(x.payload.filename, x.payload.data)
            
    def file_hash_check(self, messages):
        for x in messages:
            yield x
    
    def file_hash_handle(self, messages):
        for x in messages:
            self.swift_community.filehash_received(x.payload.filename, x.payload.directories, x.payload.roothash, 
                                                   x.payload.size, x.payload.timestamp, x.destination)
    
    def addresses_message_check(self, messages):
        for x in messages:
            yield x
    
    def addresses_message_handle(self, messages):
        for x in messages:
            self.dispersy.endpoint.peer_endpoints_received(self, x.authentication.member, x.payload.addresses, 
                                                           x.payload.wan_addresses, x.payload.ids)
            
    def addresses_request_message_check(self, messages):
        for x in messages:
            yield x
            
    def addresses_request_message_handle(self, messages):
        for x in messages:
            self.dispersy.endpoint.addresses_requested(self, x.authentication.member, x.payload.sender_lan, 
                                                       x.payload.sender_wan, x.payload.endpoint_id, x.payload.wan_address)
            
    def puncture_check(self, messages):
        for x in messages:
            yield x
            
    def puncture_handle(self, messages):
        for x in messages:
            self.dispersy.endpoint.incoming_puncture_message(self, x.authentication.member, x.payload.sender_lan, 
                                                             x.payload.sender_wan, x.payload.sender_id, 
                                                             x.payload.address_vote, x.payload.endpoint_id)
            
    def puncture_response_check(self, messages):
        for x in messages:
            yield x
            
    def puncture_response_handle(self, messages):
        for x in messages:
            self.dispersy.endpoint.incoming_puncture_response_message(x.authentication.member, x.payload.sender_lan, 
                                                                      x.payload.sender_wan,
                                                                      x.payload.address_vote, x.payload.endpoint_id)
        
    def api_message_check(self, messages):
        for x in messages:
            yield x
    
    def api_message_handle(self, messages):
        for x in messages:
            if self._api_callback:
                self._api_callback(MESSAGE_KEY_API_MESSAGE, x.payload.message)
    
    def _active_sockets(self):
        return [s.address for s in self.dispersy.endpoint.swift_endpoints if s.socket_running]
     
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
        
    def create_file_hash_messages(self, count, file_hash_message, delay, store=True, update=True, forward=True):
        """
        Endpoint decides when files will be handed to Swift to be disseminated.
        As such we will not allow messages to be send until that time, 
        because peers would not be able to do anything with this information.
        
        @param count: Number of messages
        @type file_hash_message: FileHashCarrier
        """
        # Make sure you have the filename, and a proper hash
        if isfile(file_hash_message.filename) and file_hash_message.roothash is not None and len(file_hash_message.roothash) == HASH_LENGTH:
            meta = self.get_meta_message(FILE_HASH_MESSAGE_NAME)
            
            # Messages need to be created only when they are sent, otherwise peers get sequence errors
            def send_messages():
                messages = [meta.impl(authentication=(self.my_member,), 
                                  distribution=(self.claim_global_time(), self._file_hash_distribution.claim_sequence_number()), 
                                  payload=(file_hash_message.filename, file_hash_message.directories, 
                                           file_hash_message.roothash, file_hash_message.size, 
                                           file_hash_message.timestamp, self._active_sockets()))
                        for _ in xrange(count)]
                self.dispersy.callback.register(self.dispersy.store_update_forward, args=(messages, store, update, forward), delay=delay)
                
            # Let Swift know that it should seed this file
            # Nasty hack to get the destination implementation
            self.swift_community.add_file(file_hash_message.filename, file_hash_message.roothash, 
                                          meta.destination.Implementation(meta),
                                          file_hash_message.size, file_hash_message.timestamp, send_messages)
                
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
        Creates and returns a new EligibleWalkCandidate instance,
        opposed to the WalkCandidate the general Community creates.
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
        
        l = len(others) # need l for return value
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
        
        if self._update_bloomfilter > 0: # Use our own looper to ensure that requests are sent periodically
            request_update = PeriodicIntroductionRequest(send_request, self._update_bloomfilter, candidate, 
                                                         delay=self._update_bloomfilter) # Wait because one is already sent
            self._looper.add_task(request_update)
        
        else: # Only add a timeout regardless if walker is enabled or not
            request_update = IntroductionRequestTimeout(candidate, send_request)
        
        # request_update should have a candidate field
        self._intro_request_updates.update({candidate.sock_addr : request_update})
        
        return l > 0 # if l is larger than 0 it means this candidate already existed
                
    def add_candidate(self, candidate):
        """
        Add the candidate to the list of peers that should receive Introduction requests regularly
        """
        Community.add_candidate(self, candidate)
        # Each candidate should only do send_introduction_request once
        if not candidate.sock_addr in self._intro_request_updates.iterkeys():
            self.send_introduction_request(candidate) 
        
    def send_introduction_request(self, walker):
        """
        Register the sending of an introduction request to this walker
        With resends if the request fails
        @type walker: Candidate
        """
        if isinstance(walker, EligibleWalkCandidate):
            logger.debug("Send introduction request %s", walker)
            walker.set_update_bloomfilter(self.update_bloomfilter)
        
            def send_request():
                self._dispersy.callback.register(self._dispersy.create_introduction_request, 
                                    (self, walker, True, True), callback=callback)
            
            def callback(result):
                if isinstance(result, Exception):
                    # Somehow the introduction request did not work
                    Event().wait(1) # If we don't wait, we risk trying to many times to no avail
                    send_request()
    
            # First add the IntroductionRequestTimeout to the list, then send request. 
            # Otherwise this method is recursively called to often
            if not self._add_candidate_intro_requests_update(walker, send_request):                    
                send_request()
        else:
            if self.dispersy.endpoint.is_bootstrap_candidate(candidate=walker):
                logger.debug("This is a BootstrapCandidate: %s", walker)
            else: # This should not happen
                logger.warning("This is not a EligibleWalkCandidate: %s", walker)
            
        
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
    
    def unload_community(self):
        """
        Taking down this Community, and the SwiftCommunity as well.
        """
        self._looper.stop()
        Community.unload_community(self)
        return self.swift_community.unload_community()
    
    def claim_global_time(self):
        """
        Overwritten to ensure that claiming is threadsafe
        """
        with self._lock:
            return Community.claim_global_time(self)