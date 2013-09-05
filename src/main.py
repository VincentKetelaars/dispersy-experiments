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
TOTAL_RUN_TIME = 30 # Integer
FILE_DIR = "/home/vincent/Desktop/tests"
DEST_DIR = "/home/vincent/Desktop/tests_dest"
SWIFT_BINPATH = "/home/vincent/svn/libswift/ppsp/swift"
        
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
        dis = DispersyInstance(conn2, DEST_DIR, SWIFT_BINPATH)
        p = Process(target=dis.run, args=(num_instances,))
        process_list.append(DispersyProcess(p, conn1))
        p.start()
    
    logger.info(str(num_instances) + " processes have been started")
    
    # Receive the lan addresses from each of the instances   
    for p in process_list:
        p.lan = p.pipe.recv()
    logger.info("The addresses of all processes have been received")
    
    # Notify instances of each other
    for x in range(len(process_list)):
        process_list[x].pipe.send(len(process_list)-x-1)
        for y in range(x + 1,len(process_list)):
            process_list[x].pipe.send(process_list[y].lan)
    
    logger.info("All processes have been send all addresses")
    
    fileconn, conn2 = Pipe()
    if directory is None and not files:
        filepusher = FilePusher(conn2, directory=FILE_DIR)
    else:
        filepusher = FilePusher(conn2, directory=FILE_DIR, files=files)
        
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
    parser.add_argument("-t", "--time",type=int, help="Set runtime")
    parser.add_argument("-D", "--destination", help="List directory to put downloads")
    parser.add_argument("-s", "--swift", help="Swift binary path")
    args = parser.parse_args()
    
    if args.directory:
        FILE_DIR = args.directory
    
    if args.time:
        TOTAL_RUN_TIME = args.time
        
    if args.destination:
        DEST_DIR = args.destination
    
    if args.swift:
        SWIFT_BINPATH = args.swift

    main(args.n, args.logging, args.files)   
    