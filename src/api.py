'''
Created on Nov 15, 2013

@author: Vincent Ketelaars
'''
import os
import Queue
import socket
import signal
from threading import Thread, Event
from multiprocessing import Process, Pipe

from src.logger import get_logger
from src.dispersy_instance import DispersyInstance
from src.address import Address
from src.definitions import STATE_NOT, STATE_RUNNING, MESSAGE_KEY_ADD_FILE, MESSAGE_KEY_ADD_MESSAGE, MESSAGE_KEY_ADD_PEER, \
MESSAGE_KEY_ADD_SOCKET, MESSAGE_KEY_INTERFACE_UP, MESSAGE_KEY_MONITOR_DIRECTORY, MESSAGE_KEY_RECEIVE_FILE, \
MESSAGE_KEY_API_MESSAGE, MESSAGE_KEY_STATE, MESSAGE_KEY_STOP, STATE_DONE,\
    MESSAGE_KEY_SWIFT_STATE, MESSAGE_KEY_SOCKET_STATE, MESSAGE_KEY_SWIFT_PID,\
    MESSAGE_KEY_SWIFT_INFO, MESSAGE_KEY_DISPERSY_INFO, MESSAGE_KEY_BAD_SWARM

from src.tools.runner import CallFunctionThread
from src.dispersy_extends.payload import APIMessageCarrier
logger = get_logger(__name__)

class PipeHandler(object):
    """
    This PipeHandler handles one end of a Pipe connection. 
    Both receiving and and sending are done in separate threads.
    This will not start until is_alive_event has been set.
    The Message Key Map allows child classes to define callback functions for specific Message Keys,
    which they can also define.
    When the other end of the connection is gone, _connection_process_gone() will be called, 
    which therefore needs to be implemented by all subclasses
    """
    
    # This dictionary needs to be overwritten for the messages to be handled
    # It should hold a MESSAGE_KEY_* as key and a function as value
    MESSAGE_KEY_MAP = {} 
    
        
    def __init__(self, connection, name=""):
        self.conn = connection
        self.name = name  
        
        # Receive from pipe
        self.stop_receiving_event = Event()
        self.is_alive_event = Event() # Wait until subclass tells you it is ready
        
        self._receiver = Thread(target=self.wait_on_recv, name=name + "_receiver")
        self._receiver.start()
        
        # Start send thread
        self.sender = CallFunctionThread(timeout=1.0, name=name + "_sender")
        self.sender.start()
        
    def close_connection(self):
        self.stop_receiving_event.set()
        self.sender.stop(wait_for_tasks=True, timeout=1.0) # Wait at most timeout till queue is empty
        self.conn.close()
        logger.debug("Connection closed for %s", self.name)
    
    def wait_on_recv(self):
        """
        Listen to pipe for incoming messages, which are dispatched to handle_message
        """
        while not self.stop_receiving_event.is_set():
            self.is_alive_event.wait()
            message = None
            try:
                message = self.conn.recv() # Blocking
            except EOFError: # Other end is dead
                logger.exception("Connection with process is gone for %s", self.name)
                self._connection_process_gone() # Should be implemented!!
            except:
                logger.exception("Could not receive message over pipe for %s", self.name)
            self.handle_message(message)
            
    def send_message(self, key, *args, **kwargs):
        """
        Send message via pipe to parent process
        
        @param key: MESSAGE_KEY
        """
        
        def send():
            self.is_alive_event.wait()
            try:
                self.conn.send((key, args, kwargs))
            except:
                logger.exception("%s failed to send %s %s %s", self.name, key, args, kwargs)
        
        self.sender.put(send)
        
    def handle_message(self, message):
        """
        Handles an incoming message. Relies on MESSAGE_KEY_MAP to hold the specified key.
        If the key is available, an attempt to call the function it points to is made,
        with the arguments provided.
        
        @param message: (KEY, ARGS, KWARGS)
        """
        if not message:
            return
        try:
            func = self.MESSAGE_KEY_MAP[message[0]]
            func(*message[1], **message[2])
        except:
            logger.exception("%s failed to dispatch incoming message %d %s %s", self.name, message[0], message[1], message[2])
            
    def _connection_process_gone(self):
        raise NotImplementedError()

class API(Thread, PipeHandler):
    '''
    API serves as the main vehicle for starting a DispersyInstance process. 
    It can send commands and receive feedback via a pipe connection.
    '''

    def __init__(self, name, *di_args, **di_kwargs):
        Thread.__init__(self, name=name)
        self.setDaemon(True)  # Automatically die when the main thread dies
        self._state = STATE_NOT
        parent_conn, self.child_conn = Pipe()
        
        self.MESSAGE_KEY_MAP = {MESSAGE_KEY_STOP : self._api_stop,
                                MESSAGE_KEY_STATE : self._state_change,
                                MESSAGE_KEY_RECEIVE_FILE : self.file_received_callback,
                                MESSAGE_KEY_API_MESSAGE : self.message_received_callback,
                                MESSAGE_KEY_SWIFT_STATE : self._swift_state,
                                MESSAGE_KEY_SOCKET_STATE : self.socket_state_callback,
                                MESSAGE_KEY_SWIFT_PID : self._swift_pid,
                                MESSAGE_KEY_SWIFT_INFO : self.swift_info_callback,
                                MESSAGE_KEY_DISPERSY_INFO : self.dispersy_info_callback,
                                MESSAGE_KEY_BAD_SWARM : self.bad_swarm_callback}
        PipeHandler.__init__(self, parent_conn, name=name)

        self.receiver_api = Process(target=ReceiverAPI, args=(self.child_conn,) + di_args, kwargs=di_kwargs)

        
        # Callbacks
        self._callback_state_change = None
        self._callback_swift_state = None
        
        # Any child class that wants to stop when Dispersy stops should implement stop and set this to True
        self.stop_on_dispersy_stop = False
        self._children_recur = [] # process id of every child, grandchild, etc.
        
    def start(self):
        self.receiver_api.start()
        self.child_conn.close() # This makes sure that it doesn't assume API might use this end, child can still use it
        self._children_recur.append(self.receiver_api.pid)
        self.is_alive_event.set()
        Thread.start(self)
        
    def run(self):
        logger.debug("Implement that shit!")
        
    def stop(self):
        """
        API call that will tell Dispersy to stop, if necessary
        """
        logger.info("In state %d. Stop self and children %s", self._state, self._children_recur)               
        if self._state == STATE_RUNNING: # Tell Dispersy to stop
            self.send_message(MESSAGE_KEY_STOP)
        # TODO: If something goes wrong, we should still make sure that everything is stopped
        else:
            self._api_stop()
        
    def _api_stop(self):
        # TODO: Make sure that you told the child process to stop before you sever the connection
        # wait_on_receive will block unless this is set (Is already set in case process was started)
        if not self.is_alive_event.is_set(): # Haven't actually started anything
            self.is_alive_event.set()
        self.close_connection()
        self.finish()
        
    def finish(self):
        """
        Finish call that will ensure that the child (and its child) process is killed.
        """
        logger.debug("Joining %s", self._children_recur[0] if self._children_recur else "child")
        try:
            self.receiver_api.join(1) # If the process hasn't started, you cannot join it
        except:
            pass
        
        # join should timeout after 1 second if necessary (should be plenty enough time for normal join)
        had_to_kill = False;
        for pid in self._children_recur: # Go through the processes.. (i.e. probably start with the oldest, in case they respawn killed processes)
            try:
                os.kill(pid, signal.SIGKILL) # Kill child process
                had_to_kill = True
                logger.debug("Had to kill process %d", pid)
            except:
                pass
        
        if had_to_kill: # In case a hard kill was necessary we have to try and join again
            try:
                self.receiver_api.join(1) # Try joining again
            except:
                pass
        logger.debug("finished %s", self._children_recur[0])
    
    @property
    def state(self):
        return self._state
    
    def _connection_process_gone(self):
        self.finish()
    
    def on_dispersy_stopped(self):
        raise NotImplementedError()
            
    """
    SUBSCRIBE TO CALLBACKS
    """
        
    def state_change_callback(self, callback):
        self._callback_state_change = callback
        
    def swift_state_callback(self, callback):
        self._callback_swift_state = callback
        
    """
    OVERWRITE CALLBACKS
    """           
                    
    def socket_state_callback(self, address, state):
        pass
        
    def swift_info_callback(self, download):
        pass
    
    def dispersy_info_callback(self, info):
        pass    
    
    def file_received_callback(self, file_):
        pass
        
    def message_received_callback(self, message):
        pass
    
    def bad_swarm_callback(self, download):
        pass
        
    """
    API calls
    """
    
    def add_file(self, file_):
        self.send_message(MESSAGE_KEY_ADD_FILE, file_)
        
    def add_peer(self, ip, port, family=socket.AF_INET):
        self.send_message(MESSAGE_KEY_ADD_PEER, Address(ip=ip, port=port, family=family))
        
    def add_message(self, message, addresses=[]):
        self.send_message(MESSAGE_KEY_ADD_MESSAGE, message, addresses)
        
    def add_socket(self, ip, port, family=socket.AF_INET):
        self.send_message(MESSAGE_KEY_ADD_SOCKET, Address(ip=ip, port=port, family=family))
    
    def monitor_directory(self, directory):
        self.send_message(MESSAGE_KEY_MONITOR_DIRECTORY, directory)
        
    def interface_came_up(self, ip, interface_name, device_name, gateway=None):
        self.send_message(MESSAGE_KEY_INTERFACE_UP, ip, interface_name, device_name, gateway=gateway)
    
    """
    HANDLE MESSAGES
    """
    
    def _state_change(self, state):
        self._state = state
        if self._callback_state_change is not None:
            self._callback_state_change(state)
        if self._state == STATE_DONE:
            self._api_stop()
            if self.stop_on_dispersy_stop:
                self.on_dispersy_stopped()
            
    def _swift_state(self, state, error=None):
        if self._callback_swift_state is not None:
            self._callback_swift_state(state, error)

    def _swift_pid(self, pid):
        self._children_recur.append(pid)

    
class ReceiverAPI(PipeHandler):
    """
    This ReceiverAPI receives calls from a parent process via a pipe, which is listened to continuously.
    Sending is done only in response to DispersyInstance callbacks or responses to previous calls.
    The calls and responses are tuples where the first parameter is the key to a specific response,
    the second parameter a tuple of args and the last a dictionary of args.
    """
    
    def __init__(self, child_conn, *args, **kwargs):
        
        self.MESSAGE_KEY_MAP = {MESSAGE_KEY_STOP : self.stop,
                                MESSAGE_KEY_STATE : self.send_state,
                                MESSAGE_KEY_ADD_FILE : self.add_file,
                                MESSAGE_KEY_ADD_PEER : self.add_peer,
                                MESSAGE_KEY_ADD_SOCKET : self.add_socket,
                                MESSAGE_KEY_ADD_MESSAGE : self.add_message,
                                MESSAGE_KEY_MONITOR_DIRECTORY : self.monitor_directory_for_files,
                                MESSAGE_KEY_INTERFACE_UP : self.interface_came_up}
        PipeHandler.__init__(self, child_conn, name="ReceiverAPI")
    
        self.state = STATE_NOT
        kwargs["callback"] = self._generic_callback
        logger.debug("Calling DispersyInstance with %s %s", args, kwargs)
        try:
            self.dispersy_instance = DispersyInstance(*args, **kwargs)
        except:
            logger.exception("Could not initiate Dispersy!")
            self.is_alive_event.set()
            self.send_message(MESSAGE_KEY_STOP)
            self.close_connection()
            return
        self.waiting_queue = Queue.Queue() # Hold on to calls that are made prematurely
        
        self.dispersy_callbacks_map = {MESSAGE_KEY_STATE : self._state_change}
        
        self.run()
        
        
    def run(self):
        self.is_alive_event.set() # Ready to receive messages
        logger.debug("Started DispersyInstance")
        correctStop = self.dispersy_instance.start() # Blocking call
        logger.debug("DispersyInstance has stopped %s!", "correctly" if correctStop else "incorrectly")
                
    def stop(self):
        if self.dispersy_instance:
            self.dispersy_instance.stop()
        # If you close the pipe here, the parent process will not get the final state changes
        
    def _connection_process_gone(self):
        self.stop()
    
    """
    DISPERSY MESSAGE QUEUE
    """
    
    def _enqueue(self, func, *args, **kwargs):
        logger.debug("Enqueue %s %s %s", func, args, kwargs)
        self.waiting_queue.put((func, args, kwargs))
    
    def _dequeue(self):
        while not self.waiting_queue.empty() and self.state == STATE_RUNNING:
            func, args, kwargs = self.waiting_queue.get()
            logger.debug("Dequeue %s %s %s", func, args, kwargs)
            func(*args, **kwargs)
    
    """
    INCOMING MESSAGES
    """        
    
    def send_state(self):
        self.send_message(MESSAGE_KEY_STATE, self.state)
    
    def add_message(self, message, addresses):
        assert len(message) < 2**16
        assert isinstance(message, str)
        if self.state == STATE_RUNNING:
            addrs = [Address.unknown(a) for a in addresses]
            self.dispersy_instance._register_some_message(APIMessageCarrier(message, addresses=addrs))
        else:
            self._enqueue(self.add_message, message, addresses)
    
    def monitor_directory_for_files(self, directory):
        if self.state == STATE_RUNNING:
            return self.dispersy_instance._filepusher.set_directory(directory)
        else:
            self._enqueue(self.monitor_directory_for_files, directory)
        
    def add_file(self, file_):
        if self.state == STATE_RUNNING:
            return self.dispersy_instance._filepusher.add_files([file_])
        else:
            self._enqueue(self.add_file, file_)
            
    def pause_file(self, file_):
        """
        Delete channel, but keep content and state
        """
        download = self.dispersy_instance._community.swift_community.get_download_by_file(file_)
        self.dispersy_instance._community.swift_community.pause_download(download)
        
    def continue_file(self, file_):
        """
        Try finding file in downloads and start it again, otherwise add it
        """
        download = self.dispersy_instance._community.swift_community.get_download_by_file(file_)
        if download is None:
            self.add_file(file_)
        else:
            self.dispersy_instance._community.swift_community.continue_download(download)
        
    def stop_file(self, file_):
        """
        Delete channel and state, but keep content
        """
        download = self._dispersy_instance._community.swift_community.get_download_by_file(file_)
        self.dispersy_instance._community.swift_community.stop_download(download)
    
    def add_peer(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            self.dispersy_instance.send_introduction_request(address.addr())
        else:
            self._enqueue(self.add_peer, address)
        
    def add_socket(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            e = self.dispersy_instance._endpoint.add_endpoint(address, api_callback=self._generic_callback)
            e.open(self.dispersy_instance._dispersy)
        else:
            self._enqueue(self.add_socket, address)
    
    def return_progress_data(self):
        if self.state == STATE_RUNNING:
            downloads = self.dispersy_instance._endpoint.downloads
        else:
            self._enqueue(self.return_progress_data)
        # These downloads should contain most information
        # TODO: Find something to return
    
    def interface_came_up(self, ip, if_name, device, gateway=None):
        logger.debug("Interface came up with %s %s %s %s", ip, if_name, device, gateway)
        if self.state == STATE_RUNNING:
            addr = Address.unknown(ip)
            if addr.resolve_interface():
                if addr.interface.name != if_name:
                    return # Provided the wrong interface..
                addr.interface.device = device
                addr.interface.gateway = gateway
                if addr.interface.address is None: # In case netifaces does not recognize interface such as ppp
                    addr.interface.address = ip         
                self.dispersy_instance._endpoint.interface_came_up(addr)               
            else:
                logger.debug("Bogus interface, cannot locate it")
        else:
            self._enqueue(self.interface_came_up, ip, if_name, device, gateway=gateway)
            
    def set_API_logger(self, logger):
        logger = logger
        
    def set_dispersy_instance_logger(self, logger):
        pass
    
    
    """
    INCOMING CALLBACKS
    """    
        
    def _generic_callback(self, key, *args, **kwargs):
        logger.debug("Callback %s %s %s", key, args, kwargs)
        try:
            func = self.dispersy_callbacks_map[key]
            func(*args, **kwargs)
        except:
            logger.debug("No special function available for %d", key)
            self.send_message(key, *args, **kwargs)            

    def _state_change(self, state):
        logger.info("STATECHANGE: %d -> %d", self.state, state)
        self.state = state
        self.send_state()
        if state == STATE_RUNNING:
            self._dequeue()
        if state == STATE_DONE:            
            self.close_connection() # Cleaning up pipe
        
if __name__ == "__main__":
    from src.main import main
    args, kwargs = main()
    a = API("API", *args, **kwargs)
    a.start()

    