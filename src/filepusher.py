'''
Created on Aug 30, 2013

@author: Vincent Ketelaars
'''

import Queue
from threading import Thread, Event

from string import find
from os import listdir
from os.path import exists, isfile, isdir, getmtime, join, getsize, basename

from src.dispersy_extends.payload import SimpleFileCarrier, FileHashCarrier
from src.dispersy_extends.endpoint import get_hash
from src.definitions import SLEEP_TIME

import logging
logger = logging.getLogger(__name__)

class FilePusher(object):
    '''
    FilePusher goes through a directory or a list of files to find either new files or updated files,
    and does a callback with the list of these files. It distinguishes between files larger and smaller than _file_size.
    In the former case the filename is send back, whereas in the latter case the contents of the file (string) is send back.
    '''
    
    FILE_SIZE = 2**16-60

    def __init__(self, callback, swift_path, directory=None, files=[], file_size=FILE_SIZE):
        '''
        @param callback: The function that will be called with a FileHashCarrier or SimpleFileCarrier object
        @param directory: The directory to search for files
        @param files: The list of files to monitor
        @param file_size: The decision variable for choosing callback object
        '''
        if directory and exists(directory) and isdir(directory):
            self._dir = directory
        else:
            self._dir = None
        
        self._files = []
        if files and hasattr(files, "__iter__"): # It should also have a next (or __next__ in Python 3.x) method
            for f in files:
                if exists(f) and isfile(f):
                    self._files.append(f)
                
        self._recent_files = []
        self._callback = callback
        self._file_size = file_size
        self.swift_path = swift_path
        self._queue = Queue.Queue()
        
    def start(self):
        """
        Start separate thread that calls _loop
        """
        self._thread = Thread(target=self._loop)
        self._thread.daemon = True
        self._thread.start()
        
        self._threada = CallFunctionThread(self._stop_event, self._queue)
        self._threada.daemon = True
        self._threada.start()
        
    def _loop(self):
        """
        Run until _stop_event is set. 
        Determine list of files that have are new or have changed since previous iteration.
        Call _callback with each of these files.
        """
        self._stop_event = Event()
        while not self._stop_event.is_set():
                            
            diff = self._list_files_to_send()
            for absfilename in diff:
                logger.debug("New file to be sent: %s", absfilename)
                if getsize(absfilename) > self._file_size:
                    loc = find(absfilename, self._dir)
                    if loc == -1:
                        self._queue.put((self.send_file_hash_message, (absfilename, None)))
                    else:
                        dirs = absfilename[len(self._dir) + 1:-len(basename(absfilename))]
                        self._queue.put((self.send_file_hash_message, (absfilename, ), {"dirs":dirs}))
                else:
                    with file(absfilename) as f:
                        s = f.read()
                        self._callback(message=SimpleFileCarrier(absfilename, s))
                
            self._stop_event.wait(SLEEP_TIME)
            
    def send_file_hash_message(self, absfilename, dirs=None):
        roothash = get_hash(absfilename, self.swift_path)
        logger.debug("Determined roothash %s, for %s, with dirs %s", roothash, absfilename, dirs)
        self._callback(message=FileHashCarrier(absfilename, dirs, roothash, None))
            
    def stop(self):
        """
        Stop thread
        """
        self._stop_event.set()
        self._thread.join()
        self._threada.join()
            
    def _list_files_to_send(self):
        """
        Compare all files in _directory and _files, combined in file_updates with the current list _recent_files,
        which both hold tuples of filename and last modified time.
        
        @return: the difference between _recent_files and the file_updates
        """
        
        def recur(dir):
            all_files = [ join(dir,f) for f in listdir(dir) if isfile(join(dir,f)) and 
                         not (f.endswith(".mbinmap") or f.endswith(".mhash") or f.find("swifturl-") >= 0) ]
            all_dir = [join(dir, d) for d in listdir(dir) if isdir(join(dir, d))]
            for d in all_dir:
                all_files.extend(recur(d))
            return all_files
        
        all_files = []
        if self._dir: # Get all files in the directory and subdirectories
            all_files = recur(self._dir)
            
        if self._files:
            all_files.extend(self._files)
        file_updates = [ (f, getmtime(f)) for f in all_files] # create tuple of file and last modified timestamp
        
        diff = []
        for _ft in file_updates:
            file_exists = False
            for ft in self._recent_files:
                if ft[0] == _ft[0]: # Same file
                    file_exists = True
                    if ft[1] < _ft[1]: # Newer last modified time
                        diff.append(_ft[0])
            if not file_exists: # Each file in the directory should be send at least once
                diff.append(_ft[0])
                    
        self._recent_files = file_updates
        return diff
    
    
class CallFunctionThread(Thread):
    """
    Call function in separate thread. Arguments are unpacked.
    """
    def __init__(self, event, queue):
        Thread.__init__(self)
        self.event = event
        self.queue = queue
  
    def run(self):
        while not self.event.is_set():
            try:
                f, a, d = self.queue.get(True, 1)
                f(*a, **d)
                self.queue.task_done()
            except:
                pass
    