'''
Created on Sep 10, 2013

@author: Vincent Ketelaars
'''
import unittest
import os
import time

from src.filepusher import FilePusher
from src.definitions import SWIFT_BINPATH, MAX_MESSAGE_SIZE, HASH_LENGTH, FILENAMES_NOT_TO_SEND, FILETYPES_NOT_TO_SEND

from src.tests.unit.definitions import DIRECTORY, FILES

all_success = False
        
def success_decorater(func):
    def dec(*args, **kwargs):
        func(*args, **kwargs)
        TestFilePusher.set_success()
    return dec

class TestFilePusher(unittest.TestCase): 
    
    @staticmethod
    def set_success():
        global all_success
        all_success = True

    def setUp(self):
        self._directory = DIRECTORY
        self._files = FILES
        self._copy_files = set(self._files)
        self._filepusher = None

    def tearDown(self):
        if self._filepusher is not None:
            self._filepusher.stop()
        
        def rm(dirp):
            for p in os.listdir(dirp):
                path = os.path.join(dirp, p)
                if p.endswith(".mbinmap") or p.endswith(".mhash") or p.find("swifturl-") >= 0:
                    os.remove(path)
                if os.path.isdir(path):
                    rm(path)
        
        if self._directory is not None:            
            rm(self._directory)
            
        for f in self._copy_files:
            binpath = f + ".mbinmap"
            hashpath = f + ".mhash"
            if os.path.exists(binpath):
                os.remove(binpath)
            if os.path.exists(hashpath):
                os.remove(hashpath)
            
    def get_files_from_directory_recur(self, dirp, hidden=False):
        files = [os.path.join(dirp, f) for f in os.listdir(dirp) if os.path.isfile(os.path.join(dirp, f)) and 
                         # which do not end in any of the FILETYPES_NOT_TO_SEND or contain FILENAMES_NOT_TO_SEND
                         not (any(f.endswith(t) for t in FILETYPES_NOT_TO_SEND) or 
                              any(f.find(n) >= 0 for n in FILENAMES_NOT_TO_SEND)) and
                        # which if not hidden, do no start with a dot
                         not (not hidden and f[0] == ".") ]
        dirs = [os.path.join(dirp, f) for f in os.listdir(dirp) if os.path.isdir(os.path.join(dirp, f))]
        for d in dirs:
            if not (not hidden and d.startswith(".")):
                files.extend(self.get_files_from_directory_recur(d))
        return files
    
    def check_filename(self, filename):
        for e in FILENAMES_NOT_TO_SEND:
            self.assertEqual(filename.find(e), -1, filename + " contains " + e)
        for e in FILETYPES_NOT_TO_SEND:
            self.assertFalse(filename.endswith(e), filename + " ends with " + e)
            
    def wait_and_asses(self, all_files):
        time.sleep(1) # First sleep a while till you are sure that files have been added to the queue

        while not self._filepusher._thread_func.queue.empty(): # continue while the queue still has files left
            time.sleep(1)
        
        time.sleep(1) # Wait another second because empty queue does not mean finished yet.
        
        self.assertEqual(all_files, set())
    
    def test_directory(self):        
        if all_success:
            raise unittest.SkipTest("The combined test case test_dir_and_files has already been succesful")
        all_files = set(self.get_files_from_directory_recur(self._directory))

        def callback(message):
            all_files.remove(message.filename)
            self.check_filename(message.filename)
            if os.path.getsize(message.filename) > MAX_MESSAGE_SIZE:
                self.assertEqual(len(message.roothash), HASH_LENGTH)
                
        self._filepusher = FilePusher(callback, SWIFT_BINPATH, directories=[self._directory])
        self._filepusher.start()
        
        self.wait_and_asses(all_files)
    
    def test_files(self):
        all_files = set(self.get_files_from_directory_recur(self._directory))

        def callback(message):
            all_files.remove(message.filename)
            self.check_filename(message.filename)
            if os.path.getsize(message.filename) > MAX_MESSAGE_SIZE:
                self.assertEqual(len(message.roothash), HASH_LENGTH)
                
        self._filepusher = FilePusher(callback, SWIFT_BINPATH, files=all_files)
        self._filepusher.start()

        self.wait_and_asses(all_files)
        
    def test_min_timestamp(self):
        all_files = set(self.get_files_from_directory_recur(self._directory))

        def callback(message):
            raise AssertionError("Should be no files")
                
        self._filepusher = FilePusher(callback, SWIFT_BINPATH, files=all_files, min_timestamp=time.time())
        self._filepusher.start()

        time.sleep(3)
        
        # If something came up, it would have already
    
    @success_decorater
    def test_dir_and_files(self):
        all_files = set(self.get_files_from_directory_recur(self._directory)).union(set(self._files))
        
        def callback(message):
            all_files.remove(message.filename)
            self.check_filename(message.filename)
            if os.path.getsize(message.filename) > MAX_MESSAGE_SIZE:
                self.assertEqual(len(message.roothash), HASH_LENGTH)
                
        self._filepusher = FilePusher(callback, SWIFT_BINPATH, directories=[self._directory], files=self._files)
        self._filepusher.start()
        
        self.wait_and_asses(all_files)

if __name__ == "__main__":
    unittest.main()