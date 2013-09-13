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
from src.definitions import SLEEP_TIME, MAX_FILE_SIZE, FILENAMES_NOT_TO_SEND, FILETYPES_NOT_TO_SEND

import logging
logger = logging.getLogger(__name__)

class FilePusher(object):
    '''
    FilePusher goes through a directory or a list of files to find either new files or updated files,
    and does a callback with the list of these files. It distinguishes between files larger and smaller than _file_size.
    In the former case the filename is send back, whereas in the latter case the contents of the file (string) is send back.
    '''

    def __init__(self, callback, swift_path, directory=None, files=[], file_size=MAX_FILE_SIZE):
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
        Start another thread that takes functions plus arguments and calls them
        """
        self._thread_loop = Thread(target=self._loop)
        self._thread_loop.daemon = True
        self._thread_loop.start()
        
        self._thread_func = CallFunctionThread(self._stop_event, self._queue)
        self._thread_func.daemon = True
        self._thread_func.start()
        
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
                    dirs = None
                    if loc != -1:
                        dirs = absfilename[len(self._dir) + 1:-len(basename(absfilename))]
                    self._queue.put((self.send_file_hash_message, (absfilename,), {"dirs":dirs}))
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
        self._thread_loop.join()
        self._thread_func.join()
            
    def _list_files_to_send(self):
        """
        Compare all files in _directory and _files, combined in file_updates with the current list _recent_files,
        which both hold tuples of filename and last modified time.
        
        @return: the difference between _recent_files and the file_updates
        """
        
        def recur(dir_):
            # all_files should only contain absolute filename paths in dir_
            all_files = [ join(dir_,f) for f in listdir(dir_) if isfile(join(dir_,f)) and 
                         # which do not end in any of the FILETYPES_NOT_TO_SEND or contain FILENAMES_NOT_TO_SEND
                         not (any(f.endswith(t) for t in FILETYPES_NOT_TO_SEND) or any(f.find(n) >= 0 for n in FILENAMES_NOT_TO_SEND)) ]
            all_dir = [join(dir_, d) for d in listdir(dir_) if isdir(join(dir_, d))]
            for d in all_dir:
                all_files.extend(recur(d))
            return all_files
        
        all_files = []
        if self._dir: # Get all files in the directory and subdirectories
            all_files = recur(self._dir)
            
        if self._files:
            all_files.extend(self._files)
        file_updates = [ (f, getmtime(f)) for f in all_files] # create tuple of file and last modified timestamp

        # Each file in the directory should be send at least once
        # If renewed they should be sent again  
        diff = [_ft[0] for _ft in file_updates if _ft not in self._recent_files]
                    
        self._recent_files = file_updates
        return diff
    
    
class CallFunctionThread(Thread):
    """
    Call function in separate thread. Arguments are unpacked.
    """
    def __init__(self, event, queue):
        """
        @param event: threading.Event, when set the thread will stop running
        @param queue: The queue can hold functions and their arguments as a tuple: (function, argument_tuple, argument_dict)
        """
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
    