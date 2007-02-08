# Michael Cohen <scudette@users.sourceforge.net>
# David Collett <daveco@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.84RC1 Date: Fri Feb  9 08:22:13 EST 2007$
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
""" This module implements a carver looking for specific file types in
the image.

The carver uses the indexer to pre-locate carved headers which makes
it very fast. We create VFS nodes for carved files, which means that
the carved files do not actually take storage space. This stratgy
allows PyFlag's Carver to be extremely fast.

Carved files are scanned with the usual scanners once they are
discovered.
"""
import pyflag.conf
config=pyflag.conf.ConfObject()
import pyflag.DB as DB
import pyflag.Scanner as Scanner
import PIL.Image
import pyflag.Registry as Registry
            
class JpegCarver(Scanner.Carver):
    regexs = ["\xff\xd8....JFIF", "\xff\xd8....EXIF"]
    extension = 'jpg'        
    
class CarveScan(Scanner.GenScanFactory):
    """ Carve out files """
    ## We must run after the Index scanner
    order = 300
    default = False
    depends = 'IndexScan'

    def __init__(self,fsfd):
        Scanner.GenScanFactory.__init__(self, fsfd)
        
        dbh = DB.DBO()
        carvers = [ c(fsfd) for c in Registry.CARVERS.classes ]
        self.ids = {}
        
        ## We need to ensure that the scanner regexs are in the
        ## dictionary:
        for c in carvers:
            for expression in c.regexs:
                dbh.execute("select id from dictionary where word=%r limit 1", expression)
                row = dbh.fetch()
                if not row:
                    dbh.insert("dictionary", **{'word': expression,
                                                'class':'_Carver', 
                                                'type':'regex' })
                    id = dbh.autoincrement()
                else:
                    id = row['id']

                self.ids[id] = c


    class Scan(Scanner.BaseScanner):
        def finish(self):
            dbh=DB.DBO(self.fd.case)
            ## Find the matches for our classes:
            sql = " or ".join(["word_id = '%s'" % x for x in self.outer.ids.keys()])
            dbh.execute("select word_id,offset from LogicalIndexOffsets where offset>0 and inode_id = %r and (%s)",
                        (self.fd.inode_id, sql))
            for row in dbh:
                ## Ignore matches which occur within the length of the
                ## previously found file:
                #if row['offset']<offset: continue
                offset = row['offset']
                ## Allow the carver to work with the offset:
                self.outer.ids[row['word_id']].add_inode(self.fd, offset, self.factories)
                
## Unit tests:
import unittest
import pyflag.pyflagsh as pyflagsh
import pyflag.tests

class CarverTest(pyflag.tests.ScannerTest):
    """ Carving Tests """
    test_case = "PyFlagIndexTestCase"
    test_file = "pyflag_stdimage_0.2"
    subsystem = 'advanced'
    order = 30
    offset = "16128s"
    
    def test01CarveImage(self):
        """ Carving from Image """
        env = pyflagsh.environment(case=self.test_case)
        pyflagsh.shell_execv(env=env, command="scan",
                             argv=["*",'CarveScan', 'IndexScan','TypeScan'])

        ## See if we found the two images from within the word
        ## document:
        expected = [ "Itest|K1289-0-0|o150712:87368", "Itest|K1289-0-0|o96317:141763"]
        
        dbh = DB.DBO(self.test_case)
        for inode in expected:
            dbh.execute("select inode from inode where inode=%r limit 1", inode)
            row = dbh.fetch()
            self.assert_(row != None)
