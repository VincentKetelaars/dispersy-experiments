'''
Created on Sep 17, 2013

@author: Vincent Ketelaars
'''
import binascii
import os
import unittest
import time

from src.swift.swift_process import MySwiftProcess # Before other import because of logger
from dispersy.callback import Callback

from src.address import Address
from src.definitions import SWIFT_BINPATH, HASH_LENGTH, SLEEP_TIME
from src.dispersy_extends.endpoint import MultiEndpoint, get_hash, try_sockets
from src.dispersy_extends.mydispersy import MyDispersy

from src.tests.unit.definitions import DIRECTORY, FILES, DISPERSY_WORKDIR, TIMEOUT_TESTS
from src.tests.unit.mock_classes import FakeDispersy, FakeSwift,\
    FakeCommonEndpoint, FakeCommunity

from src.logger import get_logger
from src.peer import Peer
logger = get_logger(__name__)
   
class TestEndpointNoConnection(unittest.TestCase):
                
    def turn_wlan0_on(self):
        cmd = 'ifconfig wlan0 up'
        os.system(cmd)
        
    def turn_wlan0_off(self):
        cmd = 'ifconfig wlan0 down'
        os.system(cmd)
    
    def setUp(self):
        self.turn_wlan0_off()
        
        callback = Callback("TestCallback")
        self._ports = [12344]
        self._addrs = [Address(port=p) for p in self._ports]
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, self._addrs, None, None, None)
        self._endpoint = MultiEndpoint(swift_process)
        self._dispersy = MyDispersy(callback, self._endpoint, DISPERSY_WORKDIR, u":memory:")
        self._dispersy.start()
        self._directories = "testcase_swift_seed_and_down/"
        self._dest_dir = DIRECTORY
        self._filename = FILES[0]
        self._roothash = get_hash(self._filename, SWIFT_BINPATH)
        
        callback2 = Callback("TestCallback2")
        self._ports2 = [34254]
        self._addrs2 = [Address(port=p) for p in self._ports2]
        swift_process2 = MySwiftProcess(SWIFT_BINPATH, ".", None, self._addrs2, None, None, None)
        self._endpoint2 = MultiEndpoint(swift_process2)
        self._dispersy2 = MyDispersy(callback2, self._endpoint2, u".", u":memory:")
        self._dispersy2.start()
        
    def tearDown(self):
        self._dispersy.stop(timeout=0.0)
        self._dispersy2.stop(timeout=0.0)
        if self._filename is not None:
            remove_files(self._filename)
        dir_ = os.path.join(self._dest_dir, self._directories)
        if os.path.isdir(dir_):
            for f in os.listdir(dir_):
                os.remove(os.path.join(dir_, f))
            os.removedirs(dir_)
    
    # @unittest.skipIf(os.geteuid() != 0, "Root privileges necessary to handle this testcase")
    # Shutting down wifi is easy.. Getting it back up less so
    @unittest.skip("Don't do this for now..")
    def test_temp_no_wifi(self): 
        self._endpoint.add_file(self._filename, self._roothash)
        roothash_unhex=binascii.unhexlify(self._roothash)
        self._endpoint.add_peer(self._addrs2[0], roothash_unhex)
        self._endpoint2.start_download(self._filename, self._directories, self._roothash, self._dest_dir, self._addrs2)
  
        self._wait()
           
        self.assertTrue(os.path.exists(os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))))
        
    def _wait(self):
        for i in range(int(TIMEOUT_TESTS / SLEEP_TIME)):
            if i * SLEEP_TIME >= 1:
                self.turn_wlan0_on()
            check = True
            for d in self._endpoint2.downloads.values():
                if not d.is_finished():
                    check = False
            if check:
                break
            time.sleep(SLEEP_TIME)
            
class TestCommonEndpoint(unittest.TestCase):
    
    def setUp(self):
        self.common = FakeCommonEndpoint(None)
    
    def test_update_contacts(self):
        sock_addr = ("1.1.1.1", 3)
        packets = ["asdf", "sf"]
        comm, dc = self.common.update_dispersy_contacts(sock_addr, packets, recv=False)
        first_contact = iter(self.common.dispersy_contacts).next()
        self.assertEqual(dc, None)
        self.assertEqual(len(self.common.dispersy_contacts), 1)
        self.assertEqual(first_contact.address.ip, sock_addr[0])
        self.assertEqual(self.common.get_contact(Address.tuple(sock_addr)), first_contact)
        more_packets = ["sfjdoiwenfo", "sfjisa"]
        comm, dc = self.common.update_dispersy_contacts(sock_addr, more_packets, recv=False)
        self.assertEqual(dc, None)
        self.assertEqual(len(self.common.dispersy_contacts), 1)
        self.assertEqual(first_contact.num_sent(), len(packets + more_packets))
        self.assertEqual(first_contact.total_sent(), sum(len(p) for p in packets + more_packets))
        comm, dc = self.common.update_dispersy_contacts(sock_addr, more_packets, recv=True)
        self.assertEqual(dc, first_contact, str(dc) + " != " + str(first_contact))
        self.assertEqual(len(self.common.dispersy_contacts), 1)
        self.assertEqual(first_contact.num_sent(), len(packets + more_packets))
        self.assertEqual(first_contact.total_sent(), sum(len(p) for p in packets + more_packets))
        self.assertEqual(first_contact.num_rcvd(), len(more_packets))
        self.assertEqual(first_contact.total_rcvd(), sum(len(p) for p in more_packets))
        new_sock_addr = ("2.2.1.2", 5)
        comm, dc = self.common.update_dispersy_contacts(new_sock_addr, packets, recv=True)
        for c in self.common.dispersy_contacts:
            if c != first_contact:
                second_contact = c
        self.assertEqual(dc, second_contact)
        self.assertEqual(len(self.common.dispersy_contacts), 2)
        self.assertEqual(first_contact.num_sent(), len(packets + more_packets))
        self.assertEqual(first_contact.total_sent(), sum(len(p) for p in packets + more_packets))
        self.assertEqual(first_contact.num_rcvd(), len(more_packets))
        self.assertEqual(first_contact.total_rcvd(), sum(len(p) for p in more_packets))
        self.assertEqual(second_contact.num_rcvd(), len(packets))
        self.assertEqual(second_contact.total_rcvd(), sum(len(p) for p in packets))
        
    def test_unknown_peer(self):
        # Case where these addresses do not match any incoming addresses
        # This is possible if the peer does not know its proper wan address
        community = FakeCommunity()
        mid = "Smoothy"
        lan_addresses = [Address(ip="127.3.2.4", port=123)]
        wan_addresses = [Address(ip="42.23.2.1", port=332)]
        ids = [os.urandom(16)]
        dc = self.common.peer_endpoints_received(community, mid, lan_addresses, wan_addresses, ids)
        self.assertEqual(len(self.common.dispersy_contacts), 1)
        self.assertEqual(dc.peer, Peer(lan_addresses, wan_addresses, ids, mid))
        self.assertEqual(dc.member_id, mid)
        self.assertEqual(len(dc.community_ids), 1)
        self.assertEqual(iter(dc.community_ids).next(), community.cid)
        self.assertEqual(self.common.get_contact(Address(), mid=mid), dc)
        dc2 = self.common.peer_endpoints_received(community, mid, lan_addresses, wan_addresses, ids)
        self.assertEqual(dc2, dc)        
        self.assertEqual(dc2.peer, dc.peer)
        
    def test_one_contact_peer(self):
        # DispersyCandidate is already there
        community = FakeCommunity()
        mid = "Smoothy"
        lan_addresses = [Address(ip="127.3.2.4", port=123)]
        wan_addresses = [Address(ip="42.23.2.1", port=332)]
        ids = [os.urandom(16)]
        comm, first_contact = self.common.update_dispersy_contacts(wan_addresses[0].addr(), ["asdf"], recv=True)
        dc = self.common.peer_endpoints_received(community, mid, lan_addresses, wan_addresses, ids)
        self.assertEqual(first_contact, dc)
        self.assertEqual(dc.peer, Peer(lan_addresses, wan_addresses, ids, mid))
        self.assertEqual(len(self.common.dispersy_contacts), 1)
        
    def test_two_contacts_one_peer(self):
        # here are two DispersyCandidates that represent the same peer
        community = FakeCommunity()
        mid = "Smoothy"
        lan_addresses = [Address(ip="127.3.2.4", port=123)]
        wan_addresses = [Address(ip="42.23.2.1", port=332)]
        ids = [os.urandom(16)]
        comm, first_contact = self.common.update_dispersy_contacts(lan_addresses[0].addr(), ["asdf"], recv=True)
        comm, second_contact = self.common.update_dispersy_contacts(wan_addresses[0].addr(), ["asdf"], recv=True)
        dc = self.common.peer_endpoints_received(community, mid, lan_addresses, wan_addresses, ids)
        self.assertIn(dc, [first_contact, second_contact])
        self.assertEqual(dc.peer, Peer(lan_addresses, wan_addresses, ids, mid))
        self.assertEqual(len(self.common.dispersy_contacts), 1)
    
class TestMultiEndpoint(unittest.TestCase):
    """
    MultiEndpoit might in the future specifically target SwiftEndpoints
    """

    def setUp(self):
        self._addrs = [Address(port=23456), Address(port=23457)]
        swift = FakeSwift(self._addrs)
        self.dispersy = FakeDispersy()
        self._me = MultiEndpoint(swift)
        self._me.open(self.dispersy)

    def tearDown(self):
        self._me = None

    def test_add_and_remove_endpoint(self):
        ne = self._me.swift_endpoints[0]
        ne2 = self._me.swift_endpoints[1]
        self._me.remove_endpoint(ne)
        self.assertEqual(len(self._me.swift_endpoints), 1)
        self.assertEqual(self._me._endpoint, ne2) # The one left should now take over
        self._me.remove_endpoint(ne2)
        self.assertEqual(len(self._me.swift_endpoints), 0) # No endpoints left
        self.assertEqual(self._me._endpoint, None) # No endpoints left
        
        ne = self._me.add_endpoint(self._addrs[0])
        ne.open(self.dispersy)
        self.assertEqual(len(self._me.swift_endpoints), 1) # One endpoint in the list
        self.assertEqual(self._me._endpoint, ne) 
        ne2 = self._me.add_endpoint(self._addrs[1])
        ne2.open(self.dispersy)
        self.assertEqual(len(self._me.swift_endpoints), 2) # Two endpoint in the list
        self.assertEqual(self._me._endpoint, ne) # Still the first endpoint at point
        
        self._me._endpoint = ne
        self._me.remove_endpoint(ne)
        self.assertEqual(self._me._endpoint, ne2) # ne2 should now again be default endpoint

        
    def test_add_endpoint(self):
        self._me.add_endpoint(self._addrs[0])
        self.assertEqual(self._me._endpoint.address, self._addrs[0])
    

class TestStaticMethods(unittest.TestCase):

    def setUp(self):
        self.filename = FILES[0]

    def tearDown(self):
        remove_files(self.filename)
     
    def test_get_hash(self):
        self.assertTrue(os.path.exists(self.filename), "Make sure that the file, you want the roothash of, exists")
        roothash = get_hash(self.filename, SWIFT_BINPATH)
        self.assertTrue(roothash is not None)
        self.assertEqual(len(roothash), HASH_LENGTH)
    

class TestSocketAvailable(unittest.TestCase):
        
    def setUp(self):
        self._ports = [12345, 12346, 12347]
        self._addrs = [Address.localport(p) for p in self._ports]
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, self._addrs, None, None, None)
        self._endpoint = MultiEndpoint(swift_process)
        self._endpoint.open(FakeDispersy())
        
    def tearDown(self):
        self._endpoint.close()
        
    def test_multiple_sockets_in_use(self):
        self.assertFalse(try_sockets(self._addrs, timeout=1.0))
        
    def test_multiple_sockets_not_in_use(self):
        self._endpoint.close() # Socket should be released within a second
        self.assertTrue(try_sockets(self._addrs, timeout=1.0))


def remove_files(filename, content=False):
    dir_ = os.path.dirname(filename)
    for f in os.listdir(dir_):
        if f == os.path.basename(filename) + ".mhash" or f == os.path.basename(filename) + ".mbinmap" or f.find("swifturl-") != -1:
            logger.debug("Removing %s", os.path.join(dir_, f))
            os.remove(os.path.join(dir_, f))
    if content and os.path.exists(filename):
        logger.debug("Removing %s", filename)
        os.remove(filename)
    logger.debug("Done removing %s", filename)

if __name__ == "__main__":
    unittest.main()