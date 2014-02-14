'''
Created on Feb 14, 2014

@author: Vincent Ketelaars
'''
from random import randint

class Peer(object):
    
    def __init__(self, lan_addresses, wan_addresses=[], ids=[], member_id=None):
        self._member_id = member_id
        if len(lan_addresses) == len(ids): # This should ensure that wan_addresses is also equal
            self._addresses = dict(zip(ids, zip(lan_addresses, wan_addresses)))
            self._fake_keys = False
        else: # Assume no wan_addresses and no ids
            # Fake IDs shouldn't be a problem, because we are not going to look for fake ids either
            # Understand that the fake ids are ints, whereas the real ones are raw bytes
            self._addresses = dict(zip(self._random_keys(len(lan_addresses)), zip(lan_addresses, lan_addresses)))
            self._fake_keys = True
            
    def _random_keys(self, length):
        return [randint(0, 1000000) for _ in range(length)]
    
    @property
    def member_id(self):
        return self._member_id
            
    @property
    def addresses(self):
        return set(self.lan_addresses + self.wan_addresses)
    
    @property
    def lan_addresses(self):
        return [l for l, _ in self._addresses.values()]
    
    @property
    def wan_addresses(self):
        return [w for _, w in self._addresses.values()]
    
    def get(self, id_):
        return self._addresses.get(id_, None)

    def get_id(self, address):
        for i, a in self._addresses.iteritems():
            if a[0] == address or a[1] == address: # lan or wan
                return i
        return None
    
    def matches(self, peer):
        assert isinstance(peer, Peer)
        return self.has_any([l for l, _ in peer._addresses.values()], peer._addresses.keys())
            
    def merge(self, peer):
        if self._fake_keys:
            for i, a in peer._addresses.iteritems():
                if a[0] not in self.lan_addresses:
                    self._addresses[i] = a
        else: # Actual endpoint ids as keys
            for i, a in peer._addresses.iteritems():
                self.update_address(a[0], a[1], i)
        
    def update_address(self, lan, wan, endpoint_id):
        if endpoint_id in self._addresses.keys():
            # lan has changed, or lan != wan, so probably an actual wan estimate. So update!
            if lan != self._addresses[endpoint_id][0] or lan != wan: 
                self._addresses[endpoint_id] = (lan, wan)
            # Else, what is there to update?                        
        else:
            self._addresses[endpoint_id] = (lan, wan)
            
    def update_wan(self, lan, wan):
        # Assuming lan is already in there (otherwise how find this peer?)
        if lan == wan: # No point in setting wan to the same as lan, perhaps even overwriting actual wan address
            return False
        i = None
        for i, a in self._addresses.iteritems():
            if a[0] == lan:
                break
        if i is not None:
            self._addresses[i] = (lan, wan)
            return True
        return False

    def __eq__(self, other):
        if not isinstance(other, Peer):
            return False
        # Only if each address in other matches an address in this, do they match
        return len(self.addresses) == len(other.addresses) and all([o in self.addresses for o in other.addresses])
    
    def __hash__(self):
        h = hash(None)
        for a in self.addresses:
            h |= hash(a)
        return h
    
    def has_any(self, addrs=[], ids=[]):
        """
        Return whether any of these addresses is the same as any of this _peers'
        @param addrs: List(Address)
        """
        for i, a in self._addresses.iteritems():
            if i in ids or a[0] in addrs or a[1] in addrs:
                return True
        return False