import CompatThreading as threading
import MySQLdb
import warnings
from time import time

from src.database.API import get_config
from src.logger import get_logger

logger = get_logger(__name__)

DEBUG=False

# For debugging only
global NUMCONNS
NUMCONNS = 0

class mysql:
    """
    This class provides bits that are needed to access mysql.

    The config:
    db_name: Name of the DB to use
    db_user: user
    db_password: password
    db_host: database host, default localhost
    
    You can now run self._execute(sql, params) which returns a cursor.
    This class is threadsafe too.
    
    If you provide a db_name to the init function, it will override
    any config for that exact parameter
    
    """

    def __init__(self, name, config=None, can_log=True, db_name = None):
        """
        Generic database wrapper
        if can_log is set to False, it will not try to log (should
        only be used for the logger!)
        """
        self._db_name = db_name
        self.name = name
        self.cfg = config
        #print " *** Getting default config object"
        self._default_cfg = get_config("System.InternalDB")
        #print " *** Checking required parameters"
        self._default_cfg.require(["db_user", "db_name", "db_host", "db_password"])
        #print "Default params OK"

        self.db_connections = {}
        self._db_lock = threading.Lock()

    def __del__(self):
        
        with self._db_lock:
            for c in self.db_connections.values():
                try:
                    c.commit()
                except:
                    pass

    def _init_sqls(self, sql_statements):
        """
        Prepare the database with the given SQL statements (statement, params)
        Errors are ignored for indexes, warnings are logged and not sent
        to the console
        """
        
        with warnings.catch_warnings():
            warnings.simplefilter('error', MySQLdb.Warning)
            for statement in sql_statements:
                try:
                    if statement.lower().startswith("create index"):
                        ignore_error = True
                    else:
                        ignore_error = False
                    self._execute(statement, ignore_error=ignore_error)
                except MySQLdb.Warning, e:
                    if logger:
                        logger.warning("Preparing table '%s': %s"%\
                                             (statement, e))
        
    def close_connection(self):
        with self._db_lock:
            thread_name = threading.currentThread().ident #getName()
            if self.db_connections.has_key(thread_name):
                try:
                    self.db_connections[thread_name].close()
                except:
                    pass
                del self.db_connections[thread_name]
                global NUMCONNS
                NUMCONNS -= 1
                if DEBUG:
                    if logger:
                        logger.debug("Closing connection for %s (Total connections: %d)"%(thread_name, NUMCONNS))

    def _get_cursor(self, temporary_connection=False):
        
        return self._get_conn(temporary_connection).cursor()
        #return self._get_conn(temporary_connection)[1]|

    def _get_db(self, temporary_connection=False):
        #return self._get_conn(temporary_connection)[0]
        return self._get_conn(temporary_connection)

    def _get_conn_cfg(self):
        cfg = {"db_name": self._default_cfg["db_name"],
               "db_host": self._default_cfg["db_host"],
               "db_user": self._default_cfg["db_user"],
               "db_password": self._default_cfg["db_password"]}

        # Override defaults
        for elem in ["db_name", "db_host", "db_user", "db_password"]:
            if self.cfg and self.cfg[elem]:
                cfg[elem] = self.cfg[elem]
        
        if self._db_name:
            cfg["db_name"] = self._db_name
        return cfg

    def _get_conn(self, temporary_connection=False):
        if temporary_connection:
            global NUMCONNS
            NUMCONNS += 1
            cfg = self._get_conn_cfg()
            conn = MySQLdb.connect(host=cfg["db_host"],
                                   user=cfg["db_user"],
                                   passwd=cfg["db_password"],
                                   db=cfg["db_name"],
                                   use_unicode=True,
                                   charset="utf8")
            conn.autocommit(1)
            return (conn, conn.cursor())

        with self._db_lock:
            thread_name = threading.currentThread().ident #getName()
            if not self.db_connections.has_key(thread_name):

                global NUMCONNS
                NUMCONNS += 1
                cfg = self._get_conn_cfg()
                conn = \
                    MySQLdb.connect(host=cfg["db_host"],
                                    user=cfg["db_user"],
                                    passwd=cfg["db_password"],
                                    db=cfg["db_name"],
                                    use_unicode=True,
                                    charset="utf8")
                conn.autocommit(1)

                if DEBUG:
                    if logger:
                        logger.debug("New db connection for thread %s, total is now %d (%d)"%(thread_name, len(self.db_connections), NUMCONNS))
                    else:
                        print "New db connection for thread %s, total is now %d"%(thread_name, len(self.db_connections))

                #self.db_connections[thread_name] = (conn, conn.cursor())
                self.db_connections[thread_name] = conn

            return self.db_connections[thread_name]
        
    def _execute(self, SQL, parameters=[], temporary_connection=False, 
                 ignore_error=False, commit=True,
                 log_errors=True):
        """
        Execute an SQL statement with the given parameters.  

        The SQL statement works fine if you use "?", sqlite style, e.g.
        "INSERT INTO table VALUES (?,?,?)".  Parameters will then be escaped
        automatically.
        """
        # Must convert SQL + parameters to a valid SQL statement string
        # REALLY???
        # TODO: ESCAPE PROPERLY HERE
        #SQL = SQL.replace("?", "'%s'")
        SQL = SQL.replace("?", "%s")
        #SQL = SQL % tuple(parameters)
        #parameters = ()
        conn = None
        if DEBUG:
            if logger:
                logger.debug("SQL %s(%s)"%(SQL, str(parameters)))
            else:
                print "SQL %s(%s)"%(SQL, str(parameters))

        with warnings.catch_warnings():
            warnings.simplefilter('error', MySQLdb.Warning)

            while True:
                try:
                    cursor = self._get_cursor(temporary_connection=temporary_connection)
                    #cursor = conn.cursor()
                    if len(parameters) > 0:
                        cursor.execute(SQL, tuple(parameters))
                    else:
                        cursor.execute(SQL)
                    return cursor
                except MySQLdb.Warning, e:
                    if logger and log_errors:
                        logger.warning("Warning running '%s(%s)': %s"%\
                                             (SQL, str(parameters), e))
                    return

                except MySQLdb.OperationalError,e:
                    
                    # If we lost the connection to the DB, drop the connection
                    # and retry
                    # TODO: THIS IS REALLY, REALLY UGLY!
                    if str(e).startswith("(2002, "):
                        # Mysql is not running
                        print "MySQL not responding, trying again in 1 second"
                        time.sleep(1.0)
                        continue
                    if str(e).startswith("(20"):
                        # Lost connection (Mysql server has gone away or some other badness, closing connection)
                        self.close_connection()
                        continue
                            
                    if ignore_error:
                        return

                    print "%s: Got operational error: %s"%\
                        (self.__class__, str(e))

                    if logger and log_errors:
                        logger.exception("Got an operational error during sql operation")
                    raise e

                except Exception,e:
                    print "Exception:", SQL, str(parameters), e.__class__, e
                    if logger and log_errors:
                        logger.exception("Got an error during sql operation: '%s'"%e)
                        logger.fatal("SQL was: %s %s"% (SQL, str(parameters)))
                    raise e
