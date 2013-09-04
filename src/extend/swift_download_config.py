'''
Created on Sep 3, 2013

@author: Vincent Ketelaars
'''

from Tribler.Core.DownloadConfig import DownloadStartupConfig, DownloadConfigInterface
from Tribler.Core.Swift.SwiftDownloadImpl import SwiftDownloadImpl
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.simpledefs import DLSTATUS_STOPPED

class SwiftDownloadConfig(DownloadStartupConfig):
        
    def get_def(self):
        return self._sdef
    
    def set_def(self, swift_def):
        self._sdef = swift_def
        
class FakeSession(object):
    
    def __init__(self):
        pass
    
    def get_swift_meta_dir(self):
        return None
        
class FakeSessionSwiftDownloadImpl(SwiftDownloadImpl):
    
    def __init__(self, session):
        SwiftDownloadImpl.__init__(self, session, SwiftDef())   
        
    def set_def(self, sdef):
        self.sdef = sdef
        
    def set_dest_dir(self, path):
        DownloadConfigInterface.set_dest_dir(self, path)
        
    def set_selected_files(self, files):
        DownloadConfigInterface.set_selected_files(self, files)
    
    def setup(self, dcfg=None, pstate=None, initialdlstatus=DLSTATUS_STOPPED, lm_network_engine_wrapper_created_callback=None, lm_network_vod_event_callback=None):
        # By setting initialstatus=DLSTATUS_STOPPED, no lm_network stuff will be created
        # We rely on the fact that a proper import is done for DownloadStartupConfig in this function
        SwiftDownloadImpl.setup(self, dcfg, pstate, initialdlstatus, lm_network_engine_wrapper_created_callback, lm_network_vod_event_callback)
