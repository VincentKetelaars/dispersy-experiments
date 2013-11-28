'''
Created on Oct 16, 2013

@author: Vincent Ketelaars
'''

import socket
import struct
import argparse
import select

from src.tools.runner import CallFunctionThread, Event

from src.logger import get_logger

logger = get_logger(__name__)

class MultiCast(object):
    '''
    This class will allow to send and receive UDP multicast
    '''

    def __init__(self, group, port, receive):
        self.group = group
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.thread = None
        self.event = None
        
        if receive:
            self.set_receive()
            self._receiving = True
        else:
            self.set_send()
            self._ready_to_send = True            
    
    def set_receive(self):
        logger.debug("Set receive on %s", self.group)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.port))
        mreq = struct.pack("!4sl", socket.inet_aton(self.group), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        self.thread = CallFunctionThread(timeout=1.0)
        self.thread.start()
        self.event = Event()
        self.thread.put(self._receive)
          
    def _receive(self):
        logger.debug("Start receive on %s", self.sock.getsockname())        
        while not self.event.is_set():
            # Select can be used for timeout (import select)
            ret = select.select([self.sock], [], [], 0.1)
            if ret[0]:
                message = self.sock.recv(4096) # Small power of 2 for optimal performance
                logger.info("Received %s", message)
    
    def set_send(self):
        logger.debug("Set send")
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1) # Time to live, 1 for local network..
        
    def send(self, message):
        if self.ready_to_send:    
            logger.debug("Send %s to %s", message, self.group)
            self.sock.sendto(message, (self.group, self.port))
    
    @property
    def receiving(self):
        return self._receiving
    
    @property
    def ready_to_send(self):
        return self._ready_to_send
    
    def stop(self):
        logger.debug("Stop")
        # This is apparently not sufficient to stop the thread with daemon=False
        if self.event:
            self.event.set()
        self.sock.close()
        if self.thread:
            self.thread.stop()
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Multicast')
    parser.add_argument("-a", "--action", default="receive", help="send, receive or both")
    parser.add_argument("-g", "--group", default="224.3.0.1", help="group")
    parser.add_argument("-m", "--message", default="", help="Message to send")
    parser.add_argument("-p", "--port", default=54321, help="port")
    parser.add_argument("-t", "--time", default=1, help="time to listen")
    args = parser.parse_args()
    
    multicast = None 
    multicast_recv = None
    if args.action == "receive":
        multicast = MultiCast(args.group, args.port, True)
    elif args.action == "send":
        multicast = MultiCast(args.group, args.port, False)
    elif args.action == "both":
        multicast_recv = MultiCast(args.group, args.port, True)
        Event().wait(0.1)
        multicast = MultiCast(args.group, args.port, False)
    else:
        quit("Not a valid action!")
        
    if args.message and multicast.ready_to_send:
        message = "".join(args.message)
        multicast.send(message)
    
    if multicast_recv:
        Event().wait(args.time)
        multicast_recv.stop()