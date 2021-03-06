# ******************************************************
# Copyright 2004: Commonwealth of Australia.
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

""" This is a RAID IO Source implementation.

Currently supported RAID5 with one Parity disk (any number of data
disks).
"""
import plugins.Images as Images
import pyflag.FlagFramework as FlagFramework
import pyflag.IO as IO
import re, os.path, binascii, sk
import pyflag.DB as DB
import copy

class ParityFD(Images.OffsettedFDFile):
    """An abstraction for reconstructing the missing disk in a RAID5"""
    def __init__(self, filenames):
        self.filenames = filenames
        self.readptr = 0
        self.offset = 0

    def seek(self, offset, whence=0):
        """ fake seeking routine """
        readptr = self.readptr
        if whence==0:
            readptr = offset + self.offset
        elif whence==1:
            readptr += offset
        elif whence==2:
            readptr = self.size

        if readptr < 0:
            raise IOError("Seek before start of file")

        self.readptr = readptr

    def read(self,length):
        fds = [ IO.open_URL(f) for f in self.filenames ]
        for fd in fds:
            fd.seek(self.readptr)
        data = False
        for fd in fds:
            if data == False:
                data = map(lambda x: ord(x), fd.read(length))
            else:
                data = map(lambda (x,y): x^y,zip(data,map(lambda z: ord(z), fd.read(length))))
        self.readptr += length
        return ''.join(map(lambda x: chr(x), data))


class RAIDFD(Images.OffsettedFDFile):
    """ A RAID file like object - must be initialised with the correct parameters """
    def __init__(self, fds, blocksize, map, offset, physical_period):
        self.readptr = 0
        self.fds = fds
        ## The number of disks in the set
        self.disks = len(fds)
        self.blocksize = blocksize
        
        ## The physical period is the number of blocks before the map
        ## repeats in each disk
        self.physical_period = physical_period
        self.parse_map(map)
        self.offset = offset

        ## We estimate the size:
        if fds:
            fds[0].seek(0,2)
            self.size = fds[0].tell() * self.physical_period

    def seek(self, offset, whence=0):
        """ fake seeking routine """
        readptr = self.readptr
        if whence==0:
            readptr = offset + self.offset
        elif whence==1:
            readptr += offset
        elif whence==2:
            readptr = self.size

        if readptr < self.offset:
            raise IOError("Seek before start of file")

        self.readptr = readptr

    def parse_map(self, map):
        elements = map.split(".")
        self.map = []
        for j in range(self.physical_period):
            self.map.append([])
            for i in range(self.disks):
                if not elements:
                    raise RuntimeError("Map does not have enough elements")
                
                try:
                    disk_number = int(elements.pop(0))
                except: disk_number=None
                
                self.map[-1].append(disk_number)

        ## Now derive the period map
        self.period_map = []
        for i in range(self.physical_period * (self.disks - 1)):
            found = False
            ## Find the required disk in the map:
            for period_index in range(len(self.map)):
                try:
                    d = self.map[period_index].index(i)
                    self.period_map.append((period_index,d))
                    found = True
                    break
                except: pass

            if not found:
                raise RuntimeError("Invalid map position %s not found" % i)
            
        self.logical_period_size = len(self.period_map)

    def partial_read(self, length):
        ## calculate the current position within the logical
        ## image. Logical blocks refer to the reconstituted image,
        ## physical to the raw disks
        logical_block_number = self.readptr / self.blocksize
        logical_block_offset = self.readptr % self.blocksize

        ## Our logical block position within the period
        logical_period_position = logical_block_number % self.logical_period_size
        logical_period_number = logical_block_number / self.logical_period_size

        ## Now work out which disk is needed.
        physical_period_number, disk_number = self.period_map[logical_period_position]

        ## Now the physical block within the disk:
        physical_block_number = logical_period_number * self.physical_period \
                                + physical_period_number

        ## Now fetch the data
        to_read = min(self.blocksize - logical_block_offset, length)
        offset = self.blocksize * physical_block_number \
                 + logical_block_offset
        self.fds[disk_number].seek(offset)
        
        data = self.fds[disk_number].read(to_read)

        self.readptr += to_read

        return data

def swap(a,x):
    """ Create a permutation to swap column x in list a """
    a = list(a)
    if x>=len(a)-1:
        return [a[x]] + a[:-1]
    else:
        return a[:x] + [ a[x+1] ] + [a[x]] + a[x+2:]

class RAID(Images.Standard):
    """ RAID image sets """
    name = 'RAID5 (1 Parity)'

    presets = [ [ "3 Disk Rotating parity (Adaptec)", "0.1.P.2.P.3.P.4.5", "3" ],
                [ "4 Disk Continuing parity (Linux)", "0.1.2.P.4.5.P.3.8.P.6.7.P.9.10.11", "4" ],
                [ "3 Disk double parity (4x3 permutations)",
                  "0.1.P.2.3.P.4.5.P.6.7.P.8.P.9.10.P.11."\
                  "12.P.13.14.P.15.P.16.17.P.18.19.P.20.21.P.22.23", "12"]]
    
    def form(self, query, result):
        ## Some reasonable defaults to get you started
        query.default('blocksize','4k')
        query.default('period',self.presets[0][2])
        query.default('map',self.presets[0][1])
        query.default('ismissing',False)
        keys = []
        values = []
        result.fileselector("Disks", name='filename')
        result.textfield("Block size",'blocksize')
        result.textfield("Period",'period')
        result.checkbox("Is a disk missing?",'ismissing',True)
        self.calculate_map(query, result)
        self.calculate_partition_offset(query, result)

        def preset(query, result):
            result.heading("Select a present map")

            if query.has_key("__submit__"):
                preset = self.presets[int(query['preset'])]
                query.clear('preset')
                query.set('period', preset[2])
                query.set('map', preset[1])
                return result.refresh(0, query, 'parent')
            
            result.start_form(query)
            presets = []
            presets_numbers = []
            for row in self.presets:
                presets.append(row[0])
                presets_numbers.append(len(presets)-1)
                
            result.const_selector("Preset:", "preset", presets_numbers, presets)
            result.end_form()

        result.toolbar(cb = preset, text="Select a preset map", icon='spanner.png')

    def calculate_partition_offset(self, query, result, offset = 'offset'):
        """ A GUI function to allow the user to derive the offset by calling mmls """
        def mmls_popup(query,result):
            result.decoration = "naked"
            my_offset = 0
            last_offset = 0
            done = False
            try:
                del query[offset]
            except: pass

            io = self.create(None, query.get('case'), query)
            #This loops through the disk looking for a partition table.
            #If it finds a block with the appropriate magic numbers, it
            #tries to create a mmls object. If it fails, it moves to the
            #next block.
            while(1):
                io.seek(last_offset)
                while(1):
                    my_offset = io.tell()#Starting position of this next read; if it works, this will be the partition table offset
                    foobarbaz = re.sub('=','',binascii.b2a_qp(io.partial_read(512)))
                    last_offset=io.tell()#This is the offset we will resume our search at if this table doesn't work.
                    if len(foobarbaz) == 0:#If we've reached the end of the RAID, we're done.
                        done = True
                    if re.search('0UAA$',foobarbaz) != None:#Check for magic numbers of DOS partition table
                        break
                io.seek(0)
                try:
                    print "trying"+str(my_offset) 
                    parts = sk.mmls(io,my_offset)
                except IOError, e:
                    if done:#If we've reached the end without finding a partition table, we give up.
                        result.heading("No Partitions found")
                        result.text("TESTFUNC %d Sleuthkit returned: %s" % (my_offset,e))
                        return
                else:#If we created mmls object without error, we're done searching, so break
                    break
            my_offset_s = my_offset / 512
            result.heading("Possible IO Sources")
            result.start_table(border=True)
            result.row("Chunk", "Start", "End", "Size", "Description")
            del query[offset]
            for i in range(len(parts)):
                new_query = query.clone()
                tmp = result.__class__(result)
                new_query[offset] = "%ds" % int(parts[i][0]+my_offset_s)
                tmp.link("%010d" % int(parts[i][0]+my_offset_s), new_query, pane='parent')
                result.row(i, tmp, "%010d" % (parts[i][0] + parts[i][1]),
                           "%010d" % parts[i][1] , parts[i][2])
            result.end_table()
        
        tmp = result.__class__(result)
        tmp2 = result.__class__(result)
        tmp2.popup(mmls_popup,
                   "Survey the partition table",
                   icon="examine.png")

        tmp.row(tmp2,"Enter partition offset:")
        result.textfield(tmp,offset)


    def calculate_map(self, query,result):
        """ Present the GUI for calculating the map """
        def map_popup(query,result):
            result.decoration = 'naked'
            try:
                map = str(query['map']).split('.')
            except KeyError:
                map = []

            result.start_form(query)
            ## Open all the disks
            filenames = query.getarray('filename') 
            fds = [ IO.open_URL(f) for f in filenames ]

            if query.get('ismissing',False):
                fds += [ParityFD(copy.deepcopy(filenames))]
                filenames += ('Missing Disk',)


            uis = [ result.__class__(result) for f in filenames ]

            period_number = int(query.get('period_number',0))
            blocksize = FlagFramework.calculate_offset_suffix(query['blocksize'])
            period = FlagFramework.calculate_offset_suffix(query['period'])
            logical_period_size = period * (len(fds)-1)
            ## Let the user know our disk offset
            result.para("Disk Offset is %s (%s periods)" %  (blocksize  * (period_number * period), period_number))

            if query.has_key("__submit__"):
                ## Build the new map variable
                query.clear('map')
                map = []
                for x in range(period * len(fds)):
                    map.append(query['position_%s' % x])
                    query.clear('position_%s' % x)
                    
                query.set('map', '.'.join(map))
                ## Now check that this map is valid by instantiating a
                ## RAIDFD (we will raise if anything is wrong:
                try:
                    RAIDFD(fds, blocksize, query['map'], 0, period)
                    result.refresh(0,query,pane='parent')
                except Exception,e:
                    result.heading("Error with map")
                    result.para("%s" % e)

                return result
            
            ## Possible positions the block can be
            positions = ['P', ] + [ str(x) for x in range(logical_period_size) ]

            for i in range(len(fds)):
                ## Provide links to allow swapping of filenames:
                new_query = query.clone()
                new_query.clear('filename')
                new_filenames = swap(filenames, i)
                for f in new_filenames:
                    new_query['filename'] = f

                tmp = result.__class__(result)
                tmp.text(os.path.basename(filenames[i]))
                tmp.link("Swap", new_query, icon='stock_right.png', pane='self')
                uis[i].heading(tmp)
                
                ## Display the start and end of each physical block in
                ## the period:
                ## Count is the position of each block in the map
                count = i
                for p in range(period):
                    ui = uis[i]
                    fd = fds[i]
                    
                    ## This offset of this block
                    offset = blocksize  * (p + period_number * period)
                    fd.seek(offset)
                    ui.ruler()
                    for j in range(4):
                        data = fd.read(16)
                        data = re.sub(r'[\r\n\t]','.',data)
                        ui.text(data + "    \n", sanitise='full', font='typewriter')

                    ui.start_table()
                    try:
                        ui.defaults.default("position_%s" % count, map[count])
                    except IndexError: raise


                    ui.const_selector("Pos", "position_%s" % count,positions,positions)
                    ui.end_table()
                    fd.seek(offset + blocksize - 16*4)                    
                    for j in range(4):
                        data = fd.read(16)
                        data = re.sub(r'[\r\n\t]','.',data)
                        ui.text(data + "    \n", sanitise='full', font='typewriter')
                    ui.ruler()
                    count += len(filenames)
            
            result.row(*uis)
            result.end_form()
            result.para("Press submit to update the map definition")
            query.set('period_number',max(period_number-1, 0))
            if period_number >0:
                result.toolbar(text='Previous Period', icon='stock_left.png',
                               link = query, pane='self')
            else:
                result.toolbar(text='Previous Period', icon='stock_left_gray.png',
                               pane='self')

            query.set('period_number',period_number+1)
            result.toolbar(text='Next Period', icon='stock_right.png',
                           link = query, pane='self')

            result.toolbar(text="Skip to text region", icon='stock_last.png',
                           cb = self.search_next_text_region, pane='popup')

            result.toolbar(text='goto period', icon='stock_next-page.png',
                           cb = self.goto_period, pane='popup')

        tmp = result.__class__(result)
        tmp2 = result.__class__(result)
        tmp2.popup(map_popup,
                   "Calculate the RAID map",
                   pane='new',
                   icon='examine.png')

        tmp.row(tmp2, "Map")
        result.textarea(tmp,'map')

    ## This regex matches a continuous string with only printables
    text_re = re.compile(r"^[\t\n\r !\"#$%&\'()*+,\-./0123456789:;" \
                         r"<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ\[\\\]^_`a" \
                         r"bcdefghijklmnopqrstuvwxyz{|}~]+$")

    def goto_period(self, query,result):
        """ Jumps to specified period """
        result.heading("Jump to period")
        if query.has_key("__submit__" ):
            query.set('period_number',query['goto_period'])
            query.clear('goto_period')

            result.refresh(0, query, 'parent')
            return
        
        result.start_form(query)
        result.textfield("Period Number to jump to", 'goto_period')
        result.end_form()

    def search_next_text_region(self, query, result):
        """ searches for the next text region and updates query['period_number'] """
        ## Open all the disks
        filenames = query.getarray('filename') 
        fds = [ IO.open_URL(f) for f in filenames ]
        if query.get('ismissing',False):
            fds.append(ParityFD(copy.deepcopy(filenames)))
        period_number = int(query.get('period_number',0)) + 1
        blocksize = FlagFramework.calculate_offset_suffix(query['blocksize'])
        period = FlagFramework.calculate_offset_suffix(query['period'])

        p=0
        while 1:
            offset = blocksize  * (p + period_number * period)
            for fd in fds:
                fd.seek(offset)
                ## We classify a text region as one with 20 chars at
                ## the start of the period
                data = fd.read(20)
                if not data:
                    result.heading("Error")
                    result.para("Unable to read data from %r" % fd)
                    return
                
                m = self.text_re.match(data)
                if m:
                    period_number = period_number + p / period
                    query.set('period_number',period_number)
                    result.refresh(0, query, 'parent')
                    return

                p += 1

    def create(self, name,case, query):
        offset = FlagFramework.calculate_offset_suffix(query.get('offset','0'))
        filenames = self.glob_filenames(query.getarray('filename'))

        ## Open the io sources here
        fds = [ IO.open_URL(f) for f in filenames ]
        if query.get('ismissing',False):
            fds += [ParityFD(copy.deepcopy(filenames))]
        blocksize = FlagFramework.calculate_offset_suffix(query.get('blocksize','32k'))
        period = int(query.get('period',3))
        return RAIDFD(fds, blocksize, query['map'], offset, period)


import pyflag.tests
import pyflag.pyflagsh as pyflagsh

class RaidTest(pyflag.tests.ScannerTest):
    """ Test the RAID IOSource loader """
    test_case = "PyFlagTestCase"

    def test01LoadRaid(self):
        """ Test the RAID IO Source loader """
        ## This image was made by the linux raid5 implementation.
        ## Just to make things a bit more complicated, each image of
        ## each individual disk was acquired using ewfacquire into an
        ## EWF file. We use the io://EWF/filename=/raid/linux/d1.E01
        ## URL notation as the image filename in order to use the EWF
        ## IO Source driver to read the file.
        pyflagsh.shell_execv(command="execute",
                             argv=["Load Data.Load IO Data Source",'case=%s' % self.test_case,
                                   "iosource=test",
                                   "subsys=RAID5 (1 Parity)",
                                   "filename=io://EWF/filename=/raid/linux/d1.E01",
                                   "filename=io://EWF/filename=/raid/linux/d2.E01",
                                   "filename=io://EWF/filename=/raid/linux/d3.E01",
                                   "offset=0",
                                   "map=1.0.P.P.3.2.4.P.5",
                                   "period=3",
                                   "blocksize=64k",
                                   "TZ=%s" % self.TZ
                                   ])
        
        pyflagsh.shell_execv(command="execute",
                             argv=["Load Data.Load Filesystem image",'case=%s' % self.test_case,
                                   "iosource=test",
                                   "fstype=Sleuthkit",
                                   "mount_point=/"])

    def test02Hash(self):
        """ Test the hashes of loaded files """
        env = pyflagsh.environment(case=self.test_case)
        pyflagsh.shell_execv(env=env, command="scan",
                             argv=["*",'MD5Scan'])
            
        dbh = DB.DBO(self.test_case)
        dbh.execute("select binary_md5 from hash where binary_md5=%b",
                    "04D68B7C8993A3A485A5780EC1A8D62D".decode("hex"))
        self.assert_(dbh.fetch(), "Expected hash not found")
        
