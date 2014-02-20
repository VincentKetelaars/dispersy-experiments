'''
Created on Sep 3, 2013

@author: Vincent Ketelaars
'''

import os
import binascii
import pickle
from datetime import datetime, timedelta

from src.logger import get_logger
from src.swift.tribler.DownloadConfig import DownloadStartupConfig, DownloadConfigInterface
from src.swift.tribler.SwiftDownloadImpl import SwiftDownloadImpl
from src.swift.tribler.simpledefs import DLSTATUS_STOPPED, DLSTATUS_SEEDING,\
    DLSTATUS_DOWNLOADING, DLSTATUS_WAITING4HASHCHECK
from src.definitions import MAX_SWARM_LIFE_WITHOUT_LEECHERS

logger = get_logger(__name__)

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
            logger.exception("What kind of exception can you throw?")
        
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
        self._bad_swarm_callback = None
        self._channel_closed_callback = None
        SwiftDownloadImpl.__init__(self, session, sdef)
        self.sp = sp
        self._last_leecher_time = datetime.utcnow()
        self._bad_swarm = False
        self._final_checkpoint = datetime.min # We own every bit of it
        
    @property
    def bad_swarm(self):
        return self._bad_swarm
        
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
        
    def set_bad_swarm_callback(self, callback):
        self._bad_swarm_callback = callback
        
    def set_channel_closed_callback(self, callback):
        self._channel_closed_callback = callback
        
    def i2ithread_info_callback(self, dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul):
        SwiftDownloadImpl.i2ithread_info_callback(self, dlstatus, progress, dynasize, dlspeed, ulspeed, numleech, numseeds, contentdl, contentul)
        self._update_leeching(numleech)
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
        
    def set_bad_swarm(self):
        self._bad_swarm = True
        if self._bad_swarm_callback is not None:
            self._bad_swarm_callback(self.get_def().get_roothash_as_hex())
        
    def _update_leeching(self, numleech):
        if numleech > 0:
            self._last_leecher_time = datetime.utcnow()
        
    def speed(self, direction):
        try:
            return self.get_current_speed(direction)
        except KeyError:
            logger.debug("Could not fetch speed %s", direction)
            return 0
    
    def total(self, direction, raw=False):
        try:
            return self.midict[("raw_" if raw else "") + "bytes_" + direction] / 1024.0
        except KeyError:
            logger.debug("Could not fetch total %s %s", direction, raw)
            return 0
        
    def initialized(self):
        return self.get_status() == DLSTATUS_WAITING4HASHCHECK
        
    def downloading(self):
        return self.get_status() == DLSTATUS_DOWNLOADING
        
    def seeding(self):
        return self.get_status() == DLSTATUS_SEEDING
    
    def checkpointing(self):
        if self.seeding():
            self._final_checkpoint = datetime.utcnow()
            
    def checkpoint_done(self):
        return self._final_checkpoint != datetime.min
    
    def dropped_packets_rate(self):
        # TODO: Implement this!!!
        return 0.0
    
    def is_usefull(self):
        return self._last_leecher_time + timedelta(seconds=MAX_SWARM_LIFE_WITHOUT_LEECHERS) > datetime.utcnow()
        
    def network_create_spew_from_channels(self):
        if not 'channels' in self.midict:
            return ([], None)

        plist = []
        channels = self.midict['channels']
        for channel in channels:
            d = {}
            d['ip'] = channel['ip']
            d['port'] = channel['port']
            d['sock_ip'] = channel['socket_ip']
            d['sock_port'] = channel['socket_port']
            d['total_up'] = channel['bytes_up'] / 1024.0
            d['total_down'] = channel['bytes_down'] / 1024.0
            d['raw_total_up'] = channel['raw_bytes_up'] / 1024.0
            d['raw_total_down'] = channel['raw_bytes_down'] / 1024.0
            d['current_speed_up'] = channel["cur_speed_up"] / 1024.0
            d['current_speed_down'] = channel["cur_speed_down"] / 1024.0
            d['send_buffer'] = channel["send_queue"]
            d['average_rtt'] = channel["avg_rtt"]
            plist.append(d)
        
        total = {'timestamp' : self.midict['timestamp'], 'raw_total_up' : self.midict['raw_bytes_up'] / 1024.0, 
                 'raw_total_down' : self.midict['raw_bytes_down'] / 1024.0, 'total_up' : self.midict['bytes_up'] / 1024.0,
                 'total_down' : self.midict['bytes_down'] / 1024.0}        

        return (plist, total)
    
    def __hash__(self):
        return self.get_def().get_roothash()
