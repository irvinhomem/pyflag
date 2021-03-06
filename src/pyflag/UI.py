#!/usr/bin/env python
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
#  Version: FLAG $Version: 0.87-pre1 Date: Thu Jun 12 00:48:38 EST 2008$
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

""" Main UI module.

The output within flag is abstracted such that it is possible to connect any GUI backend with any GUI Front end. This is done by use of UI objects. When a report runs, it will generate a UI object, which will be built during report execution. The report then returns the object to the calling framework which will know how to handle it. Therefore the report doesnt really know or care how the GUI is constructed """

import re,cgi,types,os,time,posixpath
import pyflag.FlagFramework as FlagFramework
import pyflag.DB as DB
from pyflag.DB import expand
import pyflag.conf
import pyflag.pyflaglog as pyflaglog
config=pyflag.conf.ConfObject()
import pyflag.parser as parser
import pyflag.Registry as Registry


config.LOG_LEVEL=7

class UIException(Exception): pass

class GenericUI:
    """ Baseclass for UI objects. Note that this is an abstract class which must be implemented fully by derived classes. This base class exists for the purpose of documentations. UI method prototypes should be added to this base class so they could be implemented in derived classes as well. """
    submit_string = 'Submit'

    def __init__(self,default = None):
        """Create a new UI object.
        Default is another UI object which we are basing this UI object on. In particular this new UI object and the default object share the same internal state variables, so that changes on one will affect the other. This is required for example when we are creating a temporary UI object inside an object which has a form in it. This way the new UI object can adjust the internal state of the form.
        """
        pass
    
    def __str__(self):
        """ A string description of this UI type. Probably needs to return a UI name """
        pass

    def pre(self,string):
        """ A paragraph formatting directive """
        pyflaglog.log(pyflaglog.DEBUG, "pre not implemented")

    def heading(self,string):
        """ Used for drawing a heading with a large font """
        pyflaglog.log(pyflaglog.DEBUG, "pre not implemented")

    def para(self,string,**options):
        """ Add a paragraph to the output """
        pyflaglog.log(pyflaglog.DEBUG, "para not implemented")

    def start_table(self,**options):
        """ Start a table. Note that all rows should have the same number of elements within a table """
        pyflaglog.log(pyflaglog.DEBUG, "start_table not implemented")

    def row(self,*columns, **options):
        """ Add a row to the table. If a table is not defined as yet, a new table is created. Column entries for the row should be given as a list of arguements. Options may be given as named pairs. Note that column objects may be strings or other UI entities.

        options is usually passed to the underlying implementation, but a number of keywords are understood by the UI:
              - type: heading - this row is the table's heading
              - colspan: The row has fewer elements than are needed, and the extra columns are to be filled with blanks.
        """
        pyflaglog.log(pyflaglog.DEBUG, "row not implemented")
    
    def newline(self):
        """ Add a new line"""
        pyflaglog.log(pyflaglog.DEBUG, "newline not implemented")
    
    def start_form(self,target, **hiddens):
        """ Creates a form. Target is a query_type object and is implemented as hidden fields. hiddens are name/value pairs of hidden parameter than should be passed. """
        pyflaglog.log(pyflaglog.DEBUG, "start_form not implemented")
        
    def end_table(self):
        """ End this table. This will cause the table to be drawn and a new table may be created """
        pyflaglog.log(pyflaglog.DEBUG, "end_table not implemented")
               
    def ruler(self):
        """ Draw a horizontal ruler """
        pyflaglog.log(pyflaglog.DEBUG, "ruler not implemented")
        
    def link(self,string,target=FlagFramework.query_type(()),**target_options):
        """ Create a link to somewhere else.

        A link is categorized by a list of named arguements, usually given as elements of query_type.
        Derived classes must make the link launch the correct part of the front end as specified by the link attributes """
        pyflaglog.log(pyflaglog.DEBUG, "link not implemented")
    
    def display(self):
        """ Main display method.

        Called when the framework is ready to display the UI object. Note that further operations on this UI are not defined once display is called. Note also that  the specific type of object returned here really depends on the implementation. The front-end should handle the return type appropriately

        This function in combination with the front end is expected to produce all the navigational aids required (e.g. nav bar or tool bars etc).
        """
        pyflaglog.log(pyflaglog.DEBUG, "display not implemented")

    def selector(self,description,name,sql,parms=None, key='key',
                 value='value', **options):
        """ Present a listbox selector based on sql. name is the target of the selector
        Note that the sql must produce two columns named key and value.
        """
        try:
            case = options['case']
            del options['case']
        except KeyError:
            case = None

        dbh = DB.DBO(case)
        keys=[]
        values=[]
        try:
            if parms:
                dbh.execute(sql,parms)
            else:
                dbh.execute(sql)
            for row in dbh:
                keys.append(row[key])
                values.append(row[value])

        ## If the SQL failed, we present an empty selector
        except DB.DBError,e:
            print e
            pass

        self.const_selector(description,name,keys,values,**options)

    def tz_selector(self,description,name,**options):
        """ Draws a timezone selector """
        timezones = [ 'SYSTEM', ]
        dbh = DB.DBO()
        dbh.execute('select name from mysql.time_zone_name where name like "posix/%"')
        for row in dbh:
            tz = row['name'][len("posix/"):]
            timezones.append(tz)

        self.const_selector(description, name, timezones, timezones, **options)

    def textfield(self,description,name,**options):
        """ Draws a textfield in a table row. """
        pyflaglog.log(pyflaglog.DEBUG, "textfield not implemented")
        
    def end_form(self,name):
        """ Called to end the form, possibly providing a submit button """
        pyflaglog.log(pyflaglog.DEBUG, "end_form not implemented")
        
    def hidden(self,name,value):
        """ Create a hidden parameter to be passed on form submission """
        pyflaglog.log(pyflaglog.DEBUG, "hidden not implemented")

    def clear(self):
        """ Clear the current object, as if it has not been drawn on """
        self.result=''

    def date_selector(self, description, name):
        self.textfield(description,name)
    
    def checkbox(self,description,name,value,**options):
        """ Create a checkbox input for the name,value pair given. """
        pyflaglog.log(pyflaglog.DEBUG, "checkbox not implemented")
        
    def filebox(self,dir=None,target="datafile",multiple="single"):
        """ Draws a file selector for all the files in directory dir.
        
        For security purposes, flag is unable to read files outside that directory.
        """
        pyflaglog.log(pyflaglog.DEBUG, "filebox not implemented")
    
    def case_selector(self,case='case',message='Case:', **options):
        """ Present a case selection box. Reports should call this method in their form in order to allow the user to specify the exact case to select. Note that a report may not need a case to operate on. """
        self.selector(message,case,'select value as `key`,value as `value` from meta where property=\'flag_db\'',(),**options)

    def meta_selector(self, case=config.FLAGDB,message='Select Value',property=None, **options):
        """ Present a selection box to select stuff from the meta table"""
        self.selector(message,property,'select value as `key`,value as `value` from meta where property=%r group by value',(property),case=case, **options)
        
    def tooltip(self,message):
        """ Renders the tooltip message each time the mouse hovers over this UI.

        The UI method may choose where the tooltip is displayed (for example it maybe more appropriate to show it on the status bar).
        """
        pyflaglog.log(pyflaglog.DEBUG, "tooltip not implemented")

    def make_link(self,query,target,target_format = None,**options):
        """ Makes a query_type object suitable for use in the links array of the table

        @note: the returned object is a clone of query.
        @note: Private ui parameters are automatically cleaned. e.g. limit, nextpage etc.
        @arg query: Original query to base the new object on
        @arg target: a string representing the name of the target
        @arg target_format: An optional format string that will be used to format the target arg for each cell in the table. There must be only one format specifier.
        """
        q = query.clone()
        del q[target]
        del q['__target__']
        del q['limit']
        del q['order']
        del q['dorder']
        for i in q.keys():
            if i.startswith('where_'):
                del q[i]
        
        q['__target__']=target
        if target_format:
            q[target]=target_format

        return q

    def FillQueryTarget(self,query,dest):
        """ Given a correctly formatted query (see table()), and a target, this function returns a query object with a filled in target

        @Note: FillQueryTarget makes a clone copy of query since it is altered quite heavily.
        @except KeyError: if the query is not formatted properly (i.e. no _target_ key)
        """
        #Need to clone because we will trash our local copy
        q = query.clone()
        for target in q.getarray('__target__'):
            try:
            ## Replace the target arg with the new one (note we cant just add one because that will append it to the end of a cgi array)
                tmp = str(q[target]) % dest
                del q[target]
                q[target] = tmp
            
            ## No q[target]
            except (KeyError,TypeError):
                del q[target]
                q[target] = dest

        try:
            ## If we were asked to mark this target, we do so here. (Note that __mark__ could still be set to a constant, in which case we ignore it, and its query_type.__str__ will fill it in)
            if q['__mark__']=='target':
                del q['__mark__']
                q['__mark__']=dest
        except KeyError:
            pass
            
        del q['__target__']
        return q

    def text(self,*cuts,**options):
        """ Adds the cuts to the current UI.

        Note that this widget may choose to implement the text as an editor widget or simply as a label. Repeated calls to this method could be made sequentially which should all end up in the same widget. This is not an editable UI element, see textfield if thats what you need.
        Supported keywork options: (defaults are in ())
              - color: A color to render this text widget in. Defaults: black
              - font: Font to render this widget in - can be (normal), bold, typewriter, small, large
              - wrap: How to wrap long lines, maybe full,(none) or word
              - sanitise: How much to sanitise the output. This probably only makes sense in the HTMLUI where output may be rendered incorrectly in the browser:
                     - Full: All tags are escaped
                     - (None): No sanitation is done
        """
        pyflaglog.log(pyflaglog.DEBUG, "text not implemented")
    
    def fileselector(self, description, name, vfs=True):
        """ Draws a file selector for files in the upload directory """
        from pyflag.ColumnTypes import IntegerType, TimestampType, \
             StringType, InodeIDType, FilenameType

        if self.defaults.has_key('select_all'):
            del self.defaults['select_all']
            self.refresh(0,self.defaults, pane='parent')

        def vfs_popup(query, result):
            if not query.has_key('case'):
                result.heading("No case selected")
            else:
                import pyflag.FileSystem as FileSystem
                def make_new_query(query, path=''):
                    case = query['case']
                    new_query = query.clone()
                    new_query['__target__'] = name
                    new_query['__target_type__'] = 'append'
                    new_query['__target_format__'] = "vfs://%s%s%%s" % (case,path)
                    new_query.poparray('callback_stored')
                    return new_query

                def tree_view_cb(query,result):
                    
                    def tree_cb(path):
                        fsfd = FileSystem.DBFS(query['case'])
                        query.default("path",'/')
                        if not path.endswith('/'): path=path+'/'
                        
                        dirs = []
                        for i in fsfd.dent_walk(path): 
                            if i['mode']=="d/d" and i['status']=='alloc' and i['name'] not in dirs:
                                dirs.append(i['name'])
                                yield(([i['name'],i['name'],'branch']))
                                
                    def pane_cb(path,tmp):
                        fsfd = FileSystem.DBFS( query["case"])
                        if not fsfd.isdir(path):
                            path=posixpath.dirname(path)

                        new_query = make_new_query(query, path + '/')

                        tmp.table(
                            elements = [ InodeIDType(case=query['case']),
                                         FilenameType(basename=True, case=query['case'],
                                                      link = new_query,
                                                      link_pane = 'parent'),
                                         IntegerType('File Size','size'),
                                         ],
                            table='inode',
                            where=DB.expand("file.path=%r and file.mode!='d/d'", (path+'/')),
                            case=query['case'],
                            pagesize=10,
                            filter="filter2",
                            )

                    result.tree(tree_cb = tree_cb,pane_cb = pane_cb, branch = [''] )

                def table_view_cb(query,result):
                    case = query['case']
                    new_query = make_new_query(query,'')
                    
                    result.table(
                        elements = [ InodeIDType(),
                                 FilenameType(case = case,
                                              link = new_query,
                                              link_pane = 'parent'),
                                 IntegerType('File Size', 'size')
                                 ],
                        table = 'inode',
                        case=case,
                        order = 2,
                        direction = 1
                        )
                    
                result.notebook(names = ["Tree View", "Table View",],
                                callbacks = [tree_view_cb, table_view_cb,],
                                context = "vfs_selector")

        def file_popup(query, result):
            result.heading(description)
            def left(path):
                if os.path.basename(path)=='.': return
                path=FlagFramework.sane_join(config.UPLOADDIR,path)
                try:
                    for d in os.listdir(path):
                        if os.path.isdir(os.path.join(path,d)):
                                         yield (d,d,'branch')
                except OSError,e:
                    yield ('.', e,'leaf')
                
            def right(path, result):
                case = self.defaults.get('case',None)
                dbh = DB.DBO(case)
                tablename = dbh.get_temp()
                dbh.execute("""create table %s (
                `filename` varchar(250) NOT NULL default '.',
                `timestamp` timestamp NOT NULL,
                `size` bigint(11) not null
                )""", tablename)

                ## populate the table:
                full_path=FlagFramework.sane_join(config.UPLOADDIR,path)

                dbh.mass_insert_start(tablename)
                ## List all the files in the directory:
                try:
                    for d in os.listdir(full_path):
                        filename = FlagFramework.sane_join(path,d)
                        full_filename = FlagFramework.sane_join(config.UPLOADDIR, filename)
                        try:
                            if not os.path.isdir(full_filename):
                                s = os.stat(full_filename)
                                dbh.mass_insert(filename = filename,
                                                _timestamp = "from_unixtime(%d)" % s.st_mtime,
                                                size = s.st_size)
                        except OSError:
                            pass
                    dbh.mass_insert_commit()
                except OSError,e:
                    pass

                new_query=query.clone()
                new_query['__target__'] = name
                new_query['__target_type__'] = 'append'

                elements = [ IntegerType(name='Size', column='size'),
                             TimestampType(name='Timestamp', column='timestamp'),
                             StringType(name='Filename', column='filename',
                                        link = new_query, link_pane='parent'
                                        )
                             ]

                ## Now display the table widget:
                result.table(
                    elements = elements,
                    table = tablename,
                    case = case,
                    order = 2, direction = 1
                    )

                ## Submit all the nodes in the display:
                def submit_all(query,new_result):
                    sql = result.renderer._make_sql(query)
                    dbh.execute(sql)
                    new_query = result.defaults.clone()
#                    new_query.remove('callback_stored',self.callback)
                    del new_query[name]
                    new_query['select_all']='1'
                    for row in dbh:
                        new_query[name] = row['Filename']

                    new_result.refresh(0,new_query, pane='parent')

                result.toolbar(cb=submit_all, text="Submit all", icon='yes.png')

            result.tree(tree_cb=left, pane_cb=right)
            
        files=self.defaults.getarray(name)
        if files:
            tmp = self.__class__(self)
            for f in files:
                new_query = self.defaults.clone()
                new_query.remove(name,f)
                tmp2 = self.__class__(self)
                tmp2.link("Remove", target=new_query, icon='delete.png')
                tmp.row("%s %s" % (tmp2,f))

            self.row('Currently Selected files',tmp)

        tmp = self.__class__(self)
        tmp.start_table( **{'class': 'highlight'})
        tmp2 = self.__class__(self)
        tmp2.popup(file_popup, "Upload Directory",
                  icon="file-selection.png",
                  width=1024, height=600)

        if vfs:
            tmp2.popup(vfs_popup, "VFS Files",
                       icon = "vfs.png",
                       width=1024,
                       height = 600)
        tmp.row('',tmp2)
        tmp.textfield('', name, Additional = True)
        tmp.end_table()
        self.row(description, tmp)

UI = None

config.add_option("PAGESIZE", default=50, type='int',
                  help="number of rows to display per page in the Table widget")

def _make_join_clause(total_elements):
    query_str = ''
    ## The tables are calculated as a join of all the individual
    ## database tables from all the columns - this allows us to
    ## put elements from different database tables in the same
    ## widget automatically.
    tables = []
    for e in total_elements:
        table = e.join_table()
        if table and table not in tables: tables.append(table)

    ## Now generate the join clause:
    query_str += " from `%s` " % tables[0]

    for i in range(1,len(tables)):
        query_str += " join `%s` on `%s`.inode_id = `%s`.inode_id " % \
                     (tables[i], tables[0],tables[i])

    return query_str


class TableRenderer:
    """ This class is responsible for rendering the table widget under
    various conditions.

    We can extend this class to produce other types of renderers like
    CSV, HTML, UI, PDF etc.
    """
    table =''
    where = '1'
    groupby = None
    _groupby = None
    case = None

    ## Exportable - indicate if we can participate in exporting
    exportable = False
    
    ## The elements we operate on (should be filled by __init__)
    elements = None

    ## The variable which contains the paging limit
    limit_context = 'limit'

    ## The query variable containing the filter expression
    filter = 'filter'
    ## The actual filter value
    filter_str = ''
    
    ## The query variable containing a list of columns to hide
    hidden = '_hidden'

    ## Take default pagesize from the configuration
    pagesize = config.PAGESIZE

    ## The total number of rows shown by this table render (only valid
    ## after calling render())
    row_count = 0

    ## Ascending or descending ordering?
    direction = 0

    ## The column number which will be sorted:
    order = 0

    ## Should we group by a column?
    groupby = None
    _groupby = None

    def __init__(self, **args):
        self.__dict__.update(args)
        
        ## These are the elements which will be filtered on
        self.filter_elements = self.elements

    def render(self, query, result):
        self.filter_str = query.get(self.filter,'')

        if self.groupby or self._groupby:
            for e in self.elements:
                if e.name==self.groupby:
                    new_query = query.clone()
                    del new_query['callback_stored']
                    del new_query['groupby']
                    del new_query['order']
                    filter_expression = self.filter_str.strip().replace('%','%%')
                    if filter_expression: filter_expression += " and "

                    filter_expression += "'%s'='%%s'" % e.name
                    new_query['__target_format__'] = filter_expression
                    new_query['__target__'] = self.filter
                    new_query.clear('limit')
                    e.link = new_query
                    e.link_pane = 'parent'

                    from pyflag.ColumnTypes import CounterType

                    self.elements = [ e,
                                      CounterType(name='Count'),
                                      ]
                    break

        self.render_table(query, result)
        self.render_tools(query, result)

    def render_tools(self,query, result):
        """ Called to install all the toolbar callbacks """
        self.paging_buttons(query, result)
        self.filter_buttons(query, result)
        self.configure_button(query, result)
        self.groupby_button(query, result)
        self.count_button(query, result)
        self.export_button(query, result)
        self.sql_button(query, result)
        
    def count_button(self, query, result):
        """  This returns the total number of rows in this table - it
        could take a while which is why its a popup."""
        def count_cb(query, result):
            sql = self._make_sql(query).split("from",1)[1]
            #sql = self._make_sql(query)[len("select "):]

            dbh=DB.DBO(self.case)
            dbh.execute("select count(*) as total from " + sql)
            row=dbh.fetch()
            result.heading("Total rows")
            result.para("%s rows" % row['total'])

        result.toolbar(count_cb, "Count rows matching filter", icon = "add.png")
        
    def groupby_button(self, query, result):
        """ This allows grouping (counting) rows with the same value """
        def group_by_cb(query,result):
            if query.has_key('groupby'):
                result.table(
                    elements= self.elements,
                    hidden = '_hidden_gb',
                    table = self.table,
                    where = self.where,
                    groupby = query.get('groupby',0),
                    limit_context="limit%s" % query['groupby'],
                    case = self.case,
                    filter = self.filter)
            
            result.start_form(query)
            result.const_selector("Group by", "groupby", self.column_names, self.column_names)
            result.end_form()
            
        result.toolbar(group_by_cb, "Group By A column",icon="group.png")
        
    def configure_button(self, query, result):
        """ Tool bar icon for hiding and showing columns """
        ## This is a toolbar popup which allows some fields to be hidden:
        def hide_fields(query, result):
            if query.has_key('__submit__'):
                del query['__submit__']
                result.refresh(0,query,pane='parent_pane')
                return
            
            result.heading("Hide Columns")
            
            result.start_form(query, pane='self')
            for i in range(len(self.elements)):
                result.checkbox(self.elements[i].name, self.hidden, "%s" % i)

            result.end_form()

        result.toolbar(cb=hide_fields, icon='spanner.png',
                       tooltip="Hide columns")

    def filter_buttons(self, query, result):
        """ Render toolbar buttons related to filtering """
        
        ## Add a possible filter condition:
        def filter_gui(query, result):
            result.heading("Filter Table")
            result.start_form(query, pane="self")
            result.add_filter(query, self.case, parser.parse_to_sql, self.elements, self.filter)
            result.end_form()
            
        ## Add a toolbar icon for the filter:
        result.toolbar(cb=filter_gui, icon='filter.png',
                       tooltip=result.defaults.get(self.filter,'Click here to filter table'))

        ## Add a clear filter icon if required
        try:
            new_query = query.clone()
            if new_query.has_key(self.filter):
                del new_query[self.filter]

                # Make it reset the limit
                new_query.clear(self.limit_context)
                new_query.clear('indexing_word')

                result.toolbar(link=new_query, icon='clear_filter.png', 
                               tooltip='Click here to clear the filter',
                               pane='pane')
        except: raise

    def paging_buttons(self,query, result):
        """ Adds toolbar buttons for paging through the table """
        new_query = query.clone()

        ## The previous button goes back if possible:
        previous_limit = self.limit - self.pagesize
        if previous_limit<0:
            result.toolbar(icon = 'stock_left_gray.png')
        else:
            del new_query[self.limit_context]
            new_query[self.limit_context] = previous_limit
            result.toolbar(icon = 'stock_left.png',
                         link = new_query, pane='pane',
                         tooltip='Previous Page (Rows %s-%s)' % (previous_limit, self.limit))

        ## Now we add the paging toolbar icons
        ## The next button allows user to page to the next page
        if self.row_count < self.pagesize:
            result.toolbar(icon = 'stock_right_gray.png')
        else:
            ## We could not fill a full page - means we ran out of
            ## rows in this table
            del new_query[self.limit_context]
            new_query[self.limit_context] = self.limit + self.pagesize
            result.toolbar(icon = 'stock_right.png',
                           link = new_query, pane='pane',
                           tooltip='Next Page (Rows %s-%s)' % (self.limit, self.limit \
                                                               + self.pagesize))

        ## Add a skip to row toolbar icon:
        def goto_row_cb(query,result,variable=self.limit_context):
            """ This is used by the table widget to allow users to skip to a
            certain row"""
            limit = query.get(variable,'0')
            result.decoration = 'naked'
            result.heading("Skip directly to a row")
            result.para("You may specify the row number in hex by preceeding it with 0x")
            result.start_form(query, pane="parent_pane")
            result.start_table()
            if limit.startswith('0x'):
                limit=int(limit,16)
            else:
                limit=int(limit)

            result.textfield('Row to skip to', variable)
            result.end_table()
            result.end_form()

        result.toolbar(
            cb = goto_row_cb,
            text="Row %s" % self.limit,
            icon="stock_next-page.png", pane='popup',
            )

    def sql_button(self, query, result):
        def button_cb(query, result):
            result.heading("SQL Statement used")
            result.para(self._make_sql(query))

        result.toolbar(
            cb = button_cb,
            text = "SQL Used",
            icon = "sql.png", pane = 'popup',
            )
    
    def _make_sql(self, query, ordering=True):
        """ Calculates the SQL for the table widget based on the query """
        ## Calculate the SQL
        query_str = "select "
        try:
            self.order = int(query.get('order',self.order))
        except: self.order=0

        try:
            self.direction = int(query.get('direction',self.direction))
        except: self.direction = 0

        total_elements = self.elements + self.filter_elements

        ## Fixup the elements - if no table specified use the global
        ## table - this is just a shortcut which allows us to be lazy:
        for e in total_elements:
            if not e.table: e.table = self.table
            if not e.case: e.case = self.case

        ## The columns and their aliases:
        query_str += ",".join([ e.select() + " as `" + e.name + "`" for e in self.elements ])
        
        query_str += _make_join_clause(total_elements)

        if self.where:
            w = ["(%s)" % self.where,]
        else:
            w = []
            
        for e in total_elements:
            tmp = e.where()
            if tmp: w.append(tmp)

        ## Is there a filter condition?
        if self.filter_str:
            filter_str = self.filter_str.replace('\r\n', ' ').replace('\n', ' ')
            filter_str = parser.parse_to_sql(filter_str, total_elements, ui=None)
            if not filter_str: filter_str=1
            
        else: filter_str = 1

        query_str += "where (%s and (%s)) " % (" and ".join(w), filter_str)

        if self.groupby:
            query_str += "group by %s " % DB.escape_column_name(self.groupby)
        elif self._groupby:
            query_str += "group by %s " % self.groupby
            
        ## Now calculate the order by:
        if ordering:
            try:
                query_str += "order by %s " % self.elements[self.order].order_by()
                if self.direction == 1:
                    query_str += "asc"
                else: query_str += "desc"
            except IndexError:
                pass

        return query_str

    def generate_rows(self,query):
        """ A Generator of rows. Each row is returned as a dictionary
        with key as the name of the column and value is a cell UI for
        that cell.

        Renderers can extend this to make the widget table use
        something other than a database.

        FIXME - Implement a memory based table renderer.
        """
        dbh = DB.DBO(self.case)
        self.sql = self._make_sql(query)
        ## This allows pyflag to cache the resultset, needed to speed
        ## paging of slow queries.
        try:    self.limit = int(query.get(self.limit_context,0))
        except: self.limit = 0
        
        dbh.cached_execute(self.sql,limit=self.limit, length=self.pagesize)
        
        return dbh

    def render_table(self, query, result):
        """ Renders the actual table itself """
        result.result+='''<table class="PyFlagTable" >
        <thead><tr>'''

        ## Get a generator for the rows:
        g = self.generate_rows(query)
        
        ## Make the table headers with suitable order by links:
        hiddens = [ int(x) for x in query.getarray(self.hidden) ]

        self.column_names = []
        for e in range(len(self.elements)):
            if e in hiddens: continue
            new_query = query.clone()
            ui = result.__class__(result)
            n = self.elements[e].column_decorator(self.table, self.sql, query, ui)
            n = n or ui
            self.column_names.append(n)
            
            if self.order==e:
                if query.get('direction','1')=='1':
                    tmp = result.__class__(result)
                    new_query.set('order', e)
                    new_query.set('direction',0)
                    tmp.link("%s<img src='images/increment.png'>" % n, target= new_query, pane='pane')
                    result.result+="<th>%s</th>" % tmp
                else:
                    tmp = result.__class__(result)
                    new_query.set('order', e)
                    new_query.set('direction',1)
                    tmp.link("%s<img src='images/decrement.png'>" % n, target= new_query, pane='pane')
                    result.result+="<th>%s</th>" % tmp
            else:
                tmp = result.__class__(result)
                new_query.set('order', e)
                new_query.set('direction',1)
                tmp.link(n, target= new_query, pane='pane')
                result.result+="<th>%s</th>" % tmp

        result.result+='''</tr></thead><tbody class="scrollContent">'''

        old_sorted = None
        old_sorted_style = ''

        ## Total number of rows
        self.row_count=0

        for row in g:
            row_elements = []
            tds = ''

            ## Render each row at a time:
            for i in range(len(self.elements)):
                if i in hiddens: continue

                ## Give the row to the column element to allow it
                ## to translate the output suitably:
                value = row[self.elements[i].name]
                try:
                    cell_ui = result.__class__(result)
                    ## Elements are expected to render on cell_ui
                    tmp = self.elements[i].display(value,row,cell_ui)
                    if tmp: cell_ui = tmp
                except Exception, e:
                    pyflaglog.log(pyflaglog.ERROR, expand("Unable to render %r: %s" , (value , e)))

                ## Render the row styles so that equal values on
                ## the sorted column have the same style
                if i==self.order and value!=old_sorted:
                    old_sorted=value
                    if old_sorted_style=='':
                        old_sorted_style='alternateRow'
                    else:
                        old_sorted_style=''

                ## Render the sorted column with a different style
                if i==self.order:
                    tds+="<td class='sorted-column'>%s</td>" % (FlagFramework.smart_unicode(cell_ui))
                else:
                    tds+=DB.expand("<td class='table-cell'>%s</td>",cell_ui)

            result.result+="<tr class='%s'> %s </tr>\n" % (old_sorted_style,tds)
            self.row_count += 1

        result.result+="</tbody></table>"


    def export_button(self, query, result):
        """ Provides an interface for exporting the table in a useful way """

        def save_table(query, result):
            result.start_form(query)
            exporters = [ c for c in Registry.TABLE_RENDERERS.classes if c.exportable ]
            names = [ c.name for c in exporters ]
            result.const_selector("Export format", "export_format", names, names)

            try:
                ## Ask the rederer to show any configuration it might
                ## need:
                r_index = names.index(query["export_format"])
                r = exporters[r_index](elements = self.elements,
                                       filter_str = self.filter_str,
                                       case = self.case,
                                       where = self.where,
                                       groupby = self.groupby,
                                       limit_context = self.limit_context,
                                       filter = self.filter,
                                       hidden = self.hidden)

                if query.has_key('finished'):
                    ## Ask the renderer to display the table:
                    r.render(query, result)
                    return 
                
                if r.form(query, result):
                    query['finished']=1
                    result.refresh(0,query)
                    return

            except KeyError:
                pass

            result.end_form()
            
        result.toolbar(save_table, "Export Table", icon="floppy.png")

## This is a reference for the original table renderer. This is needed
## for the Registry to still pick up our classes even if the above
## TableRenderer has been replaced.
TableRendererBaseClass = TableRenderer
