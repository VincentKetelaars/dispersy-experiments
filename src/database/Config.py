
"""
This class is not based on existing database wrappers, as they
all use the config service to get hold of their configuration.
"""

import MySQLdb
import threading
import os.path
import warnings

import json
import time

from src.logger import get_logger

logger = get_logger(__name__)

DEBUG=False
ANY_VERSION = 0

class ConfigException(Exception):
    pass

class NoSuchParameterException(ConfigException):
    pass

class NoSuchVersionException(ConfigException):
    pass

class VersionAlreadyExistsException(ConfigException):
    pass

class IntegrityException(ConfigException):
    pass


class ConfigParameter:
    """
    Wrapper for config database interface
    """
    
    def __init__(self, id, name, parents, path, datatype, value, version, 
                 last_modified, children=None, config=None, comment=None):
        """
        parents is a sorted list of parent ID's for the full path
        """
        self.id = id
        self.name = name
        self.parents = parents
        self.path = path
        self.set_last_modified(last_modified)
        self.comment = comment

        # Make 'float' the same as 'double' (no difference internally)
        if datatype == 'float':
            self.datatype = 'double'
        else:
            self.datatype = datatype
        self.version = version
        if not children:
            self.children = []
        else:
            self.children = children[:]
        self._config = config
        self.set_value(value, datatype)

    def __str__(self):
        return str(self.value)
    
    def __eq__(self, param):
        return self.value == param

    def __ne__(self, param):
        return self.value != param

    def set_last_modified(self, last_modified):
        if last_modified:
            self.last_modified = time.mktime(last_modified.timetuple())
        else:
            self.last_modified = None

    def set_comment(self, comment):
        self.comment = comment;

    def set_value(self, value, datatype = None):
        
        if datatype:
            self.datatype = datatype
        elif self.datatype:
            datatype = self.datatype
        else:
            raise Exception("Unknown datatype for %s"%self.name)

        try:
            if datatype == "folder":
                self.value = None
            elif value.__class__ in [str, unicode]:
                if datatype == "boolean":
                    if value.__class__ == bool:
                        self.value = value
                    else:
                        if value.isdigit():
                            self.value = int(value) == 1
                        else:
                            self.value = value.lower() == "true"
                elif datatype == "double":
                    self.value = float(value)
                elif datatype == "integer":
                    self.value = int(value)
                else:
                    self.value = value
            else:
                self.value = value
        except:
            raise ConfigException("Could not 'cast' '%s' %s to a '%s' (native class: %s)"%(self.name, value, datatype, value.__class__))
        

    def get_id(self):
        return self.id

    def get_full_path(self):
        if self.path:
            return ".".join([self.path, self.name])
        return self.name
    
    def get_name(self):
        return self.name
    
    def get_value(self):
        return self.value

    def get_children(self):
        return self.children
    
    def get_version(self):
        return self.version
            
class Configuration:
    """
    MySQL based configuration implementation for the CryoWing UAV.
    It is thread-safe.
    """
    
    def __init__(self, version=None, root="", stop_event=None):
        """
        """
        self.stop_event = stop_event
        self._internal_stop_event = threading.Event()

        if root and root[-1] != ".":
            self.root = root + "."
        elif root == None:
            self.root = ""
        else:
            self.root = root
            
        self._cb_lock = threading.Lock()

        self._cb_thread = None
        self.db_connections = {}
        self._load_lock = threading.RLock()
        self.lock = threading.Lock()
        self._cfg = {"db_name":"uav",
                     "db_host":"localhost",
                     "db_user":"pilot",
                     "db_password": "pi10t"}

        if os.path.isfile(".config"):
            cfg = json.loads(open(".config", "r").read())
            for param in cfg.keys():
                self._cfg[param] = cfg[param]

        self._prepare_tables()

        self._id_cache = {}
        self._version_cache = {}
        
        self._update_callbacks = {}

        if not version:
            try:
                version = self.get("root.default_version", version="default").get_value()
            except:
                self.set_version("default", create=True)
                self.add("root.default_version", "default", version="default")
                version = "default"

        self.set_version(version, create=True)

    def __del__(self):
        self._internal_stop_event.set()

        with self._cb_lock:
            for (cb_id, param_id) in self._update_callbacks:
                try:
                    self._execute("DELETE FROM config_callback WHERE id=%s AND param_id=%s", 
                                  [cb_id, param_id])
                except:
                    logger.exception("Failed to clean up callbacks")
                    pass
        
        with self.lock:
            for c in self.db_connections.values():
                try:
                    c.commit()
                except:
                    pass

    def close_connection(self):
        with self.lock:
            thread_name = threading.currentThread().ident
            if self.db_connections.has_key(thread_name):
                try:
                    self.db_connections[thread_name].close()
                except:
                    pass
                del self.db_connections[thread_name]


    def _get_db(self, temporary_connection=False):
        
        if temporary_connection:
            conn = MySQLdb.connect(host=self._cfg["db_host"],
                                   user=self._cfg["db_user"],
                                   passwd=self._cfg["db_password"],
                                   db=self._cfg["db_name"],
                                   use_unicode=True,
                                   charset="utf8")
            conn.autocommit(1)
            return conn
        
        with self.lock:
            thread_name = threading.currentThread().ident #getName()
            if not thread_name in self.db_connections.keys():
                #print "CREATING DB_CONNECTION",thread_name, self.db_connections.keys()
                self.db_connections[thread_name] = \
                    MySQLdb.connect(host=self._cfg["db_host"],
                                    user=self._cfg["db_user"],
                                    passwd=self._cfg["db_password"],
                                    db=self._cfg["db_name"],
                                    use_unicode=True,
                                    charset="utf8")
                self.db_connections[thread_name].autocommit(True)

            return self.db_connections[thread_name]

        
    def _execute(self, SQL, parameters=[], 
                 temporary_connection=False, 
                 ignore_error=False):
        """
        Execute an SQL statement with the given parameters.  
        """

        if DEBUG:
            logger.debug(SQL + "(" + str(parameters) + ")")

        conn = None
        while True:
            try:
                conn = self._get_db(temporary_connection=temporary_connection)
                cursor = conn.cursor()
                if len(parameters) > 0:
                    cursor.execute(SQL, tuple(parameters))
                else:
                    cursor.execute(SQL)
                return cursor
            except MySQLdb.Warning, wrng: 
                return 
                pass # Ignore these
            except MySQLdb.IntegrityError, e:
                print "Integrity error %s, SQL was '%s(%s)'"%(SQL, str(parameters), e)
                logger.exception("Integrity error %s, SQL was '%s(%s)'"%(SQL, str(parameters), e))
                raise e
                
            except MySQLdb.OperationalError, e:
                if str(e).startswith("(2006, "):
                    # Lost connection (Mysql server has gone away)
                    print "Lost connection, re-connecting"
                    self.close_connection()
                    continue

                if str(e).startswith("(2002, "):
                    # Mysql is not running
                    print "MySQL not responding, trying again in 1 second"
                    time.sleep(1.0)
                    continue

                if ignore_error:
                    return

                print "Got operational error:",e.__class__,"[%s]"%str(e)
                logger.exception("Got an operational error during sql operation, SQL:%s(%s)"%(SQL, str(parameters)))
                raise e

            except Exception, e:
                print (e)
                import traceback
                import sys
                traceback.print_exc(file=sys.stdout)
                print "SQL was:", SQL, str(parameters)
                #logger.exception("Got an error during sql operation: '%s'"%e)
                #logger.fatal("SQL was: %s %s"% (SQL, str(parameters)))
                raise e

            
    def _prepare_tables(self):
        """
        Prepare all tables and indexes if they do not exist
        """

        with warnings.catch_warnings():
            warnings.simplefilter('error', MySQLdb.Warning)

            SQL = """CREATE TABLE IF NOT EXISTS config_version (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) UNIQUE,
    device VARCHAR(128),
    comment TEXT) ENGINE = INNODB"""
            self._execute(SQL, ignore_error=False)

            self._execute("CREATE INDEX config_version_name ON config_version(name)", 
                          ignore_error = True)

            self._execute("INSERT IGNORE INTO config_version VALUES(0, 'default')",
                          ignore_error = True)

            SQL = """CREATE TABLE IF NOT EXISTS config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    version INT NOT NULL,
    last_modified TIMESTAMP,
    parent INT NOT NULL,
    name VARCHAR(128),
    value VARCHAR(256),
    datatype ENUM ('boolean', 'integer', 'double', 'string', 'folder') DEFAULT 'string',
    comment TEXT,
    FOREIGN KEY (version) REFERENCES config_version(id) ON DELETE CASCADE,
    UNIQUE(version,parent,name)) ENGINE = INNODB"""
            self._execute(SQL, ignore_error=False)

            self._execute("CREATE INDEX config_name ON config(name)", 
                          ignore_error = True)

            self._execute("CREATE INDEX config_parent ON config(parent)", 
                          ignore_error = True)

            SQL = """CREATE TABLE IF NOT EXISTS config_callback  (
    id INT NOT NULL, 
    param_id INT NOT NULL,
    last_modified TIMESTAMP, 
    PRIMARY KEY (id, param_id),
    FOREIGN KEY (param_id) REFERENCES config(id) ON DELETE CASCADE)"""
            self._execute(SQL, ignore_error=True)

    def reset(self):
        """
        Clear temporary data - should be run before software is started
        """
        self._execute("DELETE FROM config_callback");
            
    def add_version(self, version):
        """
        Add an empty configuration
        """

        with self._load_lock:
            # To avoid screaming in logs and stuff, just check if we have
            # the version already
            try:
                self._get_version_id(version)
                raise VersionAlreadyExistsException("Version '%s' already exists"%version)
            except NoSuchVersionException:
                pass


            SQL = "INSERT INTO config_version(name) VALUES(%s)"
            try:
                cursor = self._execute(SQL, [version])
            except:
                raise VersionAlreadyExistsException(version)

            # Now we need to get the version ID back
            # TODO: Get the last auto-incremented value directly?
            #logger.debug("Added version %s with id %s"%(version, cursor.lastrowid))
            #print dir(cursor)
            #self.set_version(version)
        
    def delete_version(self, version):
        """
        Delete a version (and all config parameters of it!)
        """
        with self._load_lock:
            SQL = "DELETE FROM config_version WHERE name=%s"
            self._execute(SQL, [version])

    def set_version(self, version, create=False):
        """
        Convert a version string to an internal number.  
        Throws NoSuchVersionException if it doesn't exist
        """
        with self._load_lock:
            try:
                self._cfg["version"] = self._get_version_id(version)
                self._cfg["version_string"] = version
            except NoSuchVersionException, e:
                if not create:
                    raise e
                self.add_version(version)
                return self.set_version(version, create=False)
            
    def list_versions(self, partial_name=""):
        with self._load_lock:
        
            if partial_name:
                cursor = self._execute("SELECT config_version.name, config_version.comment, max(last_modified) FROM config_version, config WHERE config_version.id=config.version AND name LIKE '%" + partial_name.replace("'", "") + "%' GROUP BY config.version")
            else:
                cursor = self._execute("SELECT config_version.name, config_version.comment, max(last_modified) FROM config_version, config WHERE config_version.id=config.version GROUP BY config.version");

            versions = []
            for row in cursor.fetchall():
                versions.append((row[0], row[1], row[2].ctime()))
            return versions

    def _get_version_id(self, name):
        if not name in self._version_cache:
            cursor = self._execute("SELECT id FROM config_version WHERE name=%s", 
                                   [name])
            row = cursor.fetchone()
            if not row:
                raise NoSuchVersionException(name)
            self._version_cache[name] = row[0]
        return self._version_cache[name]

    def copy_configuration(self, old_version, new_version, overwrite=False):
        """
        Copy a configuration to a new configuration. 
        """
        with self._load_lock:
            try:
                self.add_version(new_version)
            except:
                pass

            old_id = self._get_version_id(old_version)
            new_id = self._get_version_id(new_version)

            SQL = "INSERT INTO config (version, parent, name, value, datatype) SELECT %s,parent,name,value,datatype FROM config WHERE version=%s"
            self._execute(SQL, [new_id, old_id])
        

    def _get_parent_ids(self, full_path, version, create=True, overwrite=False):

        if DEBUG: # Makes it loop???
            logger.debug("_get_parent_ids(%s)"%full_path)

        # First find the parent
        if full_path.count(".") == 0:
            if 0 and DEBUG:
                logger.debug("%s is in the root"%full_path)
            return [0]

        parent_name, name = full_path.rsplit(".", 2)[-2:]
        parent_path = full_path.rsplit(".", 1)[0]

        parent_ids = self._get_parent_ids(parent_path, version, create, 
                                          overwrite=overwrite)
        parent_id = self._get_parent_id(parent_ids[-1], parent_name, version)
        if parent_id == None:
            if not create:
                raise NoSuchParameterException("Parent of %s does not exist, full path: '%s'"%(name, full_path))
            
            if 0 and DEBUG:
                logger.debug("No such parent - creating: %s, %s, %s"%\
                                   (parent_ids[-1], parent_name, version))

            self.add(parent_name, datatype="folder", 
                     parent_id=parent_ids[-1],
                     overwrite=overwrite)
            parent_id = self._get_parent_id(parent_ids[-1], parent_name, version)
            if parent_id == None:
                raise NoSuchParameterException("Failed to create %s"%name)

        parent_ids.append(parent_id)
        return parent_ids

    def _get_parent_id(self, parent_id, name, version):
        if name == "root":
            return 0

        if (parent_id, name) in self._id_cache:
            return self._id_cache[(parent_id, name)]

        SQL = "SELECT id FROM config WHERE parent=%s AND name=%s "
        params = [parent_id, name]
        if version:
            SQL += "AND version=%s"
            params.append(version)

        cursor = self._execute(SQL, params)
        row = cursor.fetchone()
        if not row:
            if DEBUG:
                logger.debug("Tried to get parent id for %s but failed"%\
                                   parent_id)
            return None

        self._id_cache[(parent_id, name)] = row[0]
        return row[0]

    def _get_full_path(self, full_path):
        if not full_path:
            return self.root[:-1]

        if full_path.startswith("root"):
            path = full_path[4:]
            if len(path) > 0 and path[0] == ".":
                path = path[1:]
            return path
        else:
            if self.root:
                if full_path:
                    return self.root + full_path
                else:
                    return self.root[:-1]
        return full_path
            
    def get_by_id(self, param_id, recursing=False):
        
        with self._load_lock:
            if param_id == 0:
                return [(0, "")]

            SQL = "SELECT id, parent, name, value, datatype, version, " + \
                "last_modified, comment FROM config WHERE " +\
                "id=%s"
            cursor = self._execute(SQL, [param_id])
            row = cursor.fetchone()
            if not row:
                raise NoSuchParameterException("parameter number: %s"%param_id)

            id, parent_id, name, value, datatype, version, timestamp, comment = row

            parent_ids = []

            if recursing:
                parent_info = self.get_by_id(parent_id, recursing=True)
                return parent_info + [(id, name)]

            parent_info = self.get_by_id(parent_id, recursing=True)

            path = ""
            parent_ids = []
            for (parent_id, parent_name) in parent_info:
                path += parent_name + "."
                parent_ids.append(parent_id)
            path = path + name

            cp = ConfigParameter(id, name, parent_ids, path, 
                                 datatype, value,  
                                 version, timestamp, config=self, 
                                 comment=comment)

            if cp.datatype == "folder":
                timestamp, cp.children = self._get_children(cp)
                cp.set_last_modified(timestamp)
            return cp

    def get(self, _full_path, version=None, version_id=None, 
            absolute_path=False):
        """
        Get a parameter. Throws NoSuchParameterException if not found
        
        If version is specified, only matches are returned
        if version_id is specified, no text-to-id lookup is performed.
        if absolute_path is True, no root is added to the _full_path
        """
        with self._load_lock:
            if not absolute_path:
                full_path = self._get_full_path(_full_path)
            else:
                full_path = _full_path
            if DEBUG:
                logger.debug("get(%s)"%full_path)
            if version_id:
                version = version_id
            else:
                if not version:
                    version = self._cfg["version"]
                else:
                    version = self._get_version_id(version)

            if full_path.count(".") == 0:
                name = full_path
                path = ""
                parent_ids = [0]
            else:
                (path, name) = full_path.rsplit(".", 1)

            if full_path != "root" and full_path != "": # special case for root node
                parent_ids = self._get_parent_ids(full_path, version, create=False)

                # Find the thingy
                SQL = "SELECT id, value, datatype, version, " + \
                    "last_modified, comment FROM config WHERE " +\
                    "name=%s AND parent=%s"
                params = [name, parent_ids[-1]]
                if version != ANY_VERSION:
                    SQL += " AND version=%s"
                    params.append(version)

                cursor = self._execute(SQL, params)
                row = cursor.fetchone()
                if not row:
                    raise NoSuchParameterException(full_path)
                id, value, datatype, version, timestamp, comment = row

                cp = ConfigParameter(id, name, parent_ids, path, 
                                     datatype, value,  
                                     version, timestamp, config=self, 
                                     comment=comment)
            else:
                cp = ConfigParameter(0, "root", [0], "", 
                                     "folder", "", version, None, config=self)

            if cp.datatype == "folder":
                timestamp, cp.children = self._get_children(cp)
                cp.set_last_modified(timestamp)

            return cp

    def _get_children(self, config_parameter):

        SQL = "SELECT id, name, value, datatype, version, " + \
            "last_modified, comment FROM config WHERE " +\
            "parent=%s AND version=%s ORDER BY name"
        cursor = self._execute(SQL, [config_parameter.id,
                                     config_parameter.version])

        parent_ids = config_parameter.parents + [config_parameter.id]
        path = config_parameter.get_full_path()
        res = []
        import datetime
        my_timestamp = datetime.datetime(1970,1,1)
        for id, name, value, datatype, version, timestamp, comment in cursor.fetchall():
            res.append(ConfigParameter(id, name, parent_ids, path, 
                                       datatype, value, version, timestamp,
                                       config=self, comment=comment))
            my_timestamp = max(timestamp, my_timestamp)

        return my_timestamp, res
        
    def _get_datatype(self, value):
        if not value:
            datatype = "string"
            
        elif value.__class__ == float:
            datatype = "double"
        elif value.__class__ == int:
            datatype = "integer"
        elif value.__class__ == long:
            datatype = "integer"
        elif value.__class__ == bool:
            datatype = "boolean"
            value = str(value)
        elif value.isdigit():
            datatype = "integer"
        elif value.count(".") == 1 and value.replace(".", "").isdigit():
            datatype = "double"
        elif value.lower() in ["true", "false"]:
            datatype = "boolean"
        else:
            datatype = "string"
        return datatype

    def remove(self, full_path, version=None):
        
        with self._load_lock:
            param = self.get(full_path, version)
            # Delete it
            SQL = "DELETE FROM config WHERE id=%s AND version=%s"
            self._execute(SQL, [param.get_id(), param.get_version()])

            print SQL, str([param.get_id(), param.get_version()])
            print "OK"

    def add(self, _full_path, value=None, datatype=None, comment=None, 
            version=None, 
            parent_id=None, overwrite=False, version_id=None):
        """
        Add a new config parameter. If datatype is not specified,
        we'll guess.  If version is not specified, the current version
        is used.
        """

        with self._load_lock:
            full_path = self._get_full_path(_full_path)

            assert full_path

            if full_path.count(".") == 0:
                name = full_path
            else:
                (path, name) = full_path.rsplit(".", 1)

            if version_id:
                version = version_id
            elif not version:
                version = self._cfg["version"]
            else:
                version = self._get_version_id(version)

            if DEBUG:
                logger.debug("Add (" + str(full_path) + ", " + str(value) + ", " + str(datatype) + ", " + str(version) + ")")
            if not parent_id:
                parent_ids = self._get_parent_ids(full_path, version)
                parent_id = parent_ids[-1]

            # Determine datatype
            if not datatype:
                datatype = self._get_datatype(value)

            if overwrite:
                SQL = "REPLACE"
            else:
                SQL = "INSERT"
            if datatype == "boolean":
                value = str(value)
            SQL += " INTO config (version, parent, name, value, datatype, comment) VALUES (%s, %s, %s, %s, %s, %s)"
#             logger.debug(SQL + " (" + str((version, parent_id, name, value, datatype)) + ")");
            self._execute(SQL, (version, parent_id, name, value, datatype, comment))

    def _clean_up(self):
        """
        Remove any parameters that are "lost", i.e. their parent is missing
        """
        with self._load_lock:            
            # Clean up missing children now
            SQL = "SELECT config.id, config.name, parent.id FROM config LEFT OUTER JOIN config AS parent ON config.parent=parent.id WHERE parent.id IS NULL AND config.parent<>0"
            cursor = self._execute(SQL)
            params = []
            for row in cursor.fetchall():
                logger.warning("DELETING PARAMETER %s - lost due to overwrite"%(row[1]))
                params.append(row[0])
            if len(params) > 0:
                SQL = "DELETE FROM config WHERE "
                SQL += "ID=%s OR "*len(params)
                SQL = SQL[:-4]
                self._execute(SQL, params)
                
    def set(self, _full_path, value, version=None, datatype=None, comment=None, version_id=None, absolute_path=False):
        
        with self._load_lock:
            if version and not version_id:
                version_id = self._get_version_id(version)

            param = self.get(_full_path, version_id=version_id, absolute_path=absolute_path)
            if DEBUG:
                logger.debug("Updating parameter %s to %s (type: %s)" % (_full_path, value, datatype))

            if comment != None:
                param.set_comment(comment)
            param.set_value(value, datatype=datatype)
            self.commit(param)

    def commit(self, config_parameter):
        """
        Commit an updated parameter to the database
        """
        
        with self._load_lock:
            # Integrity check?
            error = False
            if config_parameter.value:
                dt = self._get_datatype(config_parameter.value) 
                if config_parameter.datatype in ["double", "float"]:
                    if dt not in ["float", "double", "integer"]: 
                        error = True
                elif dt != config_parameter.datatype:
                    error = True
                if error:
                    raise Exception("Refusing to save inconsistent datatype for config parameter %s=%s. Datatype of parameter is '%s' but type of value is '%s'."%(config_parameter.name, config_parameter.value, config_parameter.datatype, dt))

            SQL = "UPDATE config SET value=%s,datatype=%s,comment=%s WHERE id=%s AND parent=%s AND version=%s"
            cursor = self._execute(SQL, [config_parameter.value,
                                         config_parameter.datatype,
                                         config_parameter.comment,
                                         config_parameter.id,
                                         config_parameter.parents[-1],
                                         config_parameter.version])
        

    def get_leaves(self, _full_path=None, absolute_path=False):
        """
        Recursively return all leaves of the given path
        """
        with self._load_lock:
            param = self.get(_full_path, absolute_path=absolute_path)
            leaves = []
            folders = []
            for child in param.children:
                if child.datatype == "folder":
                    folders.append(child)
                else:
                    leaves.append(child.get_full_path()[len(self.root):])

            for folder in folders:
                leaves += self.get_leaves(folder.get_full_path(),
                                          absolute_path = True)

            return leaves

    def keys(self, path=None):
        with self._load_lock:
            param = self.get(path)
            leaves = []
            for child in param.children:
                leaves.append(child.name)
            return leaves

    def get_version_info_by_id(self, version_id):
        """
        Return a map of version info
        """
        with self._load_lock:
            SQL = "SELECT name, device, comment FROM config_version WHERE id=%s"
            cursor = self._execute(SQL, [version_id])
            row = cursor.fetchone()
            if not row:
                raise NoSuchVersionException("ID: %s"%version_id)
            name, device, comment = row
            return {"name": name,
                    "device": device,
                    "comment": comment}

    def _serialize_recursive(self, root, version_id):
        """
        Internal, recursive function for serialization
        """
        
        param = self.get(root, version_id=version_id, absolute_path=True)
        children = []
        for child in param.children:
            children.append(self._serialize_recursive(child.get_full_path(),
                                                      version_id))
        serialized = {"name":param.name,
                      "value":param.value,
                      "datatype":param.datatype,
                      "comment":param.comment,
                      "last_modified":param.last_modified}
        for child in children:
            serialized[child["name"]] = child
        return serialized


    def _deserialize_recursive(self, serialized, root, version_id, 
                               overwrite=False):
        """
        Internal, recursive function for deserialization
        """
        if not serialized or serialized.__class__ != dict:
            #print root, serialized.__class__
            return

        if "value" in serialized:
            #print "%s: %s (%s) [%s]"%(root, serialized["value"], serialized["datatype"], serialized["comment"])
            if root and root != "root":
                if overwrite:
                    try:
                        self.set(root, 
                                 serialized["value"], 
                                 serialized["datatype"],
                                 comment=serialized["comment"],
                                 version_id=version_id)
                    except NoSuchParameterException, e:
                        logger.exception("Must create new parameter %s version %s"%(root, version_id))
                        # new parameter, add it
                        self.add(root, serialized["value"], 
                                 serialized["datatype"],
                                 comment=serialized["comment"],
                                 version_id=version_id, overwrite=overwrite)
                else:
                    self.add(root, serialized["value"], serialized["datatype"],
                             comment=serialized["comment"],
                             version_id=version_id, overwrite=overwrite)

        for elem in serialized.keys():
            if elem in ["name", "datatype", "comment", "last_modified"]:
                continue

            path = root + "." + elem
            self._deserialize_recursive(serialized[elem], path, version_id, 
                                        overwrite)
            

    ###################    JSON functionality for (de)serializing ###
    
    def serialize(self, root = "", version=None):
        """
        Return a JSON serialized block of config
        """
        with self._load_lock:
            if version:
                version_id = self._get_version_id(version)
            else:
                version_id = self._cfg["version"]

            version_info = self.get_version_info_by_id(version_id)
            root = self._get_full_path(root)
            serialized = self._serialize_recursive(root, version_id) 
            if not root:
                root = "root"
            serialized = { root: serialized,
                           "version": version_info}

            return json.dumps(serialized, indent=1)


    def deserialize(self, serialized, root="", version=None, overwrite=False):
        """
        Parse a JSON serialized block of config
        """

        with self._load_lock:
            if version:
                version_id = self._get_version_id(version)
            else:
                version_id = self._cfg["version"]

            version_info = self.get_version_info_by_id(version_id)
            if not root:
                root = "root"
            cfg = json.loads(serialized)

            # Clear caches
            self._id_cache = {}
            self._version_cache = {}
            
            if DEBUG:
                logger.debug("Deserialize %s from device %s (%s) into config version %s"% \
                (cfg["version"]["name"],
                 cfg["version"]["device"],
                 cfg["version"]["comment"],
                 version))
            self._deserialize_recursive(cfg[root], root, version_id, overwrite)
            
            self._clean_up()
        
    
    ####################   Quick functions   ####################
    def __setitem__(self, name, value):
        try:
            self.set(name, value)
        except NoSuchParameterException:
            # Create it
            self.add(name, value)
            
    def __getitem__(self, name):
        try:
            val = self.get(name).get_value()
            if val.__class__ == unicode:
                return val.encode("utf-8")
            return val
        except:
            return None

    def set_default(self, name, value, datatype=None):
        # Check if the root of this thing exists
        try:
            self.keys()
        except:
            # Missing root!
            raise Exception("Missing root %s for '%s'"%(self.root, name))

        try:
            self.get(name)
        except:
            self.add(name, value, datatype=datatype)
        
    def require(self, param_list):
        """
        Raise a NoSuchParameterException if any of the parameters are not
        available
        """
        with self._load_lock:
            # This could be done faster, but who cares
            for param in param_list:
                self.get(param)

    ################  Callback management ##################
    def _callback_thread_main(self):
        if DEBUG:
            logger.debug("Callback thread started")

        while not self._internal_stop_event.is_set() and not self.stop_event.is_set():
            try:
                time.sleep(0.25)
                SQL = "SELECT config_callback.id, config_callback.param_id, name, value, config.last_modified+1 FROM config, config_callback WHERE config.id=config_callback.param_id AND config_callback.last_modified<config.last_modified"
                cursor = self._execute(SQL)
                logger.debug("Checking for callbacks")
                for cb_id, param_id, name, value, last_modified in cursor.fetchall():
                    logger.debug("Updated callback for %s"%param_id)
                    try:
                        with self._cb_lock:
                            if not (cb_id, param_id) in self._update_callbacks:
                                logger.error("Requested callback '%s' (%s) that no longer exists: %s"%(name, str((cb_id, param_id)), str(self._update_callbacks)))
                                continue
                            (func, args) = self._update_callbacks[(cb_id, param_id)]
                            param = self.get_by_id(param_id)
                            if not param:
                                raise Exception("INTERNAL: Got update on deleted parameter %d"%param_id)

                        print "Executing callback %s(%s == %s)"%(func, param.get_name(), param.get_value())
                        if args:
                            print "Callback with args"
                            func(param, *args)
                        else:
                            func(param)
                    except Exception, e:
                        print "CALLBACK EXCEPTION:",e
                        logger.exception("In callback handler")

                    self._execute("UPDATE config_callback SET last_modified=%s WHERE id=%s and param_id=%s", [last_modified, cb_id, param_id])


#                time.sleep(0.5) # TODO: Config this
            except:
                logger.exception("INTERNAL: Callback handler crashed badly")

    def del_callback(self, callback_id):
        
        cursor = self._execute("DELETE FROM config_callback WHERE id=%s",
                               [callback_id])
        #dir(cursor)
        
        with self._cb_lock:
            for (cb_id, param_id) in self._update_callbacks.keys()[:]:
                del self._update_callbacks[(cb_id, param_id)]
                
        
    def add_callback(self, parameter_list, func, version=None, *args):
        """
        Add a callback for the given parameters
        """
        
        if not self.stop_event:
            raise Exception("Require a stop_event to the configuration instance to allow callbacks")
        
        if not func:
            raise Exception("Refusing to add callback without a function")
        
        if version:
            version_id = self._get_version_id(version)
        else:
            version_id = self._cfg["version"]

        import random
        callback_id = random.randint(0, 0xffffff)

        if not self._cb_thread:
            self._cb_thread = threading.Thread(target=self._callback_thread_main)
            self._cb_thread.start()
        
        for param in parameter_list:
            param = self.get(param, version_id=version_id)

            # Add to the database as callbacks
            SQL = "INSERT INTO config_callback (id, param_id, last_modified) SELECT " + str(callback_id) + ", id, last_modified FROM config WHERE id=%s"
            cursor = self._execute(SQL, [param.id])
            with self._cb_lock:
                self._update_callbacks[(callback_id, param.id)] = (func, args)
            if DEBUG:
                logger.debug("Added callback (%s,%s): %s"%\
                                   (callback_id, param.id,
                                    str((func, args))))
            
        return callback_id
            
        
