# ******************************************************
# Copyright 2004: Commonwealth of Australia.
#
# Michael Cohen <scudette@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.85 Date: Fri Dec 28 16:12:30 EST 2007$
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
""" This module is designed to extract messages from live.com (the new
name for hotmail).

The reason this is needed is that most modern web mail applications
use so much javascript its impossible to make sense of the html
objects directly - they are not simple pages any more. This module
tries to extract certain pieces of information from the html object
specifically oriented towards the live.com/hotmail service.

How this works:

1) We only target inodes with a type of html as well as the regex
'<title>\s+Windows Live' in the top.

InboxLight pages (pages showing a view of the inbox or another mail
folder)

2) We obtain the list of folders by doing some dom navigation (find li
with class=FolderItemNormal, get the a below it and extract the
FolderID, get the span below that and get the name of the mail
box. This gives us a mapping between folder id and mailbox name).

3) Extract all the messages using some more DOM stuff:
  - Locate a table with class InboxTable, iterate over its rows

  - for each row, the 5th td is the to field. The mailbox can be found
  from the a tag there.

  - The subject is the 6th field. Date is the 7th field. Size is the
  8th field.

EditMessageLight - This page is what the user receives when they want
to edit a new message.

3) Search for a table with class ComposeHeader, iterate over its rows
   - For each row extract the fields from the id attributes:

     - From tr - find an option tag with selected attribute

     - To tr, Cc tr, Bcc tr, Subject tr - find an input tag and
     extract the value attribute

     - To find the actual context of the message search for script
     tags, with a regex:
     document.getElementById\(\"fEditArea\"\).innerHTML='([^']+)' The
     result needs to be unescaped suitably.

4) When EditMessageLight is called it has a form which submits into
itself. To get the post values look at the http_parameters table for
that HTTP object id.
"""
import pyflag.FlagFramework as FlagFramework
from pyflag.ColumnTypes import StringType, TimestampType, InodeIDType, IntegerType, PacketType
import FileFormats.HTML as HTML
import pyflag.DB as DB
import pyflag.Scanner as Scanner
import pyflag.Reports as Reports
import pyflag.FileSystem as FileSystem
import re,cgi
import pyflag.pyflaglog as pyflaglog
import textwrap

class LiveTables(FlagFramework.EventHandler):
    def create(self, dbh, case):
        dbh.execute(
            """ CREATE table if not exists `live_messages` (
            `id` int not null auto_increment,
            `inode_id` int not null,
            `parent_inode_id` int not null,
            `service` VARCHAR(50),
            `type` enum('Edit Read','Edit Sent','Read','Listed') default 'Edit Read',
            `From` VARCHAR(250),
            `To` VARCHAR(250),
            `CC` VARCHAR(250),
            `BCC` VARCHAR(250),
            `Subject` VARCHAR(250),
            `Message` Text default "",
            `Sent` TIMESTAMP NULL,
            primary key (`id`))""")

        ## We need to keep the URL in case we find it later on
        dbh.execute( """ CREATE table if not exists `live_message_attachments` (
        `message_id` int NOT NULL,
        `inode_id` int NULL,
        `url` VARCHAR(500))""")

        ## This table keeps a record of http objects which may be used
        ## to assist with rendering. Often static content on web sites
        ## is cached for a long time in users browsers. This means
        ## that they are not requested by the browser at all and this
        ## causes problems when reconstructing the pages. This table
        ## allows us to maintain our own cache of such objects which
        ## we can download by ourselves when needed.
        dbh.execute("""CREATE table if not exists `http_sundry` (
        `id` int not null auto_increment,
        `url` VARCHAR(500),
        `present` enum('yes', 'no') default 'no',
        primary key (`id`))""")

import fnmatch

class HotmailScanner(Scanner.GenScanFactory):
    """ Detects Live.com/Hotmail web mail sessions """
    default = True
    depends = ['TypeScan', 'HTTPScanner']

    def multiple_inode_reset(self, inode_glob):
        Scanner.GenScanFactory.multiple_inode_reset(self, inode_glob)
        dbh = DB.DBO(self.case)
        sql = fnmatch.translate(inode_glob)
        dbh.delete("live_messages", where="inode_id in (select inode_id from inode where inode rlike %r)" % sql) 
    
    class Scan(Scanner.StoreAndScanType):
        types = (
            'text/html',
            )
        parser = None
        service = "Hotmail"

        def boring(self, metadata, data=''):
            ## We dont think its boring if our base class does not:
            ## And the data contains '<title>\s+Windows Live' in the top.
            if not Scanner.StoreAndScanType.boring(self, metadata, data='') and \
                   re.search("<title>\s+Windows Live", data):
                   ## Make a new parser:
                if not self.parser:
                    self.parser =  HTML.HTMLParser(verbose=0)
                return False

            return True

        def process(self, data, metadata=None):
            Scanner.StoreAndScanType.process(self, data, metadata)
            ## Feed our parser some more:
            if not self.boring_status:
                self.parser.feed(data)
                ## Get all the tokens
                while self.parser.next_token(True): pass

        def external_process(self, fd):
            pyflaglog.log(pyflaglog.DEBUG,"Opening %s for Hotmail processing" % self.fd.inode)
            ## Now we should be able to parse the data out:
            self.process_send_message(fd)
            self.process_editread(fd)
            self.process_readmessage(fd)
            self.process_mail_listing()

        def process_mail_listing(self):
            """ This looks for the listing in the mail box """
            table = self.parser.root.find("table",{"class":"ItemListContentTable InboxTable"})
            if not table: return False
            
            result = {'type': 'Listed', 'Message': table}

            mail_box = self.parser.root.find("li", {"class":"FolderItemSelected"})
            if mail_box:
                mail_box = mail_box.find("span")
                if mail_box:
                    result['From'] = mail_box.innerHTML()

            title = self.parser.root.find("a",{"class":"uxp_hdr_meLink"})
            if title:
                result['To'] = title.innerHTML()

            return self.insert_message(result, inode_template = "l%s")


        def process_send_message(self,fd):
            ## Check to see if this is a POST request (i.e. mail is
            ## sent to the server):
            dbh = DB.DBO(self.case)
            dbh.execute("select `key`,`value` from http_parameters where inode_id = %r", self.fd.inode_id)
            query = dict([(r['key'].lower(),r['value']) for r in dbh])
            result = {'type':'Edit Sent' }
            for field, pattern in [('To','fto'),
                                   ('From','ffrom'),
                                   ('CC','fcc'),
                                   ('Bcc', 'fbcc'),
                                   ('Subject', 'fsubject'),
                                   ('Message', 'fmessagebody')]:
                if query.has_key(pattern):
                    result[field] = query[pattern]

            if len(result.keys())>2:
                return self.insert_message(result)
            else: return False

        def process_readmessage(self,fd):
            result = {'type': 'Read', 'Message':''}
            root = self.parser.root

            tag = root.find('div', {'class':'ReadMsgContainer'})
            if not tag: return

            ## Find the subject:
            sbj = tag.find('td', {'class':'ReadMsgSubject'})
            if sbj: result['Subject'] = HTML.decode_entity(sbj.innerHTML())

            ## Fill in all the other fields:
            context = None
            for td in tag.search('td'):
                data = td.innerHTML()
                if context:
                    result[context] = HTML.decode_entity(data)
                    context = None
                
                if data.lower().startswith('from:'):
                    context = 'From'
                elif data.lower().startswith('to:'):
                    context = 'To'
                elif data.lower().startswith('sent:'):
                    context = 'Sent'

            ## Now the message:
            ## On newer sites its injected using script:
            for s in root.search('script'):
                m=re.match("document\.getElementById\(\"MsgContainer\"\)\.innerHTML='([^']*)'", s.innerHTML())
                if m:
                    result['Message'] += HTML.decode_unicode(m.group(1).decode("string_escape"))
                    break

            return self.insert_message(result)            

        def process_editread(self, fd):
            ## Find the ComposeHeader table:
            result = {'type':'Edit Read'}

            root = self.parser.root
            tag = root.find('table', {"class":'ComposeHeader'})
            if not tag:
                return

            ## Find the From:
            row = tag.find( 'select', dict(name = 'ffrom'))
            if row:
                option = row.find('option', dict(selected='.*'))
                result['From'] = HTML.decode_entity(option['value']) 

            for field, pattern in [('To','fto'),
                                   ('CC','fcc'),
                                   ('Bcc', 'fbcc'),
                                   ('Subject', 'fsubject')]:
                tmp = tag.find('input', dict(name = pattern))
                if tmp:
                    result[field] = HTML.decode_entity(tmp['value'])
            
            ## Now extract the content of the email:
            result['Message'] = ''

            ## Sometimes the message is found in the EditArea div:
            div = root.find('div', dict(id='EditArea'))
            if div:
                result['Message'] += div.innerHTML()

            ## On newer sites its injected using script:
            for s in root.search('script'):
                m=re.match("document\.getElementById\(\"fEditArea\"\)\.innerHTML='([^']*)'", s.innerHTML())
                if m:
                    result['Message'] += m.group(1).decode("string_escape")
                    break

            return self.insert_message(result)
            
        def insert_message(self, result, inode_template="l%s"):
            dbh = DB.DBO(self.case)
            dbh.insert('live_messages', service=self.service,
                       parent_inode_id = self.fd.inode_id,
                       **result)
            
            id = dbh.autoincrement()

            dbh.execute("select mtime from inode where inode_id = %r" , self.fd.inode_id)
            row = dbh.fetch()

            inode_id = self.ddfs.VFSCreate(self.fd.inode,
                                           inode_template % id,
                                           "Message", mtime = row['mtime'],
                                           _fast = True)

            dbh.update('live_messages',where = 'id = "%s"' % id,
                       inode_id = inode_id)
            
            return id

class HTMLStringType(StringType):
    """ A ColumnType which sanitises its input for HTML.
    We also fetch images etc from the db if available.
    """
    def xxxdisplay(self, value, row, result):
        parser = HTML.HTMLParser(tag_class = HTML.SanitizingTag)
        parser.feed(value)
        parser.close()

        return parser.root.innerHTML()

    def xxdisplay(self, value, row, result):
        parser = HTML.HTMLParser(tag_class = FlagFramework.Curry(HTML.ResolvingHTMLTag,
                                                                 case = result.defaults['case'],
                                                                 inode_id = row['Inode']))
        parser.feed(value)
        parser.close()

        return parser.root.innerHTML()

    def display(self, value, row, result):
        parser = HTML.HTMLParser(tag_class = HTML.TextTag)
        parser.feed(value or '')
        parser.close()

	result.text(parser.root.innerHTML(), wrap='full', font='typewriter')

class LiveComMessages(Reports.report):
    """
    Browse LiveCom/Hotmail messages.
    --------------------------------

    This allows the results from the hotmail message scanner to be viewed.

    """

    name = "Browse Hotmail Messages"
    family = "Network Forensics"

    def display(self, query, result):
        result.table(
            elements = [ TimestampType('Timestamp','inode.mtime'),
                         InodeIDType('Inode', 'inode.inode_id', case = query['case']),
                         StringType('From', 'From'),
                         StringType('To', 'To'),
                         StringType('CC', 'CC'),
                         StringType('BCC', 'BCC'),
                         StringType('Subject', 'Subject'),
                         HTMLStringType('Message','Message'),
                         StringType('Type','type'),
                         StringType('Service','service'),
                         ],
            table = 'live_messages,inode',
            where = 'inode.inode_id=live_messages.inode_id',
            case = query['case']
            )

import textwrap

## A VFS File driver which formats a row in the db nicely:
class TableViewer(FileSystem.StringIOFile):
    """ A VFS driver to read rows from an SQL table.

    Format is 't%s:%s:%s:%s' % (table_name, column_name, value, column_to_retrieve (optional))

    e.g. tlive_messages:id:2
    """
    specifier = 't'

    def __init__(self, case, fd, inode):
        parts = inode.split('|')
        ourinode = parts[-1][1:]
        self.size = 0
        self.column_to_retrieve = None

        try:
            self.table, self.id, self.value = ourinode.split(':')
        except ValueError:
            self.table, self.id, self.value, self.column_to_retrieve = ourinode.split(':')
            
        FileSystem.StringIOFile.__init__(self, case, fd, inode)
        self.force_cache()
        
    def read(self, length = None):
        try:
            return FileSystem.StringIOFile.read(self, length)
        except IOError: pass

        result = '<html><body>'
        dbh = DB.DBO(self.case)
        dbh.execute("select * from %s where `%s`=%r", (self.table, self.id, self.value))
        for row in dbh:
            if self.column_to_retrieve:
                return row[self.column_to_retrieve]

            result += ("<table border=1>\n")
            for k,v in row.items():
                result += "<tr><td>%s</td>" % k
                result += "<td>%s</td></tr>\n" % textwrap.fill(
                    cgi.escape("%s" % v) or "&nbsp;",
                    subsequent_indent = "<br>")
                
            result += "</table></body></html>"
        return result

class LiveMailViewer(FileSystem.StringIOFile):
    """ A VFS Driver to render a realistic view of a Yahoo mail
    message without allowing scripts to run.
    """
    specifier = 'l'

    def __init__(self, case, fd, inode):
        parts = inode.split('|')
        self.id = parts[-1][1:]
        dbh = DB.DBO(case)
        dbh.execute("select * from live_messages where id=%r", (self.id))
        row = dbh.fetch()
        if not row: raise RuntimeError("No such message %s" % self.id)

        self.parent_inode_id = row['parent_inode_id']
        self.message = row['Message'] or ""
        self.size = len(self.message)
        
        FileSystem.StringIOFile.__init__(self, case, fd, inode)
        self.force_cache()
        
    def read(self, length = None):
        try:
            return FileSystem.StringIOFile.read(self, length)
        except IOError: pass

        return self.message

    def fixup_page(self, root):
        ## We have to inject the message into the edit area:
        edit_area = root.find("div", {"class":"EditArea"}) or \
                    root.find("div",{"id":"MsgContainer"}) or \
                    root.find("textarea",{"id":"fMessageBody"})
        if edit_area:
            parser = HTML.HTMLParser(tag_class = FlagFramework.Curry(
                HTML.ResolvingHTMLTag,
                case = self.case,
                inode_id = self.parent_inode_id))
            parser.feed(HTML.decode(self.message))
            parser.close()
            result = parser.root.__str__()
            result = textwrap.fill(result)
            edit_area.add_child(result)

    def stats(self, query,result):
        result.start_table(**{'class':'GeneralTable'})
        dbh = DB.DBO(self.case)
        columns = ["service","type","From","To","CC","BCC","Sent","Subject","Message"]
        dbh.execute("select * from live_messages where `id`=%r", self.id)
        row = dbh.fetch()
        for c in columns:
            if c=='Message':
                ## Filter the message out here:
                parser = HTML.HTMLParser(tag_class = \
                                         FlagFramework.Curry(HTML.ResolvingHTMLTag,
                                                             case = self.case,
                                                             inode_id = row['parent_inode_id']))
                #parser = HTML.HTMLParser(tag_class = HTML.TextTag)
                parser.feed(HTML.decode(row[c] or ""))
                parser.close()
                #tmp = result.__class__(result)
                #tmp.text(parser.root.innerHTML(), font='typewriter', wrap='full')
                #row[c] = tmp
                r = parser.root.__str__()
                r = textwrap.fill(r)
                row[c] = r
                
            result.row(c, row[c])

        dbh.execute("select url from http where inode_id = %r", row['parent_inode_id'])
        row = dbh.fetch()
        if row:
            tmp = result.__class__(result)
            tmp.text(row['url'], font='typewriter', wrap='full')
            result.row("URL", tmp)

    def summary(self, query, result):
        ## Get the original HTML File:
        fsfd = FileSystem.DBFS(self.case)
        fd = fsfd.open(inode_id = self.parent_inode_id)
        data = HTML.decode(fd.read())

        ## Make a parser:
        p = HTML.HTMLParser(tag_class = FlagFramework.Curry(HTML.ResolvingHTMLTag,
                                                            case = self.case,
                                                            inode_id = self.parent_inode_id))
        p.feed(data)
        p.close()

        ## Allow us to fix the html page
        root = p.root
        self.fixup_page(root)
        page = root.innerHTML()
        
        def frame_cb(query, result):
            def generator():
                yield page

            result.generator.content_type = 'text/html'
            result.generator.generator = generator()

        result.iframe(callback = frame_cb)


## Unit tests:
import pyflag.pyflagsh as pyflagsh
import pyflag.tests as tests

class HotmailTests(tests.ScannerTest):
    """ Tests Hotmail Scanner """
    test_case = "PyFlagTestCase"
    test_file = 'live.com.pcap.e01'
    subsystem = "EWF"
    fstype = "PCAP Filesystem"

    def test01HotmailScanner(self):
        """ Test Hotmail Scanner """
        env = pyflagsh.environment(case=self.test_case)
        pyflagsh.shell_execv(env=env,
                             command="scan",
                             argv=["*",                   ## Inodes (All)
                                   "HotmailScanner",
                                   ])                   ## List of Scanners

        dbh = DB.DBO(self.test_case)
        dbh.execute("select count(*) as c from live_messages")
        row = dbh.fetch()
        self.assert_(row['c'] > 0, "No hotmail messages were found")