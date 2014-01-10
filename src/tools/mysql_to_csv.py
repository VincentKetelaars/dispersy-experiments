'''
Created on Dec 13, 2013

@author: Vincent Ketelaars
'''
import argparse
import csv
import sys
from sets import Set
from datetime import datetime

from Common.InternalDB import mysql

from src.logger import get_logger

logger = get_logger(__name__)

class ConfigTree():
    
    def __init__(self, root=None):
        if root is None:
            self.root = ConfigElement(-1, "root", 0, "folder", datetime.utcnow(), -1)
        else:
            self.root = root
        
    def add_child(self, child, parent=None):
        assert isinstance(child, ConfigElement)
        if parent is not None:
            assert isinstance(parent, ConfigElement)
            if parent.type == "folder":
                parent.add_child(child)
    
    def get_root(self):
        return self.root
    
    def dfs(self, e):
        pass
    
class ConfigElement():
    
    def __init__(self, id_, name, value, type_, last_modified, parent_id, version=1, comment=None):
        self.id = id_
        self.name = name
        self.value = value
        self.type = type_
        self.last_modified = last_modified
        self.parent_id = parent_id
        self.parent = None
        self.version = version
        self.comment = comment
        self.children = Set()
        
    def add_child(self, child):
        self.children.add(child)
        child.set_parent(self)
        
    def set_parent(self, parent):
        self.parent = parent
        
    def __eq__(self, other):
        assert isinstance(other, ConfigElement)
        return self.id == other.id
    
    def __neq__(self, other):
        return not self.__eq__(other)
    
    def __hash__(self):
        return self.id
    
    def __str__(self):
        return "{0} {1} {2} {3} {4} {5} {6} {7}".format(self.name, self.id, self.value, self.type, self.last_modified, 
                                                self.parent_id, self.version, self.comment)
        
class StatusElement(object):
    
    def __init__(self, id_, timestamp, paramid, chanid, value):
        self.id = id_
        self.timestamp = timestamp
        self.paramid = paramid
        self.chanid = chanid
        self.value = value
        self.param_name = None
        self.chan_name = None
        
    def set_param(self, name):
        self.param_name = name
        
    def set_chan(self, name):
        self.chan_name = name

class MySQLToCSV(object):
    
    def __init__(self, database, file_, channel, parameters=[], start=None, end=None, normalize=False):
        self.db_name = database
        self.file = file_         
        self.mysql = mysql("mysql", db_name=self.db_name)
        self.channel = (self.get_channel(channel), channel)
        self.parameters = parameters
        
        logger.debug("Working on database %s", database)
        
        start_time = None
        if start is not None:
            start_time = datetime.strptime(start, "%H:%M:%S_%d-%m-%Y")
            
        end_time = None
        if end is not None:
            end_time = datetime.strptime(end, "%H:%M:%S_%d-%m-%Y")
        
        logger.debug("Channel %s has id %d", channel, self.channel[0])
        params_to_csv = {}
        
        status_params = self.get_status_parameters(chanid=self.channel[0])
        logger.debug("Channel has %d parameters", len(status_params))
        status = self.get_status_by_channel(self.channel[0], start=self.unix_time(start_time), end=self.unix_time(end_time))
        logger.debug("Channel has %d values from %s to %s", len(status), start, end)
        for s in status:
            s.set_chan(channel)
            s.set_param(status_params[s.paramid][1])
            if not parameters or (parameters and status_params[s.paramid][1] in parameters):
                if params_to_csv.has_key(s.paramid):
                    l = params_to_csv.pop(s.paramid)
                    l.append(s)
                    params_to_csv[s.paramid] = l
                else:
                    params_to_csv[s.paramid] = [s]
                    
        norm_str = ""
        if normalize:
            norm_str = "normalized "
            minimum = sys.float_info.max
            for v in params_to_csv.itervalues():
                minimum = min([minimum] + [s.timestamp for s in v])
            for v in params_to_csv.itervalues():
                for s in v:
                    s.timestamp = s.timestamp - minimum
        
        logger.debug("%d %sparameters will be written to %s", len(params_to_csv), norm_str, self.file)
        for i, v in params_to_csv.iteritems():
            params_to_csv[i] = sorted(v, key=lambda obj: obj.paramid)
            
        sorted_params = sorted(params_to_csv.iterkeys(), key=lambda i: status_params[i])
                    
        with open(self.file, "wb") as csvfile:
            writer = csv.writer(csvfile, delimiter=',') # Need quotes?
            for i in sorted_params:
                writer.writerow([status_params[i][0], "timestamp"] + [s.timestamp for s in params_to_csv[i]])
                writer.writerow([status_params[i][0], "value"] + [s.value for s in params_to_csv[i]])
                
        
    def get_channel(self, name):
        """
        @return chanid
        """
        # chanid, name
        SQL = "SELECT chanid FROM status_channel WHERE name = ?"
        cursor = self.mysql._execute(SQL, [name])
        row = cursor.fetchone()
        if row is not None:
            return row[0]
        return 0
    
    def get_config_parameter(self, name):
        # id : 0, version : 1, last_modified : 2, parent : 3, name : 4, value : 5, datatype : 6, comment : 7
        SQL = "SELECT id, last_modified, parent, value, datatype FROM config WHERE name = ?"
        cursor = self.mysql._execute(SQL, [name])
        if cursor is not None:
            elements = []
            for row in cursor.fetchall():
                elements.append(ConfigElement(row[0], name, row[3], row[4], row[1], row[2]))
        return elements
    
    def get_status_parameters(self, name="", chanid=0):
        # id, timestamp, paramid, chanid, value
        SQL = "SELECT * FROM status_parameter WHERE name = ? OR chanid = ?"
        cursor = self.mysql._execute(SQL, [name, chanid])
        sp = {}
        if cursor:
            for row in cursor.fetchall():
                sp[row[0]] = (row[1], row[2])
        return sp
    
    def get_status_by_channel(self, chanid, start=0, end=0):
        params = [chanid]
        t = ""
        if start > 0:
            params.append(start)
            t = " AND timestamp > ?"
        if end > 0:
            params.append(end)
            t += " AND timestamp < ?"
        SQL = "SELECT * FROM status WHERE chanid = ?"+ t
        dSQL = SQL
        for p in params:
            dSQL = dSQL.replace("?", str(p), 1)
        logger.debug(dSQL)
        cursor = self.mysql._execute(SQL, params)
        elements = []
        if cursor:
            for row in cursor.fetchall():
                elements.append(StatusElement(*row))
        return elements
    
    def unix_time(self, dt):
        if dt is None:
            return 0;
        epoch = datetime.utcfromtimestamp(0)
        delta = dt - epoch
        return delta.total_seconds()
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert MySQL to CSV')
    parser.add_argument("-c", "--channel", required=True, help="Channel")
    parser.add_argument("-d", "--database", required=True, help="Database")
    parser.add_argument("-e", "--end", help="Get only values before this time, formatted: hh:mm:ss_dd-MM-YYYY")
    parser.add_argument("-f", "--file", required=True, help="CSV file")
    parser.add_argument("-p", "--params", default=[], nargs="+", help="Parameters")
    parser.add_argument("-s", "--start", help="Get only values after this time, formatted: hh:mm:ss_dd-MM-YYYY")
    parser.add_argument("-z", "--zero", action="store_true", help="Normalize timestamps to start from zero")
    args = parser.parse_args()

    MySQLToCSV(args.database, args.file, args.channel, parameters=args.params, start=args.start, end=args.end, 
               normalize=args.zero)