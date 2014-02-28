'''
Created on Jan 7, 2014

@author: Vincent Ketelaars
'''
import binascii
from os import makedirs
from os.path import exists, basename, join
from threading import Thread, Event

from src.swift.tribler.SwiftDef import SwiftDef
from src.swift.swift_download_config import FakeSession, FakeSessionSwiftDownloadImpl
from src.download import Download
from src.definitions import MESSAGE_KEY_RECEIVE_FILE, MESSAGE_KEY_SWIFT_INFO, HASH_LENGTH,\
    MOREINFO, DELETE_CONTENT, PEXON, REPORT_DISPERSY_INFO_TIME, PATH_SEPARATOR,\
    MESSAGE_KEY_BAD_SWARM
from src.logger import get_logger
logger = get_logger(__name__)

class SwiftCommunity(object):
    '''
    This class represents the bridge between the Dispersy Community and Libswift
    
    Needs mapping from Destination / Distribution to know who are allowed to receive a download.
    '''

    def __init__(self, dispersy_community, endpoint, api_callback=None):
        self.dcomm = dispersy_community
        self.endpoint = endpoint
        self._api_callback = api_callback
        self.downloads = {}
        
        self._thread_stop_event = Event()
        self._thread_loop = Thread(target=self._loop, name="SwiftCommunity_periodic_loop")
        self._thread_loop.setDaemon(True)
        self._thread_loop.start()
        
    def _swift_start(self, d, cid, moreinfo=MOREINFO, pexon=PEXON, func=None):
        if func is not None:
            func()
        # TODO: Swift start should also work with candidatedestination
        self.endpoint.swift_start(d, cid)
        self.endpoint.swift_moreinfo(d, moreinfo)
        self.endpoint.swift_pex(d, pexon)
        
    def add_file(self, filename, roothash, destination, size, timestamp, send_message):
        roothash = binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        # Check if not already added, and if the unhexlified roothash has the proper length
        if not roothash in self.downloads.keys() and len(roothash) == HASH_LENGTH / 2: 
            logger.info("Add file %s with roothash %s of size %d with timestamp %f", filename, binascii.hexlify(roothash), size, timestamp)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(filename)

            # Sharing so setting seed to True
            download = self.add_to_downloads(roothash, filename, d, size, timestamp, seed=True, destination=destination) 
            if download.community_destination():
                self.endpoint.put_swift_upload_stack(self._swift_start, size, timestamp, priority=0, args=(d, self.dcomm.cid), 
                                                     kwargs={"func" : send_message})
                download.stacked()
            
    def clean_up_download(self, download):
        """
        Remove download from swift if it is not seeding. This method is only used once per download.
        Do checkpoint if not removing content or state. Notification via general callback.
        
        @param roothash: roothash to find the correct DownloadImpl
        @param rm_state: Remove state boolean
        @param rm_download: Remove download file boolean
        """
        if not download.running_on_swift():
            return
        rm_state = not download.seeder()
        rm_download = DELETE_CONTENT
        # No point in doing checkpoint if not both false, and if we've already done it for the entire thing   
        if not rm_state and not rm_download and not download.downloadimpl.checkpoint_done():
            logger.debug("Create checkpoint for %s %s %s", download.roothash_as_hex(), rm_state, rm_download)
            self.endpoint.swift_checkpoint(download.downloadimpl)
        # Do callback before removing, in case DELETE_CONTENT is True and someone wants to use it first
        self.do_callback(MESSAGE_KEY_RECEIVE_FILE, download.filename)
        if not download.seeder(): # If we close the download we cannot seed
            logger.debug("Clean up download, %s, %s, %s", download.roothash_as_hex(), rm_state, rm_download)
            self.endpoint.swift_remove_download(download.downloadimpl, rm_state, rm_download)
                
    def do_callback(self, key, *args, **kwargs):
        if self._api_callback is not None:
            self._api_callback(key, *args, **kwargs)
        
    def filehash_received(self, filename, directories, roothash_hex, size, timestamp, destination, priority=0):
        """
        @param filename: The name the file will get
        @param directories: Optional path of directories within the destination directory
        @param roothash: hash to locate swarm
        @param size: Size of the file
        @type destination: Destination.Implementation
        """
        roothash=binascii.unhexlify(roothash_hex) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys():
            logger.debug("Start download %s %s %s %d %f %s", filename, directories, roothash_hex, size, timestamp, self.dcomm.dest_dir)
            dir_ = self.dcomm.dest_dir + "/" + directories
            if not exists(dir_):
                makedirs(dir_)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(dir_ + basename(filename)) # File stored in dest_dir/directories/filename

            seed = not DELETE_CONTENT # Seed if not delete when done
            # Add download first, because it might take while before swift process returns
            download = self.add_to_downloads(roothash, d.get_dest_dir(), d, size, timestamp,
                                  seed=seed, download=True, destination=destination, priority=priority)
            if download.community_destination():
                self.endpoint.put_swift_download_stack(self._swift_start, size, timestamp, priority=priority, args=(d, self.dcomm.cid))
            
            
    def file_received(self, filename, contents):
        """
        Received small file. Create this file in the current directory.
        
        @param filename: filename
        @param contents: Contents of the file
        """
        logger.debug("Received file %s", filename)
        def create_file():
            try:
                path = join(self.dcomm.dest_dir, filename)
                with open(path, "w") as f:
                    f.write(contents)
                self.do_callback(MESSAGE_KEY_RECEIVE_FILE, filename)
            except IOError:
                logger.exception("Can't write to %s", path)
                
        t = Thread(target=create_file, name="create_" + filename)
        t.start()
    
    def create_download_impl(self, roothash):
        """
        Create DownloadImpl
        
        @param roothash: Roothash of a file
        """
        logger.debug("Create download implementation, %s", roothash)
        sdef = SwiftDef(roothash=roothash)
        # This object must have: get_def, get_selected_files, get_max_speed, get_swift_meta_dir
        d = FakeSessionSwiftDownloadImpl(FakeSession(), sdef, self.endpoint.swift)
        d.setup()
        # get_selected_files is initialized to empty list
        # get_max_speed for UPLOAD and DOWNLOAD are set to 0 initially (infinite)
        d.set_swift_meta_dir(None)
        d.set_download_ready_callback(self.download_is_ready_callback)
        d.set_moreinfo_callback(self.moreinfo_callback)
        d.set_bad_swarm_callback(self.bad_swarm_callback)
        d.set_channel_closed_callback(self.channel_closed_callback)
        return d    
        
    def download_is_ready_callback(self, roothash):
        """
        This method is called when a download is ready
        
        @param roothash: Identifier of the download
        """
        download = self.downloads[roothash]
        if download.set_finished() and download.is_download() and not MOREINFO: # More info is not used so call clean up yourself
            logger.debug("Download is ready %s", binascii.hexlify(roothash))
            self.clean_up_download(download)
                
    def moreinfo_callback(self, roothash):
        """
        This method is called whenever more info comes in.
        In case the download is finished and not supposed to seed, clean up the files
        
        @param roothash: The roothash to which the more info is related
        """
        download = self.downloads[roothash]
        download.got_moreinfo()
        self.do_callback(MESSAGE_KEY_SWIFT_INFO, {"direct" : download.package()}) # If more info is not set for the download this is never called
        if download.is_finished() and download.is_download():
            self.clean_up_download(download)
            
    def bad_swarm_callback(self, roothash):
        logger.debug("We have a bad swarm %s", roothash)
        download = self.downloads.get(roothash, None)
        if download is not None:
            self.do_callback(MESSAGE_KEY_BAD_SWARM, download.filename)
        else:
            logger.warning("We don't know this swarm %s", binascii.hexlify(roothash))
            
    def channel_closed_callback(self, roothash, socket_addr, peer_addr):
        logger.debug("Channel %s %s %s closed", binascii.hexlify(roothash), socket_addr, peer_addr)
        download = self.downloads.get(roothash, None)
        if download is not None:
            download.channel_closed(socket_addr, peer_addr)
            if not download.active():
                self.clean_up_download(download)
        else:
            logger.debug("Unknown swarm %s", binascii.hexlify(roothash))

    def add_to_downloads(self, roothash, filename, download_impl, size, timestamp, seed=False, download=False, 
                         destination=None, priority=0):
        """
        @param roothash: Binary form of the roothash of filename
        @param filename: Absolute path of filename
        @param download_impl: Download implementation as created in create_download_impl
        @param size: Size of the file
        @param timestamp: Timestamp (Creation / modification) of the file
        @param seed: Boolean that determines if this download should seed after finishing download
        @param download: Boolean that determines if this file needs to be downloaded
        @param add_known: Boolean that determines if all known peers should be added to this download
        @return: Download
        """
        logger.debug("Add to known downloads, %s %s %d %f %s %s", binascii.hexlify(roothash), filename, size, timestamp, 
                     seed, download)
        d = Download(roothash, filename, download_impl, size, timestamp, self.dcomm.cid, seed=seed, download=download, 
                     moreinfo=MOREINFO, destination=destination, priority=priority)
        self.downloads[roothash] = d
        return d
        
    def put_endpoint_calls(self, q, roothashes):
        """
        Request from SwiftHandler to restart downloads
        Enqueue those calls in q
        @param q: Queue
        @param roothashes: List of roothashes that represent downloads that were running at the time of failure
        """
        for h in roothashes:
            d = self.downloads.get(h)
            if d is not None and not d.is_bad_swarm() and d.has_peer() and (not d.is_finished() or d.seeder()): # No sense in adding a download that is finished, and not seeding
                logger.debug("Enqueue start download %s", h)
                if d.community_destination():
                    q.put((self._swift_start, (d.downloadimpl, self.dcomm.cid), {}))
                        
    def get_download_by_file(self, file_):
        for d in self.downloads.itervalues():
            if d.filename == file_ or d.directories + PATH_SEPARATOR + d.filename == file_:
                return d
        return None
    
    def pause_download(self, download):
        if download is not None and download.running_on_swift():
            if download.is_download():
                self.endpoint.swift_checkpoint(download.downloadimpl)
            self.endpoint.swift_remove_download(download.downloadimpl, False, False)
            
    def continue_download(self, download):
        if download is not None and not download.is_bad_swarm():
            if download.community_destination():
                self._swift_start(download.downloadimpl, self.dcomm.cid)
            
    def stop_download(self, download):
        if download is not None and download.running_on_swift():
            self.endpoint.swift_remove_download(download.downloadimpl, True, False)
                        
    def _loop(self):
        while not self._thread_stop_event.is_set():
            self.do_callback(MESSAGE_KEY_SWIFT_INFO, {"regular" : self._overal_data()})
            for download in self.downloads.itervalues():
                if not download.is_finished() and not download.running_on_swift() and not download.on_stack() and not download.is_bad_swarm():
                    self.endpoint.put_swift_download_stack(self._swift_start, download.size, download.timestamp, 
                                                           priority=download.priority, args=(download.downloadimpl, self.dcomm.cid))
                    download.stacked()
            self._thread_stop_event.wait(REPORT_DISPERSY_INFO_TIME)
            
    def unload_community(self):
        self._thread_stop_event.set()
        self._thread_loop.join()
        return True
        
    def _overal_data(self):
        upspeed = 0
        downspeed = 0
        total_up = 0
        total_down = 0
        raw_total_up = 0
        raw_total_down = 0
        for d in self.downloads.itervalues():
            if d.has_started():
                upspeed += d.downloadimpl.speed("up")
                downspeed += d.downloadimpl.speed("down")
                total_up += d.downloadimpl.total("up")
                total_down += d.downloadimpl.total("down")
                raw_total_up += d.downloadimpl.total("up", raw=True)
                raw_total_down += d.downloadimpl.total("down", raw=False)
        done_downloads = sum([d.is_finished() and d.is_download() and not d.is_bad_swarm() for d in self.downloads.itervalues()])
        num_seeding = sum([d.seeder() and not d.running_on_swift() for d in self.downloads.itervalues()])
        active_sockets = len(set(s for d in self.downloads.itervalues() for s in d.active_sockets()))
        active_addresses = set(a for d in self.downloads.itervalues() for a in d.active_addresses())
        active_peers = len([p for p in self.endpoint.peers(self.dcomm.cid) if p.has_any(active_addresses)])
        active_channels = len([c for d in self.downloads.itervalues() for c in d._active_channels])
        num_downloading = sum([d.seeder() and not d.is_finished() and not d.running_on_swift() for d in self.downloads.itervalues()])
        return {"up_speed" : upspeed, "down_speed" : downspeed, "total_up" : total_up, 
                "total_down" : total_down, "raw_total_up" : raw_total_up, "raw_total_down" : raw_total_down,
                "downloads" : len(self.downloads), "done_downloads" : done_downloads, 
                "seeders" : num_seeding, "downloading" : num_downloading, "active_peers" : active_peers,
                "active_sockets" : active_sockets, "active_channels" : active_channels}