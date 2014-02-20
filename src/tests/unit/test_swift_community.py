'''
Created on Jan 7, 2014

@author: Vincent Ketelaars
'''
import unittest
import os
import time

from src.swift.swift_process import MySwiftProcess # Before other import because of logger
from dispersy.callback import Callback

from src.address import Address
from src.definitions import SWIFT_BINPATH, SLEEP_TIME,\
    MASTER_MEMBER_PUBLIC_KEY, SECURITY
from src.dispersy_extends.endpoint import MultiEndpoint, get_hash
from src.dispersy_extends.community import MyCommunity
from src.dispersy_extends.mydispersy import MyDispersy
from src.dispersy_extends.payload import FileHashCarrier
from src.dispersy_extends.candidate import EligibleWalkCandidate

from src.tests.unit.definitions import DIRECTORY, FILES, DISPERSY_WORKDIR, TIMEOUT_TESTS
from src.tests.unit.test_endpoint import remove_files

from src.logger import get_logger
logger = get_logger(__name__)


class TestSwiftCommunity(unittest.TestCase):
    
    def api_callback(self, key, *args, **kwargs):
        logger.debug("%d %s %s", key, args, kwargs)
    
    def add_file(self, callback, community, message):
        community.create_file_hash_messages(1, message, 0.0, update=False)
        
    def candidate(self, addr):
        return EligibleWalkCandidate(addr, True, addr, addr, u"unknown")
    
    def create_mycommunity(self, dispersy):    
        master_member = dispersy.get_member(MASTER_MEMBER_PUBLIC_KEY)
        my_member = dispersy.get_new_member(SECURITY)
        return MyCommunity.join_community(dispersy, master_member, my_member, *(), **{"enable":False, "api_callback" : self.api_callback})

    def setUp(self):
        self._callback = Callback("TestCallback")
        self._ports = [12544]
        self._addrs = [Address(port=p, ip="127.0.0.1") for p in self._ports]
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, self._addrs, None, None, None)
        self._endpoint = MultiEndpoint(swift_process)
        self._dispersy = MyDispersy(self._callback, self._endpoint, DISPERSY_WORKDIR, u":memory:")
        self._dispersy.start()
        self._community = self._callback.call(self.create_mycommunity, (self._dispersy,))
        self._swiftcomm = self._community.swift_community
        self._directories = "testcase_swift_seed_and_down/"
        self._dest_dir = DIRECTORY
        self._community.dest_dir = self._dest_dir
        self._filename = FILES[0]
        self._roothash = get_hash(self._filename, SWIFT_BINPATH)
        
        self._callback2 = Callback("TestCallback2")
        self._ports2 = [34254]
        self._addrs2 = [Address(port=p, ip="127.0.0.1") for p in self._ports2]
        swift_process2 = MySwiftProcess(SWIFT_BINPATH, ".", None, self._addrs2, None, None, None)
        self._endpoint2 = MultiEndpoint(swift_process2)
        self._dispersy2 = MyDispersy(self._callback2, self._endpoint2, u".", u":memory:")
        self._dispersy2.start()
        self._community2 = self._callback2.call(self.create_mycommunity, (self._dispersy2,))
        self._community2.dest_dir = self._dest_dir
        self._swiftcomm2 = self._community2.swift_community
        self._filename2 = FILES[1]
        self._roothash2 = get_hash(self._filename2, SWIFT_BINPATH)

    def tearDown(self):
        self._dispersy.stop(timeout=0.0)
        self._dispersy2.stop(timeout=0.0)
        for f in FILES:
            remove_files(f) # Remove hashmap and bin files
        dir_ = os.path.join(self._dest_dir, self._directories)
        if os.path.isdir(dir_):
            for f in os.listdir(dir_):
                os.remove(os.path.join(dir_, f))
            os.removedirs(dir_)
          
    def test_seed_and_download(self):           
        self.add_file(self._callback, self._community, 
                      FileHashCarrier(self._filename, self._directories, self._roothash, os.path.getsize(self._filename), 
                                      os.path.getmtime(self._filename), None))
        self._community.add_candidate(self.candidate(self._addrs2[0].addr()))
           
        self._wait(self._swiftcomm2)
        
        self.assertTrue(os.path.exists(os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))))
    
    def test_seed_and_download_both(self):           
        self.add_file(self._callback, self._community, 
                      FileHashCarrier(self._filename, self._directories, self._roothash, os.path.getsize(self._filename), 
                                      os.path.getmtime(self._filename), None))
        self.add_file(self._callback2, self._community2, 
                      FileHashCarrier(self._filename2, self._directories, self._roothash2, os.path.getsize(self._filename2), 
                                      os.path.getmtime(self._filename2), None))
        self._community.add_candidate(self.candidate(self._addrs2[0].addr()))
           
        self._wait(self._swiftcomm, self._swiftcomm2, n=2)
        
        self.assertTrue(os.path.exists(os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))))
        self.assertTrue(os.path.exists(os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename2))))
    
    def test_duplicate_roothash_and_cleanup(self):           
        self.add_file(self._callback, self._community, 
                      FileHashCarrier(self._filename, self._directories, self._roothash, os.path.getsize(self._filename), 
                                      os.path.getmtime(self._filename), None))
        self._community.add_candidate(self.candidate(self._addrs2[0].addr()))
        self.add_file(self._callback, self._community, 
                      FileHashCarrier(self._filename, self._directories, self._roothash, os.path.getsize(self._filename), 
                                      os.path.getmtime(self._filename), None))
        self._community.add_candidate(self.candidate(self._addrs2[0].addr()))
        file2 = FILES[1]
        roothash2 = get_hash(file2, SWIFT_BINPATH)
        self.add_file(self._callback, self._community, 
                      FileHashCarrier(file2, self._directories, roothash2, os.path.getsize(file2), 
                                      os.path.getmtime(file2), None))
        self._wait(self._swiftcomm2)
         
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
        self.add_file(self._callback, self._community, 
                      FileHashCarrier(self._filename, self._directories, self._roothash, os.path.getsize(self._filename), 
                                      os.path.getmtime(self._filename), None))
        self._community.add_candidate(self.candidate(self._addrs2[0].addr()))
  
        self._wait(self._swiftcomm2)
        
        res_path = os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))
        self.assertTrue(os.path.exists(res_path))

    def _wait(self, *scomms, **kwargs):
        n = 1
        if "n" in kwargs.iterkeys():
            n = kwargs["n"]
        for _ in range(int(TIMEOUT_TESTS / SLEEP_TIME)):
            check = True
            for sc in scomms:
                for d in sc.downloads.values():
                    if not d.is_finished():
                        check = False
                if len(sc.downloads.values()) < n:
                    check = False
            if check:
                break
            time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    unittest.main()