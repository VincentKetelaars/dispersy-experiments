'''
Created on Aug 7, 2013

@author: Vincent Ketelaars

This is the main file which starts up Dispersy instances.
'''

import time
import os
import argparse

from multiprocessing import Process, Pipe

from src.dispersy_process import DispersyProcess
from src.dispersy_instance import DispersyInstance
from src.filepusher import FilePusher

import logging.config

# Time in seconds
UPDATE_TIME = 1
TOTAL_RUN_TIME = 20 # Integer
        
def main(num_instances, show_logs, directory=None, files=[]):
    if show_logs:
        logger_conf = os.path.abspath(os.environ.get("LOGGER_CONF", "logger.conf"))
        logging.config.fileConfig(logger_conf)
        logger = logging.getLogger(__name__)
        logger.info("Logger using configuration file: " + logger_conf)
    else:
        logger = logging.getLogger(__name__)
    
    # Start the Dispersy instances
    process_list = []
    for _ in range(num_instances):
        conn1, conn2 = Pipe()
        dis = DispersyInstance(conn2)
        p = Process(target=dis.run, args=(num_instances,))
        process_list.append(DispersyProcess(p, conn1))
        p.start()
    
    logger.info(str(num_instances) + " processes have been started")
    
    # Receive the lan addresses from each of the instances   
    for p in process_list:
        p.lan = p.pipe.recv()
    logger.info("The addresses of all processes have been received")
    
    # Send to each instance the lan addresses of the others
    for x in process_list:
        for y in process_list:
            if x != y:
                x.pipe.send(y.lan)
    
    logger.info("All processes have been send all addresses")
    
    fileconn, conn2 = Pipe()
    if directory is None and not files:
        dirc = "/home/vincent/Desktop/tests"
        filepusher = FilePusher(conn2, directory=dirc)
    else:
        filepusher = FilePusher(conn2, directory=directory, files=files)
        
    Process(target=filepusher.run).start()
    logger.info("FilePusher is running!")
    
    counter = int(TOTAL_RUN_TIME / UPDATE_TIME)
    while counter > 0:
        if fileconn.poll():
            m = fileconn.recv()
            logger.info("Message arrived from FilePusher")
            process_list[0].pipe.send("message")
            process_list[0].pipe.send(m)
            logger.info("Message send to process!")
        time.sleep(UPDATE_TIME)
        counter -= 1
        
    logger.info("Done fooling around for today!")
 
    try:
        fileconn.send(False)
        fileconn.close()
        # Make sure to stop each Dispersy instance, pipe and process
        for p in process_list:
            p.pipe.send("continue")
            p.pipe.send(False) # Tell process to end connection and stop Dispersy
            p.pipe.close()
            p.process.join()
    except:
        logger.warning("Stopping instances, pipes and processes has failed")
    finally:
        for p in process_list:
            p.process.terminate()
    
    logger.info("The program is finished")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start Dispersy instance(s)')
    parser.add_argument("-n", type=int, help="Create n Dispersy instances")
    parser.add_argument("-i", "--logging", action="store_true", help="If set, logs will be shown in the cmd")
    parser.add_argument("-d", "--directory",help="List directory of files to send")
    parser.add_argument("-f", "--files", nargs="+", help="List files to send")
    args = parser.parse_args()

    main(args.n, args.logging, args.directory, args.files)   
    