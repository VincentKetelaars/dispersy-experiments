'''
Created on Aug 30, 2013

@author: Vincent Ketelaars
'''

import time

from os import listdir
from os.path import exists, isfile, isdir, getmtime, join

from src.extend.payload import SimpleFileCarrier, FileHashCarrier

import logging
logger = logging.getLogger()

UPDATE_TIME = 1 # Seconds

class FilePusher(object):
    '''
    classdocs
    '''

    def __init__(self, conn, directory=None, files=[]):
        '''
        Constructor
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
        
        self._conn = conn
        
        self._recent_files = []
        
    def run(self):
        self._loop()
        
    def _loop(self):
        _continue = True
        while _continue:
            if self._conn.poll():
                _continue = self._conn.recv()
                if not _continue:
                    break
                
            diff = self._list_files_to_send()
            for absfilename in diff:
                with file(absfilename) as f:
                    s = f.read()
                    if len(s) > 2**16-60:
                        self._conn.send(FileHashCarrier(absfilename, None, None))
                    else:
                        self._conn.send(SimpleFileCarrier(absfilename, s))
                       
            time.sleep(UPDATE_TIME)
            
    def _list_files_to_send(self):
        all_files = []    
        if self._dir: # Get all files in the directory
            all_files = [ join(self._dir,f) for f in listdir(self._dir) if isfile(join(self._dir,f)) and 
                         not (f.endswith(".mbinmap") or f.endswith(".mhash")) ]
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
    
    