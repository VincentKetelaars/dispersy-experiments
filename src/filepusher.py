'''
Created on Aug 30, 2013

@author: Vincent Ketelaars
'''

from threading import Thread, Event
from datetime import datetime
from string import find
from os import listdir
from os.path import exists, isfile, isdir, getmtime, join, getsize, basename, abspath

from src.logger import get_logger
from src.tools.runner import CallFunctionThread
from src.dispersy_extends.payload import SmallFileCarrier, FileHashCarrier
from src.dispersy_extends.endpoint import get_hash
from src.definitions import SLEEP_TIME, MAX_MESSAGE_SIZE, FILENAMES_NOT_TO_SEND, FILETYPES_NOT_TO_SEND

logger = get_logger(__name__)

class FilePusher(Thread):
    '''
    FilePusher goes through a directory or a list of files to find either new files or updated files,
    and does a callback with the list of these files. It distinguishes between files larger and smaller than _file_size.
    In the former case the filename is send back, whereas in the latter case the contents of the file (string) is send back.
    '''

    def __init__(self, callback, swift_path, directories=[], files=[], file_size=MAX_MESSAGE_SIZE, hidden=False, min_timestamp=None):
        '''
        @param callback: The function that will be called with a FileHashCarrier or SimpleFileCarrier object
        @param swift_path: Path to swift executable
        @param directory: The directory to search for files
        @param files: The list of files to monitor
        @param file_size: The decision variable for choosing callback object
        @param hidden: List hidden downloads as well
        @param min_timestamp: Oldest modification time to use for new files
        '''
        Thread.__init__(self, name="Filepusher")
        self.setDaemon(True)
        self._dirs = set()
        for d in directories:
            self.add_directory(d)
        
        self._files = set()
        self.add_files(files)
                
        self._recent_files = []
        self._callback = callback
        self._file_size = file_size
        self.swift_path = swift_path
        self._hidden = hidden
        self._min_timestamp = datetime.fromtimestamp(min_timestamp) if min_timestamp is not None else datetime.min
        
        self._stop_event = Event()
        self._thread_func = CallFunctionThread(timeout=1.0, name="Filepusher")
        self._paused = False
        
    def add_directory(self, directory):
        if directory and exists(directory) and isdir(directory):
            self._dirs.add(abspath(directory)) # Add only absolute paths, no ambiguities
        
    def add_files(self, files):
        for f in files:
            if exists(f) and isfile(f):
                self._files.add(f)

    def run(self):
        """
        Run until _stop_event is set. 
        Determine list of files that have are new or have changed since previous iteration.
        Call _callback with each of these files.
        """        
        self._thread_func.start()
        
        while not self._stop_event.is_set():                            
            diff = self._list_files_to_send()
            for absfilename in diff:
                if datetime.fromtimestamp(getmtime(absfilename)) < self._min_timestamp:
                    continue # Only go for files that are older than self._min_timestamp
                logger.debug("New file to be sent: %s", absfilename)
                if getsize(absfilename) > self._file_size:
                    self._thread_func.put(self.send_file_hash_message, absfilename, dirs=self._get_dir(absfilename), 
                                          queue_priority=getmtime(absfilename))
                else:
                    with file(absfilename) as f:
                        s = f.read()
                        self._callback(message=SmallFileCarrier(absfilename, s))
                
            self._stop_event.wait(SLEEP_TIME)
            
    def _get_dir(self, absfilename):
        """
        Find the longest path in the available directories.
        Return None if no found. 
        @param absfilename: The absolute path to the filename
        """
        longest = "" # Longest directory path
        for d in self._dirs:
            if d in absfilename and len(longest) < len(d):
                longest = d
        if len(longest): # Not length 0
            return absfilename[len(longest) + 1:-len(basename(absfilename))]
        return None
            
    def send_file_hash_message(self, absfilename, dirs=None):
        roothash = get_hash(absfilename, self.swift_path)
        size = getsize(absfilename)
        modified = getmtime(absfilename)
        logger.debug("Determined roothash %s, for %s, with dirs %s of size %d at time %f", 
                     roothash, absfilename, dirs, size, modified)
        self._callback(message=FileHashCarrier(absfilename, dirs, roothash, size, modified, None))
        
    def pause(self):
        if not self._paused:
            self._thread_func.pause()
            self._paused = True
            logger.info("Paused")
        
    def unpause(self):
        if self._paused:
            self._thread_func.unpause()
            self._paused = False
            logger.info("Unpaused")
    
    @property        
    def paused(self):
        return self._paused
            
    def stop(self):
        """
        Stop thread
        """
        self._stop_event.set()
        self._thread_func.stop()
            
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
                         not (any(f.endswith(t) for t in FILETYPES_NOT_TO_SEND) 
                              or any(f.find(n) >= 0 for n in FILENAMES_NOT_TO_SEND)) and
                        # which if not hidden, do no start with a dot
                         not (not self._hidden and f[0] == ".") ]
                        
            all_dir = [join(dir_, d) for d in listdir(dir_) if isdir(join(dir_, d)) and 
                       # If not hidden, don't go into directories starting with a dot
                       not (not self._hidden and d[0] == ".") ]
            for d in all_dir:
                all_files.extend(recur(d))
            return all_files
        
        # Get all files in the directory and subdirectories
        all_files = set([f for d in self._dirs for f in recur(d)])
        all_files.update(self._files)
        file_updates = [ (f, getmtime(f)) for f in all_files] # create tuple of file and last modified timestamp

        # Each file in the directory should be send at least once
        # If renewed they should be sent again
        diff = [_ft[0] for _ft in file_updates if _ft not in self._recent_files]
        
        self._recent_files = file_updates
        return diff
    