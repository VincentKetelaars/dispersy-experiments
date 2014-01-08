'''
Created on Jan 7, 2014

@author: Vincent Ketelaars
'''
import unittest
import binascii
import os
import time

from src.swift.swift_process import MySwiftProcess # Before other import because of logger
from dispersy.callback import Callback

from src.address import Address
from src.definitions import SWIFT_BINPATH, TIMEOUT_TESTS, SLEEP_TIME,\
    MASTER_MEMBER_PUBLIC_KEY, SECURITY
from src.dispersy_extends.endpoint import MultiEndpoint, get_hash
from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.mydispersy import MyDispersy

from src.tests.unit.definitions import DIRECTORY, FILES, DISPERSY_WORKDIR
from src.tests.unit.test_endpoint import remove_files

from src.logger import get_logger
logger = get_logger(__name__)


class TestSwiftCommunity(unittest.TestCase):
    
    def create_mycommunity(self, dispersy):    
        master_member = dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
        my_member = dispersy.get_new_member(SECURITY)
        return MyCommunity.join_community(dispersy, master_member, my_member, *(), **{"enable":False})

    def setUp(self):
        callback = Callback("TestCallback")
        self._ports = [12544]
        self._addrs = [Address(port=p, ip="127.0.0.1") for p in self._ports]
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, self._addrs, None, None, None)
        self._endpoint = MultiEndpoint(swift_process)
        self._dispersy = MyDispersy(callback, self._endpoint, DISPERSY_WORKDIR, u":memory:")
        self._dispersy.start()
        self._community = callback.call(self.create_mycommunity, (self._dispersy,))
        self._swiftcomm = self._community.swift_community
        self._directories = "testcase_swift_seed_and_down/"
        self._dest_dir = DIRECTORY
        self._filename = FILES[0]
        self._roothash = get_hash(self._filename, SWIFT_BINPATH)
        
        callback2 = Callback("TestCallback2")
        self._ports2 = [34254]
        self._addrs2 = [Address(port=p, ip="127.0.0.1") for p in self._ports2]
        swift_process2 = MySwiftProcess(SWIFT_BINPATH, ".", None, self._addrs2, None, None, None)
        self._endpoint2 = MultiEndpoint(swift_process2)
        self._dispersy2 = MyDispersy(callback2, self._endpoint2, u".", u":memory:")
        self._dispersy2.start()
        self._community2 = callback2.call(self.create_mycommunity, (self._dispersy2,))
        self._community2.dest_dir = self._dest_dir
        self._swiftcomm2 = self._community2.swift_community

    def tearDown(self):
        self._dispersy.stop()
        self._dispersy2.stop()
        for f in FILES:
            remove_files(f) # Remove hashmap and bin files
#         dir_ = os.path.join(self._dest_dir, self._directories)
#         if os.path.isdir(dir_):
#             for f in os.listdir(dir_):
#                 os.remove(os.path.join(dir_, f))
#             os.removedirs(dir_)
          
    def test_seed_and_download(self):           
        self._swiftcomm.add_file(self._filename, self._roothash)
        roothash_unhex=binascii.unhexlify(self._roothash)
        self._swiftcomm.add_peer(roothash_unhex, self._addrs2[0])
        self._swiftcomm2.filehash_received(self._filename, self._directories, self._roothash, self._addrs2)
           
        self._wait()
        
        self.assertTrue(os.path.exists(os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))))
          
    def test_duplicate_roothash_and_cleanup(self):           
        self._swiftcomm.add_file(self._filename, self._roothash)
        roothash_unhex=binascii.unhexlify(self._roothash)
        self._swiftcomm.add_peer(roothash_unhex, self._addrs2[0])
        self._swiftcomm.add_file(self._filename, self._roothash)
        self._swiftcomm.add_peer(roothash_unhex, self._addrs2[0])
        self._swiftcomm2.filehash_received(self._filename, self._directories, self._roothash, self._addrs2)
        self._swiftcomm2.filehash_received(self._filename, self._directories, self._roothash, self._addrs2)
        file2 = FILES[1]
        roothash2 = get_hash(file2, SWIFT_BINPATH)
        roothash_unhex=binascii.unhexlify(roothash2)
        self._swiftcomm.add_file(file2, roothash2)
        self._swiftcomm.add_peer(roothash_unhex, self._addrs2[0])
        self._swiftcomm2.filehash_received(file2, self._directories, roothash2, self._addrs2)
                
        self._wait()
         
        absfilename1 = os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))
        absfilename2 = os.path.join(self._dest_dir, self._directories, os.path.basename(file2))
          
        # Check that files have been downloaded
        self.assertTrue(os.path.exists(absfilename1))
        self.assertTrue(os.path.exists(absfilename2))
          
        # Check that checkpoint is created, and the mhash file is maintained.
        self.assertTrue(os.path.exists(absfilename1 + ".mhash"))
        self.assertTrue(os.path.exists(absfilename1 + ".mbinmap"))
        self.assertTrue(os.path.exists(absfilename2 + ".mhash"))
        self.assertTrue(os.path.exists(absfilename2 + ".mbinmap"))
        
    
    def test_restart(self): 
        # Send fake message over cmdgw, which will lead to an error 
        self._endpoint._swift.write("message designed to crash tcp conn\n")
        self._swiftcomm.add_file(self._filename, self._roothash)
        roothash_unhex=binascii.unhexlify(self._roothash)
        self._swiftcomm.add_peer(roothash_unhex, self._addrs2[0])
        self._swiftcomm2.filehash_received(self._filename, self._directories, self._roothash, self._addrs2)
  
        self._wait()
        
        res_path = os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))
        self.assertTrue(os.path.exists(res_path))
        remove_files(res_path)   

    def _wait(self):
        for _ in range(int(TIMEOUT_TESTS / SLEEP_TIME)):
            check = True
            for d in self._swiftcomm2.downloads.values():
                if not d.is_finished():
                    logger.debug("Not ready %s", d.roothash_as_hex())
                    check = False
            if check:
                break
            time.sleep(SLEEP_TIME)

    # TODO: Create test that will see if Endpoint handles no Swift well

if __name__ == "__main__":
    unittest.main()