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
from src.tests.unit.mock_classes import FakeDispersy, FakeSwift

from src.logger import get_logger
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
        self._dispersy.stop()
        self._dispersy2.stop()
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