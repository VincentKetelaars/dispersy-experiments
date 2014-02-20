'''
Created on Nov 21, 2013

@author: Vincent Ketelaars
'''

from datetime import datetime, timedelta
from src.address import Address

from src.logger import get_logger
from src.definitions import ENDPOINT_CONTACT_TIMEOUT
from src.peer import Peer
logger = get_logger(__name__)

class DispersyContact(object):
    '''
    This object represents a Dispersy contact (i.e. peer address). 
    Each incoming and outgoing message to this address is noted.
    '''

    def __init__(self, address, peer=None, community_id=None, addresses_received=False, member_id=None):
        self.address = address # Primary address
        self.last_send_time = {address : datetime.min}
        self.last_recv_time = {address : datetime.min}
        self.count_sent = {}
        self.count_rcvd = {}
        self.bytes_sent = {}
        self.bytes_rcvd = {}
        self.community_ids = [community_id] if community_id is not None else []
        self.peer = peer
        self._unreachable_addresses = set()
        self._addresses_received = datetime.utcnow() if addresses_received else datetime.min
        self._addresses_sent = datetime.min
        self._addresses_requested = datetime.min
        self._member_id = member_id
        
    @classmethod
    def shallow_copy(cls, contact):
        assert isinstance(contact, DispersyContact)
        dc = DispersyContact(contact.address, peer=contact.peer) # TODO: Should these be copies?
        dc.community_ids = list(contact.community_ids)
        return dc
    
    @property
    def addresses(self):
        return self.peer.addresses if self.peer is not None else set([self.address])
        
    @property
    def reachable_addresses(self):
        return list(self.addresses.difference(self._unreachable_addresses))
    
    @property
    def confirmed_addresses(self):
        return [a for a in self.addresses if self.last_rcvd(a) > datetime.min]
    
    @property
    def addresses_received(self):
        return self._addresses_received != datetime.min
    
    @property
    def addresses_sent(self):
        return self._addresses_sent
    
    @property
    def member_id(self):
        return self._member_id
    
    @property
    def addresses_requested(self):
        return self._addresses_requested

    @member_id.setter
    def member_id(self, member_id):
        self._member_id = member_id
        
    def sent_addresses(self):
        self._addresses_sent = datetime.utcnow()
    
    def requested_addresses(self):
        self._addresses_requested = datetime.utcnow()
    
    def get_peer_addresses(self, lan, wan):
        if self.peer is None:
            return [self.address]
        return [l if wan.ip == w.ip else w for l, w in self.peer._addresses.itervalues()]
    
    def add_community(self, cid):
        if not cid in self.community_ids:
            self.community_ids.append(cid)
            
    def has_community(self, cid):
        for c in self.community_ids:
            if c == cid:
                return True
        return False
        
    def add_unreachable_address(self, address):
        self._unreachable_addresses.add(address)
        
    def reset_unreachable_addresses(self):
        self._unreachable_addresses = set()
       
    def rcvd(self, num_messages, bytes_rcvd, address=Address()):
        self.count_rcvd[address] = self.count_rcvd.get(address, 0) + num_messages
        self.bytes_rcvd[address] = self.bytes_rcvd.get(address, 0) + bytes_rcvd
        self.last_recv_time[address] = datetime.utcnow()
        
    def num_rcvd(self):
        return sum([v for _, v in self.count_rcvd.items()])
    
    def total_rcvd(self):
        return sum([v for _, v in self.bytes_rcvd.items()])
        
    def sent(self, num_messages, bytes_sent, address=Address()):
        self.count_sent[address] = self.count_sent.get(address, 0) + num_messages
        self.bytes_sent[address] = self.bytes_sent.get(address, 0) + bytes_sent
        self.last_send_time[address] = datetime.utcnow()
        
    def num_sent(self):
        return sum([v for _, v in self.count_sent.items()])
    
    def total_sent(self):
        return sum([v for _, v in self.bytes_sent.items()])
        
    def last_contact(self, address=None):
        """
        This function returns the last time there was either a send or a receive to or from the supplied address
        If no address is supplied, the default address will be used
        @return the last contact, otherwise datetime.min
        """
        if address is None:
            return max(self.last_send_time[self.address], self.last_recv_time[self.address])
        return max(self.last_send_time.get(address, datetime.min), self.last_recv_time.get(address, datetime.min))
    
    def no_contact_since(self, expiration_time=ENDPOINT_CONTACT_TIMEOUT):
        addrs = []
        for a in self.reachable_addresses:
            if (self.last_rcvd(a) + timedelta(seconds=expiration_time) < datetime.utcnow() or
                self.last_sent(a) + timedelta(seconds=expiration_time) < datetime.utcnow()): # Timed out
                addrs.append(a)
        return addrs
    
    def last_rcvd(self, address):
        return self.last_recv_time.get(address, datetime.min)
    
    def last_sent(self, address):
        return self.last_send_time.get(address, datetime.min)
    
    def set_peer(self, peer, addresses_received=False):
        """
        @type peer: Peer
        """
        self.peer = peer
        if addresses_received:
            self._addresses_received = datetime.utcnow()
        
    def has_address(self, address):
        """
        Return whether this address belongs to this contact
        @type address: Address
        """
        return address == self.address or (self.peer is not None and self.peer.has_any([address]))
    
    def has_any(self, addresses, ids=[]):
        if self.peer is None:
            return self.address in addresses
        return self.peer.has_any(addresses, ids)
    
    def update_address(self, lan_address, wan_address, endpoint_id, mid):
        if self.peer is None:
            self.peer = Peer(lan_address, wan_address, endpoint_id, mid)
        else:
            self.peer.update_address(lan_address, wan_address, endpoint_id)
    
    def merge(self, contact):
        self.merge_stats(contact)
        for id_ in contact.community_ids:
            if not id_ in self.community_ids:
                self.community_ids.append(id_)
        self._unreachable_addresses.update(contact._unreachable_addresses)
    
    def merge_stats(self, contact):
        """
        Merge statistics of this contact with that of another DispersyContact
        @type contact: DispersyContact
        """
        assert isinstance(contact, DispersyContact)
        for k, v in contact.last_send_time.iteritems():
            self.last_send_time[k] = max(self.last_send_time.get(k, datetime.min), v)
        for k, v in contact.last_recv_time.iteritems():
            self.last_recv_time[k] = max(self.last_recv_time.get(k, datetime.min), v)
        for k, v in contact.count_sent.iteritems():
            self.count_sent[k] = self.count_sent.get(k, 0) + v
        for k, v in contact.bytes_sent.iteritems():
            self.bytes_sent[k] = self.bytes_sent.get(k, 0) + v
        for k, v in contact.count_rcvd.iteritems():
            self.count_rcvd[k] = self.count_rcvd.get(k, 0) + v
        for k, v in contact.bytes_rcvd.iteritems():
            self.bytes_rcvd[k] = self.bytes_rcvd.get(k, 0) + v
            
    def addr_info(self, address):
        return "%d:%d rcvd at %s, %d:%d sent %s" % (self.count_rcvd.get(address, 0), self.bytes_rcvd.get(address, 0), 
                                                    self.last_recv_time.get(address, datetime.min), self.count_sent.get(address, 0),
                                                    self.bytes_sent.get(address, 0), self.last_send_time.get(address, datetime.min))
            
    def __str__(self):
        return "%s, %d:%d sent, %d:%d received, at %s" % (self.address, self.num_sent(), self.total_sent(), 
                                                          self.num_rcvd(), self.total_rcvd(), self.last_contact())
        
    # We only care about the address when comparing
    def __eq__(self, other):
        if not isinstance(other, DispersyContact):
            return False
        # TODO: Do we need a better comparison?
        if self.address == other.address and self.bytes_rcvd == other.bytes_rcvd and self.bytes_sent == other.bytes_sent: 
            return True
        return False
        
    def __ne__(self, other):
        return not self.__eq__(other)
    
    # Create this hash function to make it easily comparible in a set..
    # The address should be the key
    # We do not use peer because we rely on the user to ensure that the same peer does not get multiple DispersyContacts
    def __hash__(self, *args, **kwargs):
        return hash(self.address)