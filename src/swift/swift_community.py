'''
Created on Jan 7, 2014

@author: Vincent Ketelaars
'''
import binascii
from os import makedirs
from os.path import exists, basename, join
from sets import Set
from threading import Thread, Event

from Tribler.Core.Swift.SwiftDef import SwiftDef

from src.swift.swift_download_config import FakeSession, FakeSessionSwiftDownloadImpl
from src.download import Download, Peer
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
        self.peers = Set()
        self.downloads = {}
        
        self._thread_stop_event = Event()
        self._thread_loop = Thread(target=self._loop)
        self._thread_loop.daemon = True
        self._thread_loop.start()
        
    def add_file(self, filename, roothash, destination):
        logger.debug("Add file, %s %s", filename, roothash)        
        roothash = binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys() and len(roothash) == HASH_LENGTH / 2: # Check if not already added, and if the unhexlified roothash has the proper length
            logger.info("Add file %s with roothash %s", filename, binascii.hexlify(roothash))
            d = self.create_download_impl(roothash)
            d.set_dest_dir(filename)

            self.add_to_downloads(roothash, filename, d, seed=True, destination=destination) # Sharing so setting seed to True
            self.endpoint.swift_start(d)
            self.endpoint.swift_moreinfo(d, MOREINFO)
            self.endpoint.swift_pex(d, PEXON)
            
            self.add_new_peers()
            
    def add_peer(self, roothash, addr, sock_addr=None):
        logger.debug("Add peer %s with roothash %s to %s", addr, roothash, sock_addr)
        if self.endpoint.is_bootstrap_candidate(addr=addr):
            logger.debug("Add bootstrap candidate rejected")
            return
        d = self.endpoint.retrieve_download_impl(roothash)
        if d is not None:
            self.downloads[roothash].add_address(addr)
            # Only add this peer if it is one of the addresses allowed by the download
            if self.downloads[roothash].known_address(addr) and not self.downloads[roothash].is_bad_swarm():
                self.endpoint.swift_add_peer(d, addr, sock_addr)
        else: # Swift is not available at this time
            self.endpoint.enqueue_swift_queue(self.add_peer, roothash, addr, sock_addr)
            
    def clean_up_files(self, download):
        """
        Remove download from swift if it is not seeding. This method is only used once per download.
        Do checkpoint if not removing content or state. Notification via general callback.
        
        @param roothash: roothash to find the correct DownloadImpl
        @param rm_state: Remove state boolean
        @param rm_download: Remove download file boolean
        """
        if download.cleaned:
            return
        roothash = download.roothash
        rm_state = not download.seeder()
        rm_download = DELETE_CONTENT
        logger.debug("Clean up files, %s, %s, %s", roothash, rm_state, rm_download)        
        if download.downloadimpl is not None:
            if not rm_state or rm_download: # No point in doing checkpoint otherwise
                self.endpoint.swift_checkpoint(download.downloadimpl)
            # Do callback before removing, in case DELETE_CONTENT is True and someone wants to use it first
            self.do_callback(MESSAGE_KEY_RECEIVE_FILE, download.filename)
            if not download.seeder(): # If we close the download we cannot seed
                self.endpoint.swift_remove_download(download.downloadimpl, rm_state, rm_download)
            download.cleaned = True
        else: # Swift is not available at this time
            self.endpoint.enqueue_swift_queue(self.clean_up_file, download)
        # Note that the endpoint will still have the hash and peers in its added_peers
                
    def do_callback(self, key, *args, **kwargs):
        if self._api_callback is not None:
            self._api_callback(key, *args, **kwargs)
        
    def filehash_received(self, filename, directories, roothash, size, addresses, destination):
        """
        @param filename: The name the file will get
        @param directories: Optional path of directories within the destination directory
        @param roothash: hash to locate swarm
        @param size: Size of the file
        @param addresses: The sockets available to the peer that sent us this file
        @type destination: Destination.Implementation
        """
        logger.debug("Start download %s %s %s %d %s %s", filename, directories, roothash, size, self.dcomm.dest_dir, addresses)
        roothash=binascii.unhexlify(roothash) # Return the actual roothash, not the hexlified one. Depends on the return value of add_file
        if not roothash in self.downloads.keys():
            logger.info("Start download of %s with roothash %s", filename, roothash)
            dir_ = self.dcomm.dest_dir + "/" + directories
            if not exists(dir_):
                makedirs(dir_)
            d = self.create_download_impl(roothash)
            d.set_dest_dir(dir_ + basename(filename)) # File stored in dest_dir/directories/filename

            seed = not DELETE_CONTENT # Seed if not delete when done
            # Add download first, because it might take while before swift process returns
            self.add_to_downloads(roothash, d.get_dest_dir(), d, addresses=addresses, seed=seed, download=True, destination=destination)
            
            self.endpoint.swift_start(d)
            self.endpoint.swift_moreinfo(d, MOREINFO)
            self.endpoint.swift_pex(d, PEXON)          
            
            # TODO: Make sure that this peer is not added since the peer has already added us!                
            self.add_new_peers() # Notify our other peers that we have something new available!
            
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
                f = open(path, "w")
                f.write(contents)
                self.do_callback(MESSAGE_KEY_RECEIVE_FILE, filename)
            except:
                logger.exception("Can't write file")
            finally:
                try:
                    f.close()
                except:
                    pass
                
        t = Thread(target=create_file, name="create_" + filename)
        t.start()
        
    def peer_endpoints_received(self, messages):
        for x in messages:
            addresses = x.payload.addresses
            logger.debug("Peer's addresses arrived %s", addresses)
            for download in self.downloads.itervalues():
                # TODO: Protect against unreachable local addresses
                download.merge_peers(Peer(addresses))
            
        self.add_new_peers()
    
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
        logger.debug("Download is ready %s", binascii.hexlify(roothash))
        download = self.downloads[roothash]
        if download.set_finished() and not MOREINFO: # More info is not used so call clean up yourself
            self.clean_up_files(download)
                
    def moreinfo_callback(self, roothash):
        """
        This method is called whenever more info comes in.
        In case the download is finished and not supposed to seed, clean up the files
        
        @param roothash: The roothash to which the more info is related
        """
        logger.debug("More info %s", binascii.hexlify(roothash))
        download = self.downloads[roothash]
        download.got_moreinfo()
        self.do_callback(MESSAGE_KEY_SWIFT_INFO, {"direct" : download.package()}) # If more info is not set for the download this is never called
        if download.is_finished():
            self.clean_up_files(download)
            
    def bad_swarm_callback(self, roothash):
        logger.debug("We have a bad swarm %s", roothash)
        download = self.downloads.get(roothash, None)
        if download is not None:
            download.set_bad_swarm(True)
            self.do_callback(MESSAGE_KEY_BAD_SWARM, download.filename)
        else:
            logger.warning("We don't know this swarm %s", binascii.hexlify(roothash))
            
    def channel_closed_callback(self, roothash, socket_addr, peer_addr):
        logger.debug("Channel %s %s %s closed", binascii.hexlify(roothash), socket_addr, peer_addr)
        download = self.downloads.get(roothash, None)
        if download is not None:
            download.channel_closed(socket_addr, peer_addr)
            if not download.active():
                self.clean_up_files(download)
        else:
            logger.debug("Unknown swarm %s", binascii.hexlify(roothash))

    def add_to_downloads(self, roothash, filename, download_impl, addresses=None, seed=False, download=False, destination=None):
        """
        @param roothash: Binary form of the roothash of filename
        @param filename: Absolute path of filename
        @param donwload_impl: Download implementation as created in create_download_impl
        @param addresses: List of Address objects
        @param seed: Boolean that determines if this download should seed after finishing download
        @param download: Boolean that determines if this file needs to be downloaded
        @param add_known: Boolean that determines if all known peers should be added to this download
        """
        logger.debug("Add to known downloads, %s %s %s %s %s", binascii.hexlify(roothash), filename, addresses, seed, download)
        d = Download(roothash, filename, download_impl, seed=seed, download=download, moreinfo=MOREINFO, destination=destination)
        if addresses is not None: # We received this from someone else
            d.determine_seeding()
            self.peers.add(Peer(addresses))
        d.add_peers(self.peers)
        self.downloads[roothash] = d
        logger.debug("Download %s has %s as peers", filename, [str(a) for a in [asets for asets in [p.addresses for p in d.peers()]]])
        
    def put_endpoint_calls(self, q):
        for h, d in self.downloads.iteritems():
            if not d.is_bad_swarm() and (not d.is_finished() or d.seeder()): # No sense in adding a download that is finished, and not seeding
                logger.debug("Enqueue start download %s", h)
                q.put((self.endpoint.swift_start, (d.downloadimpl,), {}))
                q.put((self.endpoint.swift_moreinfo, (d.downloadimpl, MOREINFO), {}))
                for peer in self.downloads[h].peers():
                    for addr in peer.addresses:
                        logger.debug("Enqueue add peer %s %s", addr, h)
                        q.put((self.endpoint.swift_add_peer, (d.downloadimpl, addr, None), {}))
            
    def notify_filehash_peers(self, addresses):
        # We assume that endpoint only sends one file hash message to one peer,
        # so that each address actually belongs to a different peer
        logger.debug("File hash peers %s", addresses)
        for d in self.downloads.itervalues():
            for a in addresses:
                d.merge_peers(Peer([a]))
        # This would be the time to add peers (At this point the other side needs to do that)
        
    def add_new_peers(self, sock_addr=None):
        """
        For each download, its peers are added to Swift.
        The sock_addr option is there to allow for a single socket to disseminate this download.
        @param sock_addr: Address of local socket
        """
        logger.debug("Add new peers!")
        for roothash in self.downloads.keys():
            if self.downloads[roothash].seeder():
                for peer in self.downloads[roothash].peers():
                    for addr in peer.addresses:
                        self.add_peer(roothash, addr, sock_addr)
                        
    def get_download_by_file(self, file_):
        for d in self.downloads.itervalues():
            if d.filename == file_ or d.directories + PATH_SEPARATOR + d.filename == file_:
                return d
        return None
    
    def pause_download(self, download):
        if download is not None and not download.is_bad_swarm():
            self.endpoint.swift_checkpoint(download.downloadimpl)
            self.endpoint.swift_remove_download(download.downloadimpl, False, False)
            
    def continue_download(self, download):
        if download is not None and not download.is_bad_swarm():
            self.endpoint.swift_start(download.downloadimpl)
            self.endpoint.swift_moreinfo(download.downloadimpl, MOREINFO)
            self.endpoint.swift_pex(download.downloadimpl, PEXON)            
            self.add_new_peers()
            
    def stop_download(self, download):
        if download is not None and not download.is_bad_swarm():
            self.endpoint.swift_remove_download(download.downloadimpl, True, False)
            self.cleaned = True
                        
    def _loop(self):
        while not self._thread_stop_event.is_set():
            self.do_callback(MESSAGE_KEY_SWIFT_INFO, {"regular" : self._overal_data()})
            self._thread_stop_event.wait(REPORT_DISPERSY_INFO_TIME)
        
    def _overal_data(self):
        upspeed = 0
        downspeed = 0
        total_up = 0
        total_down = 0
        raw_total_up = 0
        raw_total_down = 0
        for d in self.downloads.itervalues():
            if not d.is_bad_swarm() and d.active():
                upspeed += d.speed("up")
                downspeed += d.speed("down")
                total_up += d.total("up")
                total_down += d.total("down")
                raw_total_up += d.total("up", raw=True)
                raw_total_down += d.total("down", raw=False)
        done_downloads = sum([d.is_finished() and d.is_download() and not d.is_bad_swarm() for d in self.downloads.itervalues()])
        num_seeding = sum([d.seeder() and not d.is_bad_swarm() for d in self.downloads.itervalues()])
        active_sockets = len(Set(s for d in self.downloads.itervalues() for s in d.active_sockets()))
        active_peers = len(Set(p for d in self.downloads.itervalues() for p in d.active_peers()))
        active_channels = len([c for d in self.downloads.itervalues() for c in d._active_channels])
        num_downloading = sum([d.seeder() and not d.is_finished() and not d.is_bad_swarm() for d in self.downloads.itervalues()])
        return {"up_speed" : upspeed, "down_speed" : downspeed, "total_up" : total_up, 
                "total_down" : total_down, "raw_total_up" : raw_total_up, "raw_total_down" : raw_total_down,
                "downloads" : len(self.downloads), "done_downloads" : done_downloads, 
                "seeders" : num_seeding, "downloading" : num_downloading, "active_peers" : active_peers,
                "active_sockets" : active_sockets, "active_channels" : active_channels}