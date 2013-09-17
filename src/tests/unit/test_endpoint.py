'''
Created on Sep 17, 2013

@author: Vincent Ketelaars
'''
import unittest
import os
import time
import binascii
from sets import Set

from dispersy.callback import Callback
from dispersy.dispersy import Dispersy

from src.swift.swift_process import MySwiftProcess
from src.dispersy_extends.endpoint import MultiEndpoint, SwiftEndpoint, get_hash
from src.definitions import SWIFT_BINPATH, HASH_LENGTH

def get_file():
    dir_ = os.getenv("HOME")+ "/Downloads"
    files = [os.path.join(dir_, f) for f in os.listdir(dir_) if os.path.isfile(os.path.join(dir_, f))]
    if not files:
        dir_ = os.getenv("HOME")+ "/Documents"
        files = [os.path.join(dir_, f) for f in os.listdir(dir_) if os.path.isfile(os.path.join(dir_, f))]
    return files[0]

def remove_files(filename):
    mhash = filename +".mhash"
    if os.path.exists(mhash):
        os.remove(mhash)
    mbinmap = filename+".mbinmap"
    if os.path.exists(mbinmap):
        os.remove(mbinmap)
    dir_ = os.path.dirname(filename)
    swift = [os.path.join(dir_,f) for f in os.listdir(dir_) if f.find("swifturl-") != -1]
    for s in swift:
        os.remove(s)

class TestSwiftEndpoint(unittest.TestCase):


    def setUp(self):
        callback = Callback("TestCallback")
        self._port = 11223
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, self._port, None, None, None)
        self._endpoint = SwiftEndpoint(swift_process, SWIFT_BINPATH)
        self._dispersy = Dispersy(callback, self._endpoint, u".", u":memory:")
        self._dispersy.start()
        self._filename = None

    def tearDown(self):
        self._dispersy.stop()
        if self._filename is not None:
            remove_files(self._filename)

    def test_address(self):
        address = self._endpoint.get_address()
        self.assertEqual(address[1], self._port)
        self.assertNotEqual(address[0], "0.0.0.0")
        
    def test_seed_and_download(self):
        callback = Callback("TestCallback2")
        port = 34254
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, port, None, None, None)
        endpoint = SwiftEndpoint(swift_process, SWIFT_BINPATH)
        dispersy = Dispersy(callback, endpoint, u".", u":memory:")
        dispersy.start()
        
        self._filename = get_file()
        roothash = get_hash(self._filename, SWIFT_BINPATH)
        
        self._endpoint.add_file(self._filename, roothash)
        roothash_unhex=binascii.unhexlify(roothash)
        self._endpoint.add_peer(("127.0.0.1",port), roothash_unhex)
        directories = "testcase_swift_seed_and_down/"
        dest_dir = os.getenv("HOME")+ "/Downloads"
        endpoint.start_download(os.path.basename(self._filename), directories, roothash, dest_dir)
        
        while True:
            check = True
            for d in endpoint.downloads.values():
                if not d.is_finished():
                    check = False
            if check:
                break
            time.sleep(0.5)
            
        dispersy.stop()
        self.assertTrue(os.path.exists(os.path.join(dest_dir, directories, os.path.basename(self._filename))))

class TestMultiEndpoint(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass


    def testName(self):
        pass
    
class TestStaticMethods(unittest.TestCase):

    def setUp(self):
        self.filename = get_file()

    def tearDown(self):
        remove_files(self.filename)
    
    def test_get_hash(self):
        self.assertTrue(os.path.exists(self.filename), "Make sure that the file you want the roothash of exists")
        roothash = get_hash(self.filename, SWIFT_BINPATH)
        self.assertTrue(roothash is not None)
        self.assertEqual(len(roothash), HASH_LENGTH)

if __name__ == "__main__":
    unittest.main()