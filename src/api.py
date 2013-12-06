'''
Created on Nov 15, 2013

@author: Vincent Ketelaars
'''

import Queue
import socket
import os
import signal
from threading import Thread, Event
from multiprocessing import Process, Pipe

from src.dispersy_instance import DispersyInstance
from src.address import Address
from src.definitions import STATE_NOT, STATE_RUNNING, MESSAGE_KEY_ADD_FILE, MESSAGE_KEY_ADD_MESSAGE, MESSAGE_KEY_ADD_PEER, \
MESSAGE_KEY_ADD_SOCKET, MESSAGE_KEY_INTERFACE_UP, MESSAGE_KEY_MONITOR_DIRECTORY, MESSAGE_KEY_RECEIVE_FILE, \
MESSAGE_KEY_RECEIVE_MESSAGE, MESSAGE_KEY_STATE, MESSAGE_KEY_STOP, STATE_DONE,\
    MESSAGE_KEY_SWIFT_RESET, MESSAGE_KEY_SOCKET_ERROR, MESSAGE_KEY_SWIFT_PID

from src.logger import get_logger
from src.tools.runner import CallFunctionThread
logger = get_logger(__name__)

class PipeHandler(object):
    
    # This dictionary needs to be overwritten for the messages to be handled
    # It should hold a MESSAGE_KEY_* as key and a function as value
    MESSAGE_KEY_MAP = {} 
    
        
    def __init__(self, connection):
        self.conn = connection        
        
        # Receive from pipe
        self.stop_receiving_event = Event()
        self.is_alive_event = Event() # Wait until subclass tells you it is ready
        t = Thread(target=self.wait_on_recv)
        t.start()
        
        # Start send thread
        self.sender = CallFunctionThread(timeout=1.0)
        self.sender.start()
        
    def stop_connection(self):
        self.stop_receiving_event.set()
        self.sender.stop(wait_for_tasks=True, timeout=1.0) # Wait at most timeout till queue is empty
        self.conn.close()
        logger.debug("Connection closed")
    
    def wait_on_recv(self):
        """
        Listen to pipe for incoming messages, which are dispatched to handle_message
        """
        while not self.stop_receiving_event.is_set():
            message = None
            try:
                if self.conn.poll(1.0):
                    message = self.conn.recv()
            except:
                logger.exception("Could not receive message over pipe")
            self.is_alive_event.wait()
            self.handle_message(message)
            
    def send_message(self, key, *args, **kwargs):
        """
        Send message via pipe to parent process
        
        @param key: MESSAGE_KEY
        """
        
        def send():
            try:
                self.conn.send((key, args, kwargs))
            except:
                logger.exception("Failed to send %s %s %s", key, args, kwargs)
        
        self.sender.put(send)
        
    def handle_message(self, message):
        if not message:
            return
        try:
            func = self.MESSAGE_KEY_MAP[message[0]]
            func(*message[1], **message[2])
        except:
            logger.exception("Failed to dispatch incoming message %d %s %s", message[0], message[1], message[2])


class API(Thread, PipeHandler):
    '''
    API serves as the main vehicle for starting a DispersyInstance process. 
    It can send commands and receive feedback via a pipe connection.
    '''

    def __init__(self, name, *di_args, **di_kwargs):
        Thread.__init__(self, name=name)
        self.setDaemon(True)  # Automatically die when the main thread dies
        self._state = STATE_NOT
        parent_conn, child_conn = Pipe()
        
        self.MESSAGE_KEY_MAP = {MESSAGE_KEY_STATE : self._state_change,
                                MESSAGE_KEY_RECEIVE_FILE : self._received_file,
                                MESSAGE_KEY_RECEIVE_MESSAGE : self._received_message,
                                MESSAGE_KEY_SWIFT_RESET : self._swift_reset,
                                MESSAGE_KEY_SOCKET_ERROR : self._socket_error,
                                MESSAGE_KEY_SWIFT_PID : self._swift_pid}
        PipeHandler.__init__(self, parent_conn)

        self.receiver_api = Process(target=ReceiverAPI, args=(child_conn,) + di_args, kwargs=di_kwargs)
        
        # Callbacks
        self._callback_file_received = None
        self._callback_message_received = None
        self._callback_state_change = None
        self._callback_swift_reset = None
        self._callback_socket_error = None
        
        # Any child class that wants to stop when Dispersy stops should implement stop and set this to True
        self.stop_on_dispersy_stop = False
        self._children_recur = [] # process id of every child, grandchild, etc.
        
    def start(self):
        self.receiver_api.start()
        self._children_recur.append(self.receiver_api.pid)
        self.is_alive_event.set()
        Thread.start(self)
        
    def run(self):
        logger.debug("Implement that shit!")
        
    def stop(self):
        """
        API call that will tell Dispersy to stop, if necessary
        """               
        if self._state == STATE_RUNNING: # Tell Dispersy to stop
            self.send_message(MESSAGE_KEY_STOP)
        else:
            self._api_stop()
        # TODO: If something goes wrong, finish should still be called
        
    def _api_stop(self):
        # wait_on_receive will block unless this is set (Is already set in case process was started)
        # TODO: Make sure that you kill (have killed) the child process before you sever the connection
        # Or try join for a short while, and forcefully kill it if it does not succeed.
        # This could leave subprocesses of the childprocess running.
        if not self.is_alive_event.is_set():
            self.is_alive_event.set()        
            self.stop_connection()
        else:
            self.stop_connection()
            self.finish()
        
    def finish(self):
        """
        Finish call that will ensure that the child process is killed.
        This is called when Dispersy signals STATE_DONE.
        """
        logger.debug("Joining")
        self.receiver_api.join(1) # If the process hasn't started, you cannot join it
        # join should timeout after 1 second if necessary
        for pid in self._children_recur: # Go through the processes.. (i.e. probably start with the oldest, in case they respawn killed processes)
            try:
                os.kill(pid, signal.SIGKILL) # Kill child process
                logger.debug("Had to kill process %d", pid)
            except:
                pass
        logger.debug("finished")
    
    @property
    def state(self):
        return self._state
    
    def on_dispersy_stopped(self):
        raise NotImplementedError()
            
    """
    SUBSCRIBE TO MESSAGE CALLBACKS
    """
        
    def file_received_callback(self, callback):
        self._callback_file_received = callback
        
    def message_received_callback(self, callback):
        self._callback_message_received = callback    
        
    def state_change_callback(self, callback):
        self._callback_state_change = callback
        
    def swift_reset_callback(self, callback):
        self._callback_swift_reset = callback
        
    def socket_error_callback(self, callback):
        self._callback_socket_error = callback
        
    """
    API calls
    """
    
    def add_file(self, file_):
        self.send_message(MESSAGE_KEY_ADD_FILE, file_)
        
    def add_peer(self, ip, port, family):
        self.send_message(MESSAGE_KEY_ADD_PEER, Address(ip=ip, port=port, family=family))
        
    def add_message(self, message, message_kind):
        self.send_message(MESSAGE_KEY_ADD_MESSAGE, message, message_kind)
        
    def add_socket(self, ip, port, family=socket.AF_INET):
        self.send_message(MESSAGE_KEY_ADD_SOCKET, Address(ip=ip, port=port, family=family))
    
    def monitor_directory(self, directory):
        self.send_message(MESSAGE_KEY_MONITOR_DIRECTORY, directory)
        
    def interface_came_up(self, ip, interface_name, device_name, gateway=None):
        self.send_message(MESSAGE_KEY_INTERFACE_UP, ip, interface_name, device_name, gateway=gateway)
    
    """
    HANDLE MESSAGES
    """

        
    def _received_file(self, file_):
        if self._callback_file_received is not None:
            self._callback_file_received(file)
        
    def _received_message(self, message, message_kind):
        if self._callback_message_received is not None:
            self._callback_message_received(message, message_kind)
    
    def _state_change(self, state):
        self._state = state
        if self._callback_state_change is not None:
            self._callback_state_change(state)
        if self._state == STATE_DONE:
            self._api_stop()
            if self.stop_on_dispersy_stop:
                self.on_dispersy_stopped()
            
    def _swift_reset(self, error):
        if self._callback_swift_reset is not None:
            self._callback_swift_reset(error)
            
    def _socket_error(self, address, errno):
        if self._callback_socket_error is not None:
            self._callback_socket_error(address, errno)
            
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
        PipeHandler.__init__(self, child_conn)
    
        self.state = STATE_NOT
        kwargs["callback"] = self._generic_callback
        logger.debug("Calling DispersyInstance with %s %s", args, kwargs)
        self.dispersy_instance = DispersyInstance(*args, **kwargs)
        self.waiting_queue = Queue.Queue() # Hold on to calls that are made prematurely
        
        self.dispersy_callbacks_map = {MESSAGE_KEY_STATE : self._state_change,
                                       MESSAGE_KEY_RECEIVE_FILE : self._received_file,
                                       MESSAGE_KEY_RECEIVE_MESSAGE : self._received_message,
                                       MESSAGE_KEY_SWIFT_RESET : self._swift_reset,
                                       MESSAGE_KEY_SOCKET_ERROR : self._socket_error,
                                       MESSAGE_KEY_SWIFT_PID : self._swift_pid}
        
        self.run()
        
        
    def run(self):
        self.is_alive_event.set() # Ready to receive messages
        logger.debug("Started DispersyInstance")
        correctStop = self.dispersy_instance.start() # Blocking call
        logger.debug("DispersyInstance has stopped %s!", "correctly" if correctStop else "incorrectly")
                
    def stop(self):
        self.dispersy_instance.stop()
        # If you close the pipe here, the parent process will not get the final state changes
    
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
    
    def add_message(self, message, message_kind):
        assert len(message) < 2**16
        if self.state == STATE_RUNNING:
            pass
        # TODO: These will be special message kinds which need to be developed..
    
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
    
    def add_peer(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            self.dispersy_instance.send_introduction_request(address.addr())
        else:
            self._enqueue(self.add_peer, address)
        
    def add_socket(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            e = self.dispersy_instance._endpoint.add_endpoint(address)
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
    DISPERSY UPDATES 
    """    
        
    def _generic_callback(self, key, *args, **kwargs):
        logger.debug("Callback %s %s %s", key, args, kwargs)
        try:
            func = self.dispersy_callbacks_map[key]
            func(*args, **kwargs)
        except:
            logger.exception("Failed to handle dispersy callback")

    def _state_change(self, state):
        logger.info("STATECHANGE: %d -> %d", self.state, state)
        self.state = state
        self.send_state()
        if state == STATE_RUNNING:
            self._dequeue()
        if state == STATE_DONE:            
            self.stop_connection() # Cleaning up pipe
        
    def _received_file(self, file_):
        logger.info("RECEIVED FILE: %s", file_)
        self.send_message(MESSAGE_KEY_RECEIVE_FILE, file_)
        
    def _received_message(self, message, message_kind):
        logger.info("RECEIVED MESSAGE: %s %s", message[0:100], message_kind)
        self.send_message(MESSAGE_KEY_RECEIVE_MESSAGE, message, message_kind)
        
    def _swift_reset(self, error=['0' * 20,"unknown"]): # Defaults to 00000000000000000000 unknown
        logger.info("SWIFT RESET: %s", error)
        self.send_message(MESSAGE_KEY_SWIFT_RESET, error)
        
    def _socket_error(self, address, errno):
        logger.info("SOCKET ERROR: %s %d", address, errno)
        self.send_message(MESSAGE_KEY_SOCKET_ERROR, address, errno)
    
    def _swift_pid(self, pid):
        self.send_message(MESSAGE_KEY_SWIFT_PID, pid)
        
if __name__ == "__main__":
    from src.main import main
    main(API)
    

    