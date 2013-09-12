'''
Created on Sep 3, 2013

@author: Vincent Ketelaars
'''

import os
import binascii
import pickle

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
        
class FakeRawServer(object):
    
    def __init__(self):
        pass
    
    def add_task(self, get_state, delay):
        return None    
        
class FakeSwiftProcessMgr(object):
    
    def __init__(self):
        pass
    
    def release_sp(self, sp):
        return None
    
    def get_or_create_sp(self, a, b, c, d, e):
        return None
        
class FakeLaunchManyCore(object):
    
    def __init__(self):
        self.rawserver = FakeRawServer()
        self.spm = FakeSwiftProcessMgr()
        
    def network_engine_wrapper_created_callback(self, d, pstate):
        """ Called by network thread """
        try:
            if pstate is None:
                # Checkpoint at startup
                (infohash, pstate) = d.network_checkpoint()
                self.save_download_pstate(infohash, pstate)
        except:
            pass
        
    def save_download_pstate(self, infohash, pstate):
        """ Called by network thread """
        basename = binascii.hexlify(infohash) + '.pickle'
        filename = os.path.join(self.session.get_downloads_pstate_dir(), basename)

        f = open(filename, "wb")
        pickle.dump(pstate, f)
        f.close()

    def network_vod_event_callback(self, videoinfo, event, params):
        return None

class FakeUserCallBack(object):
    
    def __init__(self):
        pass
    
    def perform_vod_usercallback(self, downimpl, callback, event, params):
        return None
    
    def perform_getstate_usercallback(self, usercallback, ds, returncallback):
        return None
    
    def perform_removestate_callback(self, a, b, c):
        return None
        
class FakeSession(object):
    
    def __init__(self):
        self.lm = FakeLaunchManyCore()
        pass
    
    def get_swift_meta_dir(self):
        return None
    
    def get_swift_working_dir(self):
        return None
    
    def get_torrent_collecting_dir(self):
        return None
        
    
        
class FakeSessionSwiftDownloadImpl(SwiftDownloadImpl):
    
    def __init__(self, session, sdef, sp):
        self._download_ready_callback = None
        self._moreinfo_callback = None
        SwiftDownloadImpl.__init__(self, session, sdef)
        self.sp = sp
        
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
            
    def set_moreinfo_callback(self, callback):
        self._moreinfo_callback = callback
        
    def i2ithread_info_callback(self, dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul):
        SwiftDownloadImpl.i2ithread_info_callback(self, dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul)
        if dlstatus == DLSTATUS_SEEDING and self._download_ready_callback is not None:
            self._download_ready_callback(self.get_def().get_roothash())
    
    def i2ithread_moreinfo_callback(self, midict):
        SwiftDownloadImpl.i2ithread_moreinfo_callback(self, midict)
        self._moreinfo_callback(self.get_def().get_roothash())
      
    def i2ithread_vod_event_callback(self, event, httpurl):
        SwiftDownloadImpl.i2ithread_vod_event_callback(self, event, httpurl)
        
    def network_create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=None):
        SwiftDownloadImpl.network_create_engine_wrapper(self, lm_network_engine_wrapper_created_callback, pstate, lm_network_vod_event_callback, initialdlstatus=initialdlstatus)
        # If this is used, most likely self.sp will be None. 
        # self.sp.start_download(self)
