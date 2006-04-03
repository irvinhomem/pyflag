# ******************************************************
# Copyright 2004: Commonwealth of Australia.
#
# Developed by the Computer Network Vulnerability Team,
# Information Security Group.
# Department of Defence.
#
# Michael Cohen <scudette@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG  $Version: 0.80.1 Date: Tue Jan 24 13:51:25 NZDT 2006$
# ******************************************************
#
# * This program is free software; you can redistribute it and/or
# * modify it under the terms of the GNU General Public License
# * as published by the Free Software Foundation; either version 2
# * of the License, or (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# ******************************************************

""" This module contains db related functions """
import MySQLdb
import pyflag.conf
config=pyflag.conf.ConfObject()
import pyflag.logging as logging
import time,types
import threading
from Queue import Queue, Full, Empty

db_connections=0

def escape(string):
    return MySQLdb.escape_string(string)

class DBError(Exception):
    """ Generic Database Exception """
    pass

class DBExpander:
    """ A utility class for interpolating into the query string.

    This class implements the correct interpolation so that %s is not escaped and %r is escaped in the mysql interpolation.

    @Note: We cant use the MySQLdb native interpolation because it has a brain dead way of interpolating - it always escapes _ALL_ parameters and always adds quotes around anything. So for example:

    >>> MySQLdb.execute('select blah from %s where id=%r',table,id)

    Does not work as it should, since the table name is always enclosed in quotes which is incorrect.
    """
    def __init__(self,string):
        self.string = str(string)

    def __str__(self):
        return self.string

    def __repr__(self):
        return "'%s'"% MySQLdb.escape_string(self.string)

class Pool(Queue):
    """ Pyflag needs to maintain multiple simulataneous connections to
    the database sometimes.  To avoid having to reconnect on each
    occasion, we keep a pool of connection objects. This allows
    connections to be placed back in the pool after DBO destruction
    for reuse by other DBOs.
    
    Note that since we use the Queue class we are thread safe
    here. I.e. we guarantee that the same connection will never be
    shared by two different threads.

    Note that connections are not placed back on the queue until all
    references to them are GCed. This means that we still need to be
    relatively concervative in creating new DBOs and prefer to reuse
    existing ones whenever possible (of course we need to create new
    ones if the connection state is important (e.g. iterating through
    a resultset while doing some different db activity).
    """
    def __init__(self, case, poolsize=0):
        self.case=case
        Queue.__init__(self, poolsize)

    def get(self, block=1):
        """Get an object from the pool or a new one if empty."""
        try:
            return self.empty() and self.connect() or Queue.get(self, block)
        except Empty:
            return self.connect()

    def connect(self):
        """ Connect specified case and return a new connection handle """
        global db_connections
        db_connections +=1
        logging.log(logging.VERBOSE_DEBUG, "New Connection to DB. We now have %s in total" % (db_connections, ))
        
        case=self.case
        try:
            #Try to connect over TCP
            dbh = MySQLdb.Connect(user = config.DBUSER, passwd = config.DBPASSWD,db = case, host=config.DBHOST, port=config.DBPORT)
            mysql_bin_string = "%s -f -u %r -p%r -h%s -P%s" % (config.MYSQL_BIN,config.USER,config.PASSWD,config.HOST,config.PORT)
        except Exception,e:
            #or maybe over the socket?
            dbh = MySQLdb.Connect(user = config.DBUSER, passwd = config.DBPASSWD,db = case, unix_socket = config.DBUNIXSOCKET)
            mysql_bin_string = "%s -f -u %r -p%r -S%s" % (config.MYSQL_BIN,config.DBUSER,config.DBPASSWD,config.DBUNIXSOCKET)

        return (dbh,mysql_bin_string)

global DBH
DBH={}

class DBO:
    """ Class controlling access to DB handles

    We implement a pool of connection threads. This gives us both worlds - the advantage of reusing connection handles without running the risk of exhausting them, as well as the ability to issue multiple simultaneous queries from different threads.

    @cvar DBH: A dict containing cached database connection objects
    @cvar lock: an array of unique locks that each thread must hold before executing new SQL
    @ivar temp_tables: A variable that keeps track of temporary tables so they may be dropped when this object gets gc'ed
    """
    temp_tables = []
    
    def __init__(self,case=None):
        """ Constructor for DB access. Note that this object implements database connection caching and so should be instantiated whenever needed. If case is None, the handler returned is for the default flag DB

        @arg case: Case database to connect to. May be None in which case it connects to the default flag database
        """
        if not case:
            case = config.FLAGDB

        try:
            self.dbh,self.mysql_bin_string=DBH[case].get()
        except KeyError:
            DBH[case] = Pool(case)
            self.dbh,self.mysql_bin_string=DBH[case].get()
            
        self.temp_tables = []
        self.case = case
        self.cursor = self.dbh.cursor()
                
    def clone(self):
        """ Returns a new database object for the same case database """
        return self.__class__(self.case)

    def execute(self,query_str,params=None):
        """  SQL execution method.
               This functions executes the SQL in this object's cursor context. the query must be given as a string with with %s or %r escape characters, and the correct number of strings in the params list.

               @note: Just as a reminder - using %r will escape the corresponding string in a manner that is adequate for mysql, it will also automatically insert quotes around the string. On the other hand using %s will not escape the strings.
               
               >>> a.execute('select * from %s where id=%r' , ('table','person'))
                       
               @arg query_str: A format string with only %r and %s format sequences
               @arg params: A list of strings which will be formatted into query_str. If there is only one format string and the programmer is truely lazy, a string is ok. """

        if params==None:
            string = query_str
        else:
            try:
                ## We only do this if the params are truely iteratable
                params.__getattribute__('__iter__')
            ## Hopefully this does not bear a huge performance overhead???
                params = tuple([ DBExpander(i) for i in params])
            except AttributeError:
                params=(DBExpander(params),)

            string= query_str % params
            
        try:
            self.cursor.execute(string,None)
        #If anything went wrong we raise it as a DBError
        except Exception,e:
            str = "%s" % e
            if not str.startswith('Records'):
                raise DBError,e


    def commit(self):
        self.cursor.connection.commit()

    def __iter__(self):
        return self

    def mass_insert_start(self, table):
        self.mass_insert_cache = {}
        self.mass_insert_table = table
    
    def mass_insert(self, **columns):
        """ Starts a mass insert operation. When done adding rows, call commit_mass_insert to finalise the insert.
        """
        for k,v in columns.items():
            try:
                self.mass_insert_cache[k].append(v)
            except:
                self.mass_insert_cache[k] = [ v, ]

        ## If the transaction is too large, we need to commit it and restart:
        if len(self.mass_insert_cache[k]) > 100:
            self.mass_insert_commit()
            self.mass_insert_start(self.mass_insert_table)

    def mass_insert_commit(self):
        keys = self.mass_insert_cache.keys()
        if len(keys)==0: return
        
        args = []
        values = []
        for i in range(len(self.mass_insert_cache[keys[0]])):
            for k in keys:
                args.append( self.mass_insert_cache[k][i])

            values.append(",".join(["%r"] * len(keys)))

        sql = "insert into %s (%s) values (%s)" % (self.mass_insert_table,
                                                   ','.join(["`%s`" % c for c in keys]),
                                                   "),(".join(values))
        self.execute(sql,args)


    def autoincrement(self):
        """ Returns the value of the last autoincremented key """
        self.execute("select LAST_INSERT_ID() as result")
        row=self.fetch()
        return row['result']

    def next(self):
        """ The db object supports an iterator so that callers can simply iterate over the result set.

        Each iteration returns a hash as obtained from fetch. """
        result = self.fetch()
        if not result: raise StopIteration

        return result

    def fetch(self):
        """ Returns the next cursor row as a dictionary.

        It is encouraged to use this function over cursor.fetchone to ensure that if columns get reordered in the future code does not break. The result of this function is a dictionary with keys being the column names and values being the values """
        results = {}
        temp = self.cursor.fetchone()
        temp2=[]
        if temp:
            for i in temp:
                try:
                    temp2.append(i.tostring())
                except AttributeError:
                    temp2.append(i)
                    pass
            temp = temp2
                            
        if not temp: return None
        
        column = 0
        for d in self.cursor.description:
            if results.has_key(d[0]): raise DBError, "Duplicate names in query heading"
            results[d[0]] = temp[column]
            column += 1

        return results

    def check_index(self, table, key, length=None):
        """ This checks the database to ensure that the said table has an index on said key.

        If an index is missing, we create it here, so we always ensure an index exists once we return. """
        ## We implement a local cache to ensure that we dont hit the DB all the time:
##        try:
##            return self.DBH[self.case].indexes["%s.%s" % (table,key)]
##        except KeyError:        
        if 1:
            self.execute("show index from `%s`",table)
            for row in self:
                if row['Key_name'] == key:
                    ## We found an index we are looking for
                    return

            if length:
                sql="(`%s`(%s))" % (key,length)
            else:
                sql="(`%s`)" % (key) 

            logging.log(logging.DEBUG,"Oops... No index found in table %s on field %s - Generating index, this may take a while" %(table,key))
            ## Index not found, we make it here:
            self.execute("Alter table `%s` add index%s",(table,sql))

            ## Add to cache:
##            self.DBH[self.case].indexes["%s.%s" % (table,key)] = True
        
    def get_meta(self, property, table='meta',**args):
        """ Returns the value for the given property in meta table selected database

        Only returns first value """
        self.execute("select value from `%s` where property=%r",
                     (table,property))
        row = self.fetch()
        print "row %s: %s" % (property, row)
        if row != None:
            return row['value']
        return None

    def set_meta(self, property,value, table='meta', **args):
        """ Sets the value in meta table
        """
        row = self.get_meta(property)
        if row:
            self.execute("update `%s` set property=%r,value=%r,%s where property=%r",
                         (table, property,value, property))
        else:
            self.execute("insert into `%s` set property=%r,value=%r", (table, property,value))

    def MakeSQLSafe(self,string):
        """ Returns a version of string, which is SQL safe.

        String will be converted to a form which is suitable to be used as the name of a table for example.
        """
        import re
        return re.sub('[^a-zA-Z0-9]','_',string)

    def get_temp(self):
        """ Gets a unique name for a table.

        This can be used to create temporary tables - since flag is multi-threaded, temporary tables remain within the same thread. Use this function to get names for temporary tables.

        Note that each DBO object maintains a list of temporary tables, and drops those when gc'd so users of this class do not need to clean temporary tables up.

        The result from this function is guaranteed to exist - so a create temporary table (or even a create table) call should work.
        """
        thread_name = threading.currentThread().getName()
        thread_name = thread_name.replace('-','_')
        count = 1

        while 1:
            test_name = "temp%s_%u" % (thread_name,count)
            ## Check if the table already exists:
            self.execute('show table status like %r',test_name)
            rs = self.dbh.cursor.fetchone()
            if not rs:
                self.temp_tables.append(test_name)
                return test_name

            count+=1

    def __del__(self):
        """ Destructor that gets called when this object is gced """
        try:
            for i in self.temp_tables:
                self.execute('drop table if exists %s' % i)

            DBH[self.case].put((self.dbh, self.mysql_bin_string))
        except (TypeError,AssertionError):
            pass

    def MySQLHarness(self,client):
        """ A function to abstact the harness pipes for all programs emitting SQL.

        @arg client: A string of the command to shell out to.
        @arg dbh: The database handle to use.
        """
        if not client.startswith('/'):
            client = "%s/%s" % (config.FLAG_BIN, client)
            
        logging.log(logging.DEBUG, "Will shell out to run %s " % client)

        import os
        p_mysql=os.popen("%s -D%s" % (self.mysql_bin_string,self.case),'w')
        p_client=os.popen(client,'r')
        while 1:
            data= p_client.read(1000)
            if not data: break
            p_mysql.write(data)

        if not p_client.close():
            pass
    #        raise IOError("Client program exited with a non-zero exit code")
        if not p_mysql.close():
            pass
    #        raise IOError("MySQL client exited with an error")
