'''
Created on Nov 15, 2013

@author: Vincent Ketelaars
'''

import Queue
from threading import Thread, Event
from multiprocessing import Process, Pipe

from src.dispersy_instance import DispersyInstance
from src.address import Address
from src.definitions import STATE_NOT, STATE_RUNNING, MESSAGE_KEY_ADD_FILE, MESSAGE_KEY_ADD_MESSAGE, MESSAGE_KEY_ADD_PEER, \
MESSAGE_KEY_ADD_SOCKET, MESSAGE_KEY_INTERFACE_UP, MESSAGE_KEY_MONITOR_DIRECTORY, MESSAGE_KEY_RECEIVE_FILE, \
MESSAGE_KEY_RECEIVE_MESSAGE, MESSAGE_KEY_STATE, MESSAGE_KEY_STOP, STATE_DONE

from dispersy.logger import get_logger
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
        self.sender.stop(Event(), timeout=1.0) # Wait at most timeout till queue is empty
        self.conn.close()
        logger.debug("Connection closed")
    
    def wait_on_recv(self):
        """
        Listen to pipe for incoming messages, which are dispatched to handle_message
        """
        while not self.stop_receiving_event.is_set():
            message = self.conn.recv()
            self.is_alive_event.wait()
            self.handle_message(message)
            
    def send_message(self, key, *args, **kwargs):
        """
        Send message via pipe to parent process
        
        @param key: MESSAGE_KEY
        """
        self.sender.put(self.conn.send, args=((key, args, kwargs),))
        
    def handle_message(self, message):
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

    def __init__(self, *di_args, **di_kwargs):
        Thread.__init__(self)
        self.setDaemon(True)  # Automatically die when the main thread dies
        self._state = STATE_NOT
        parent_conn, child_conn = Pipe()
        
        self.MESSAGE_KEY_MAP = {MESSAGE_KEY_STATE : self._state_change,
                                MESSAGE_KEY_RECEIVE_FILE : self._received_file,
                                MESSAGE_KEY_RECEIVE_MESSAGE : self._received_message}
        PipeHandler.__init__(self, parent_conn)

        self.receiver_api = Process(target=ReceiverAPI, args=(child_conn,) + di_args, kwargs=di_kwargs)
        
        # Callbacks
        self._callback_file_received = None
        self._callback_message_received = None
        self._callback_state_change = None
        
    def start(self):
        self.receiver_api.start()
        self.is_alive_event.set()
        
    def stop(self):
        """
        API call that will tell Dispersy to stop
        """
        self.send_message(MESSAGE_KEY_STOP)
        # TODO: If something goes wrong, finish should still be called
        
    def finish(self):
        """
        Finish call that will ensure that the child process is killed.
        This is called when Dispersy signals STATE_DONE.
        """
        self.receiver_api.join()
        logger.debug("finished")
    
    @property
    def state(self):
        return self._state
            
    """
    SUBSCRIBE TO MESSAGE CALLBACKS
    """
        
    def file_received_callback(self, callback):
        self._callback_file_received = callback
        
    def message_received_callback(self, callback):
        self._callback_message_received = callback    
        
    def state_change_callback(self, callback):
        self._callback_state_change = callback
        
    """
    API calls
    """
    
    def add_file(self, file_):
        self.send_message(MESSAGE_KEY_ADD_FILE, file_)
        
    def add_peer(self, ip, port, family):
        self.send_message(MESSAGE_KEY_ADD_PEER, Address(ip=ip, port=port, family=family))
        
    def add_message(self, message, message_kind):
        self.send_message(MESSAGE_KEY_ADD_MESSAGE, message, message_kind)
        
    def add_socket(self, ip, port, family):
        self.send_message(MESSAGE_KEY_ADD_SOCKET, Address(ip=ip, port=port, family=family))
    
    def monitor_directory(self, directory):
        self.send_message(MESSAGE_KEY_MONITOR_DIRECTORY, directory)
        
    def interface_came_up(self, ip, interface_name, device_name):
        self.send_message(MESSAGE_KEY_INTERFACE_UP, ip, interface_name, device_name)
    
    """
    HANDLE MESSAGES
    """

        
    def _received_file(self, file_):
        if self._callback_file_received:
            self._callback_file_received(file)
        
    def _received_message(self, message, message_kind):
        if self._callback_message_received:
            self._callback_message_received(message, message_kind)
    
    def _state_change(self, state):
        self._state = state
        if self._callback_state_change:
            self._callback_state_change(state)
        if self._state == STATE_DONE:
            self.stop_connection()
            self.finish()
    
    
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
        self.dispersy_instance = DispersyInstance(*args, **kwargs)
        self.waiting_queue = Queue.Queue() # Hold on to calls that are made prematurely
        
        self.dispersy_callbacks_map = {MESSAGE_KEY_STATE : self._state_change,
                                       MESSAGE_KEY_RECEIVE_FILE : self._received_file,
                                       MESSAGE_KEY_RECEIVE_MESSAGE : self._received_message}
        
        self.run()
        
        
    def run(self):
        self.is_alive_event.set() # Ready to receive messages
        logger.debug("Started DispersyInstance")
        correctStop = self.dispersy_instance.start() # Blocking call
        logger.debug("DispersyInstance has stopped %s!", "correctly" if correctStop else "incorrectly")
        self.stop_connection() # Cleaning up pipe
                
    def stop(self):
        self.dispersy_instance.stop()
        # If you close the pipe here, the parent process will not get the final state changes
    
    """
    DISPERSY MESSAGE QUEUE
    """
    
    def _enqueue(self, func, args, kwargs):
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
            self._enqueue(self.monitor_directory_for_files, (directory,), {})
        
    def add_file(self, file_):
        if self.state == STATE_RUNNING:
            return self.dispersy_instance._filepusher.add_files([file_])
        else:
            self._enqueue(self.add_file, (file_,), {})
    
    def add_peer(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            self.dispersy_instance.send_introduction_request(address.addr())
        else:
            self._enqueue(self.add_peer, (address,), {})
        
    def add_socket(self, address):
        assert isinstance(address, Address)
        if self.state == STATE_RUNNING:
            e = self.dispersy_instance._endpoint.add_endpoint(address)
            e.open(self.dispersy_instance._dispersy)
        else:
            self._enqueue(self.add_socket, (address,), {})
    
    def return_progress_data(self):
        if self.state == STATE_RUNNING:
            downloads = self.dispersy_instance._endpoint.downloads
        else:
            self._enqueue(self.return_progress_data, (), {})
        # These downloads should contain most information
        # TODO: Find something to return
    
    def interface_came_up(self, ip, if_name, device):
        addr = Address.unknown(ip)
        if addr.resolve_interface():
            if addr.interface.name != if_name:
                return # Provided the wrong interface..
            else:
                addr.interface.device = device
        if self.state == STATE_RUNNING:
            return self.dispersy_instance._endpoint.if_came_up(addr)
        else:
            self._enqueue(self.interface_came_up, (ip, if_name, device), {})
        
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
        
    def _received_file(self, file_):
        logger.info("RECEIVED FILE: %s", file_)
        self.send_message(MESSAGE_KEY_RECEIVE_FILE, file_)
        
    def _received_message(self, message, message_kind):
        logger.info("RECEIVED MESSAGE: %s %s", message[0:100], message_kind)
        self.send_message(MESSAGE_KEY_RECEIVE_MESSAGE, message, message_kind)
        
        
        
if __name__ == "__main__":
    from src.main import main
    main(API)
    

    