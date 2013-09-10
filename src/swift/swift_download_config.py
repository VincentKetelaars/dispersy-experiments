'''
Created on Sep 3, 2013

@author: Vincent Ketelaars
'''

from Tribler.Core.DownloadConfig import DownloadStartupConfig, DownloadConfigInterface
from Tribler.Core.Swift.SwiftDownloadImpl import SwiftDownloadImpl
from Tribler.Core.Swift.SwiftDef import SwiftDef
from Tribler.Core.simpledefs import DLSTATUS_STOPPED, DLSTATUS_SEEDING

import logging
logger = logging.getLogger()

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
        self._download_ready_callback = None
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
    
    def set_download_ready_callback(self, callback):
        self._download_ready_callback = callback
        
    def i2ithread_info_callback(self, dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul):
        SwiftDownloadImpl.i2ithread_info_callback(self, dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul)
        if dlstatus == DLSTATUS_SEEDING and self._download_ready_callback is not None:
            self._download_ready_callback(self.get_def().get_roothash()) # Relies on the fact that currently the right SwiftDef is used!!!!
      
    def i2ithread_vod_event_callback(self, event, httpurl):
        SwiftDownloadImpl.i2ithread_vod_event_callback(self, event, httpurl)
