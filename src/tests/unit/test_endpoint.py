'''
Created on Sep 17, 2013

@author: Vincent Ketelaars
'''
import binascii
import os
import unittest
import time

from dispersy.callback import Callback
from dispersy.dispersy import Dispersy
from dispersy.endpoint import NullEndpoint

from src.definitions import SWIFT_BINPATH, HASH_LENGTH, TIMEOUT, SLEEP_TIME
from src.dispersy_extends.endpoint import MultiEndpoint, SwiftEndpoint, get_hash
from src.swift.swift_process import MySwiftProcess

def get_file(num=0):
    dir_ = os.getenv("HOME")+ "/Downloads"
    files = [os.path.join(dir_, f) for f in os.listdir(dir_) if os.path.isfile(os.path.join(dir_, f))]
    if not files or len(files) < num:
        dir_ = os.getenv("HOME")+ "/Documents"
        files = [os.path.join(dir_, f) for f in os.listdir(dir_) if os.path.isfile(os.path.join(dir_, f))]
    return files[num]

def remove_files(filename):
    dir_ = os.path.dirname(filename)
    for f in os.listdir(dir_):
        if f.endswith(".mhash") or f.endswith(".mbinmap") or f.find("swifturl-") != -1:
            os.remove(os.path.join(dir_, f))

class TestSwiftEndpoint(unittest.TestCase):

    def setUp(self):
        callback = Callback("TestCallback")
        self._port = 11223
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, self._port, None, None, None)
        self._endpoint = SwiftEndpoint(swift_process, SWIFT_BINPATH)
        self._dispersy = Dispersy(callback, self._endpoint, u".", u":memory:")
        self._dispersy.start()
        self._directories = "testcase_swift_seed_and_down/"
        self._dest_dir = os.getenv("HOME")+ "/Downloads"
        self._filename = get_file()
        self._roothash = get_hash(self._filename, SWIFT_BINPATH)

    def tearDown(self):
        self._dispersy.stop()
        if self._filename is not None:
            remove_files(self._filename)
        dir_ = os.path.join(self._dest_dir, self._directories)
        if os.path.isdir(dir_):
            for f in os.listdir(dir_):
                os.remove(os.path.join(dir_, f))
            os.removedirs(dir_)

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
           
        self._endpoint.add_file(self._filename, self._roothash)
        roothash_unhex=binascii.unhexlify(self._roothash)
        self._endpoint.add_peer(("127.0.0.1",port), roothash_unhex)
        endpoint.start_download(self._filename, self._directories, self._roothash, self._dest_dir)
           
        for _ in range(int(TIMEOUT / SLEEP_TIME)):
            check = True
            for d in endpoint.downloads.values():
                if not d.is_finished():
                    check = False
            if check:
                break
            time.sleep(SLEEP_TIME)
               
        dispersy.stop()
        self.assertTrue(os.path.exists(os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))))
         
    def test_duplicate_roothash_and_clean_up(self):
        callback = Callback("TestCallback2")
        port = 34254
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, port, None, None, None)
        endpoint = SwiftEndpoint(swift_process, SWIFT_BINPATH)
        dispersy = Dispersy(callback, endpoint, u".", u":memory:")
        dispersy.start()
           
        addr = ("127.0.0.1", port)
        self._endpoint.add_file(self._filename, self._roothash)
        roothash_unhex=binascii.unhexlify(self._roothash)
        self._endpoint.add_peer(addr, roothash_unhex)
        self._endpoint.add_file(self._filename, self._roothash)
        self._endpoint.add_peer(addr, roothash_unhex)
        endpoint.start_download(self._filename, self._directories, self._roothash, self._dest_dir)
        endpoint.start_download(self._filename, self._directories, self._roothash, self._dest_dir)
        file2 = get_file(1)
        roothash2 = get_hash(file2, SWIFT_BINPATH)
        roothash_unhex=binascii.unhexlify(roothash2)
        self._endpoint.add_file(file2, roothash2)
        self._endpoint.add_peer(addr, roothash_unhex)
        endpoint.start_download(file2, self._directories, roothash2, self._dest_dir)
       
        for _ in range(int(TIMEOUT / SLEEP_TIME)):
            check = True
            for d in endpoint.downloads.values():
                if not d.is_finished():
                    check = False
            if check:
                break
            time.sleep(SLEEP_TIME)
               
        dispersy.stop()
         
        absfilename1 = os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))
        absfilename2 = os.path.join(self._dest_dir, self._directories, os.path.basename(file2))
         
        # Check that files have been downloaded
        self.assertTrue(os.path.exists(absfilename1))
        self.assertTrue(os.path.exists(absfilename2))
         
        # Check that files created for download have been removed
        self.assertFalse(os.path.exists(absfilename1 + ".mhash"))
        self.assertFalse(os.path.exists(absfilename1 + ".mbinmap"))
        self.assertFalse(os.path.exists(absfilename2 + ".mhash"))
        self.assertFalse(os.path.exists(absfilename2 + ".mbinmap"))
         
    def test_restart(self):
        callback = Callback("TestCallback2")
        port = 34254
        swift_process = MySwiftProcess(SWIFT_BINPATH, ".", None, port, None, None, None)
        endpoint = SwiftEndpoint(swift_process, SWIFT_BINPATH)
        dispersy = Dispersy(callback, endpoint, u".", u":memory:")
        dispersy.start()
         
        # Send fake message over cmdgw, which will lead to an error 
        self._endpoint._swift.write("START stuff to do..;)")
        addr = ("127.0.0.1", port)
        self._endpoint.add_file(self._filename, self._roothash)
        roothash_unhex=binascii.unhexlify(self._roothash)
        self._endpoint.add_peer(addr, roothash_unhex)
        endpoint.start_download(self._filename, self._directories, self._roothash, self._dest_dir, addr)
 
        for _ in range(int(TIMEOUT / SLEEP_TIME)):
            check = True
            for d in endpoint.downloads.values():
                if not d.is_finished():
                    check = False
            if check:
                break
            time.sleep(SLEEP_TIME)
               
        dispersy.stop()
        self.assertTrue(os.path.exists(os.path.join(self._dest_dir, self._directories, os.path.basename(self._filename))))

class TestMultiEndpoint(unittest.TestCase):


    def setUp(self):
        self._me = MultiEndpoint()

    def tearDown(self):
        self._me = None

    def test_add_and_remove_endpoint(self):
        dispersy = 1
        ne = NullEndpoint(23456)
        ne.open(dispersy)
        self._me.add_endpoint(ne)
        self.assertEqual(len(self._me._endpoints), 1)
        self.assertEqual(self._me._endpoint, ne) 
        ne2 = NullEndpoint(23457)
        ne2.open(dispersy)
        self._me.add_endpoint(ne2)
        self.assertEqual(len(self._me._endpoints), 2)
        self.assertEqual(self._me._endpoint, ne) # Still the first endpoint at point
        self._me.remove_endpoint(ne)
        self.assertEqual(len(self._me._endpoints), 1)
        self.assertEqual(self._me._endpoint, ne2) # The one left should now take over
        self._me.add_endpoint(ne)
        ne.open(dispersy)
        self._me._endpoint = ne
        self._me.remove_endpoint(ne)
        self.assertEqual(self._me._endpoint, ne2)
        self._me.remove_endpoint(ne2)
        self.assertEqual(len(self._me._endpoints), 0)
        self.assertEqual(self._me._endpoint, None)
        
    def test_address(self):
        addr = 34254
        ne = NullEndpoint(addr)
        self._me.add_endpoint(ne)
        self.assertEqual(self._me.get_address(), addr)
    
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