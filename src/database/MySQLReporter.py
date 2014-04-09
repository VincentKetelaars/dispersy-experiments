from src.database import API, InternalDB
from src.database import Status
from src.logger import get_logger

logger = get_logger(__name__)

DEBUG=False

class MySQLStatusReporter(Status.OnChangeStatusReporter, InternalDB.mysql):

    def __init__(self, name = "System.Status.MySQL"):
        """
        Log messages to a database on change
        """
        Status.OnChangeStatusReporter.__init__(self, name)
        self.name = name
        self.cfg = API.get_config(name)
        InternalDB.mysql.__init__(self, "MySQLStatusReporter", self.cfg)
        self._prepare_db()
        self.cachedCursor	= None

        self._channels = {}
        self._parameters = {}

    def _prepare_db(self):
        """
        This function will prepare the db for a first utilisation
        It will create tables if needed
        """
        
        # Check if the status table is "old" and must be deleted first"
        try:
            self._execute("SELECT paramid FROM status LIMIT 1")
        except:
            logger.warning("Status database must be updated, clearing old status")
        try:
            self._execute("DROP TABLE status")
        except:
            pass

        statements = [""" CREATE TABLE IF NOT EXISTS status_channel (
                      chanid INTEGER PRIMARY KEY AUTO_INCREMENT,
                      name VARCHAR(256) UNIQUE) ENGINE=MyISAM""",

                      """CREATE TABLE IF NOT EXISTS status_parameter (
                      paramid INTEGER PRIMARY KEY AUTO_INCREMENT,
                      name VARCHAR(128),
                      chanid INTEGER NOT NULL,
                      UNIQUE KEY uid (name,chanid)) ENGINE=MyISAM""", 

                      """CREATE TABLE IF NOT EXISTS status  (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            timestamp DOUBLE,
            paramid INTEGER REFERENCES status_parameter(paramid),
            chanid INTEGER REFERENCES status_channel(chanid),
            value VARCHAR(128)
            ) ENGINE=MyISAM""",
                      "CREATE INDEX stat_time ON status(timestamp)",
                      "CREATE INDEX stat_chanid ON status(chanid)",
                      "CREATE INDEX stat_paramid ON status(paramid)"]
        self._init_sqls(statements)

    def _update_event_ids(self, event):
        """
        Update DB ID's for this event
        """
        if not event._db_channel_id:
            holder_name = event.status_holder.get_name()
            if not holder_name in self._channels.keys():
                SQL = "SELECT chanid FROM status_channel WHERE name=%s"
                cursor = self._execute(SQL, [holder_name])
                row = cursor.fetchone()
                if not row:
                    # Must insert
                    if DEBUG:
                        logger.debug("New channel '%s'" % holder_name)
                    self._execute("INSERT INTO status_channel(name) VALUES (%s)",
                                  [holder_name])
            
                    return self._update_event_ids(event) # Slightly dangerous, but should be OK as exceptions will break it
                self._channels[holder_name] = row[0]

            event._db_channel_id = self._channels[holder_name]
        
        if not event._db_param_id:
            param_name = event.get_name()
            if not (event._db_channel_id, param_name) in self._parameters.keys():
                SQL = "SELECT paramid FROM status_parameter WHERE name=%s AND chanid=%s"
                assert event.get_name()
                assert event._db_channel_id
                cursor = self._execute(SQL, [param_name, event._db_channel_id])
                row = cursor.fetchone()
                if not row:
                    # Must insert
                    if DEBUG:
                        logger.debug("New status parameter '%s'"% param_name)
                    self._execute("INSERT INTO status_parameter(name, chanid) VALUES (%s, %s)",
                                  [param_name, event._db_channel_id])
                    return self._update_event_ids(event) # Slightly dangerous, but should be OK as exceptions will break it
                self._parameters[(event._db_channel_id, param_name)] = row[0]
            event._db_param_id = self._parameters[(event._db_channel_id, param_name)]

    def report(self, event):
        """
        Report to DB
        """
        try: 
            if not event._db_param_id or not event._db_channel_id:
                self._update_event_ids(event)
            assert event._db_param_id
            assert event._db_channel_id
        except:
            logger.exception("Could not resolve event ids for event %s %s", event.name, str(event))
            return

        try:
            SQL = "INSERT INTO status(timestamp, paramid, chanid, value) "\
                "VALUES (%s, %s, %s, %s)"
            if DEBUG:
                logger.debug("%s %s"%(SQL, str((event.get_timestamp(),
                                                  event._db_param_id,
                                                  event._db_channel_id,
                                                  str(event.get_value())))))
            params = (event.get_timestamp(), event._db_param_id, event._db_channel_id, str(event.get_value()))
            if 1 or self.cachedCursor == None:
                self.cachedCursor = self._execute(SQL, params)
            else:
                try:
                    self.cachedCursor.execute(SQL, params)
                except:
                    self.cachedCursor = None
                    self._execute(SQL, params)

        except Exception, e:
            logger.exception("Updating status information %s.%s"%(event.status_holder.get_name(), event.get_name()))
            
