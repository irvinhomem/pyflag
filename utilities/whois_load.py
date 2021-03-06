#!/usr/bin/python
# 
# Script to load whois ipv4 data into pyflag master database
# usage:
# ./whois_load [filename]...
#
# Multiple files can be named on the cmd line, but filenames MUST
# be of a particular format:
# RIR Records: delegated-<source>-<latest|date> eg. delegated-arin-latest
# Full Records: <source>.db.inetnum.gz eg. ripe.db.inetnum.gz
# These are the default names of the files provided via ftp, the
# names are used to determine file type and parse the source and date
#
# If called without arguments, script will attempt to download
# the latest versions of the databases via FTP
#
# David Collett <daveco@sourceforge.net>

import sys
import re
import urllib
import time
import gzip
import os.path
import pyflag.DB as DB
import pyflag.conf
config=pyflag.conf.ConfObject()
from optparse import OptionParser

# whois database URL's
# Full databases are available for apnic and ripencc
# Only have 'RIR' stats for lacnic and arin
# ...though you may be able to request full databases from them

urls = {#'apnic':'ftp://ftp.apnic.net/apnic/whois-data/APNIC/split/apnic.db.inetnum.gz',
        'ripe':'ftp://ftp.ripe.net/ripe/dbase/split/ripe.db.inetnum.gz',
        'arin':'ftp://ftp.arin.net/pub/stats/arin/delegated-arin-latest',
        'lacnic':'ftp://ftp.lacnic.net/pub/stats/lacnic/delegated-lacnic-latest'}

config.set_usage(usage="""%prog [Options]
Downloads some whois repositories.""")

config.optparser.add_option('-d','--delete', action="store_true",
                  help="""Delete previous databases""")

config.optparser.add_option('-a','--all', action="store_true",
                  help="""Load all repositories""")

for k in urls.keys():
  config.optparser.add_option('','--%s' % k, action="store_true",
                    help = "Load %s databases" % k)

config.parse_options()

if config.all:
  for k in urls.keys():
    setattr(config, k, 1)

MASK32 = 0xffffffffL

import sys

def progress(block,blocksize,totalblocks):
  sys.stdout.write("Retrieved %skb/%skb %u%%\r" % (blocksize*block/1024
                                                    ,totalblocks/1024
                                                    ,(block*blocksize*100)/totalblocks))
  sys.stdout.flush()

# apnic and ripe can be replaced by the below URLs, if only stats are req'd
# ftp://ftp.apnic.net/pub/stats/apnic/delegated-apnic-latest
# ftp://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest

# pow2 list
pow2 = {}
for num in range(33):
  pow2[long(2**num)] = num

pow2list = pow2.keys()
pow2list.sort()

def largest_nm(num):
  """ return highest valid netmask possible """
  res = 0
  for hosts in pow2list:
    if hosts <= num:
      res = hosts
    else:
      break

  res =  (res-1) ^ MASK32
  return res

def num_hosts(nm):
  """ return number of hosts possible given netmask """
  res=(nm ^ MASK32) + 1
  return res

def aton(str):
  """ convert dotted decimal IP to int """
  oct = [long(i) for i in str.split('.')]
  result=((oct[0] << 24) | (oct[1] << 16) | (oct[2] << 8) | (oct[3])) & MASK32
  return result

class WhoisRec:
    """ class representing an ipv4 inetnum whois record """
    regex = {'inetnum':re.compile('^inetnum:\s+(.*)$', re.MULTILINE),
             'netname':re.compile('^netname:\s+(.*)$', re.MULTILINE),
             'descr':re.compile('^descr:\s+(.*)$', re.MULTILINE),
             'remarks':re.compile('^remarks:\s+(.*)$', re.MULTILINE),
             'country':re.compile('^country:\s+(.*)$', re.MULTILINE),
             'status':re.compile('^status:\s+([^\s]*)$', re.MULTILINE),
             'adminc':re.compile('^admin-c:\s+(.*)$', re.MULTILINE),
             'techc':re.compile('^tech-c:\s+(.*)$', re.MULTILINE),
             'notify':re.compile('^notify:\s+(.*)$', re.MULTILINE)}
    
    unfold = re.compile('\n\s+')
    
    def __init__(self, string, type):
      if type == 'whois':
        self.parse_whois(string)
      elif type == 'rir':
        self.parse_rir(string)
      else:
        print "Unknown record type"
        
    def parse_whois(self, string):
      # first unfold the string
      string = WhoisRec.unfold.sub(' ',string)
      # get start_ip, numhosts
      self.start_ip = 0L
      self.num_hosts = 0
      try:
        inetnum = self._getsingle('inetnum', string)
        self.start_ip, end_ip = [ aton(a.strip()) for a in inetnum.split('-') ]
        self.num_hosts = end_ip - self.start_ip + 1
      except ValueError, e:
        print >>sys.stderr, "ERROR PARSING: %s %s" % (inetnum,e)

      self.netname = self._getsingle('netname', string)
      self.country = self._getsingle('country', string)
      self.adminc = self._getsingle('adminc', string)
      self.techc = self._getsingle('techc', string).decode("UTF8","ignore")
      self.descr = self._getmulti('descr', string).decode("UTF8","ignore")
      self.remarks = self._getmulti('remarks', string).decode("UTF8","ignore")

      # get status
      status_str = self._getsingle('status', string).lower()
      if status_str.find('allocated'):
        self.status = 'allocated'
      elif status_str.find('assigned'):
        self.status = 'assigned'
      else:
        print "invalid status"

    def parse_rir(self, string):
      cols = string.split('|')
      self.country = cols[1]
      self.adminc = ''
      self.techc = ''
      self.netname=''
      self.start_ip = aton(cols[3])
      self.num_hosts = int(cols[4])
      self.status = cols[6].strip()
      self.descr = ''
      self.remarks = ''
      
    def _getsingle(self, field, string):
        match = WhoisRec.regex[field].search(string)
        if match:
            return match.groups()[0]
        else:
            return ""

    def _getmulti(self, field, string):
        return "\n".join(WhoisRec.regex[field].findall(string))

    def __str__(self):
      return """
      start_ip: %x
      netname: %s
      num_hosts: %i
      country: %s
      adminc: %s
      techc: %s
      status: %s
      descr: %s
      remarks: %s""" % (self.start_ip,self.netname,self.num_hosts,self.country,self.adminc,self.techc,self.status, self.descr, self.remarks)

class Whois:
    """ class to process a whois database file """    
    def __init__(self, url):
      base = os.path.basename(url)
      if base.startswith('delegated'):
        self.whois = 0
        match = re.search('^delegated-(\w+)-(.*)$',base)
        if match:
          self.source, self.date = match.groups()
          if not self.date.isdigit():
            self.date = ':'.join(["%i"% i for i in time.localtime()[:6]])
        else:
          return None
      else:
        match = re.search('^(\w+)\.db\.inetnum\.gz$', base)
        if match:
          self.whois = 1
          self.source = match.group(1)
          self.date = ':'.join(["%i"% i for i in time.localtime()[:6]])
        else:
          return None

      fname="%s/%s" % (config.RESULTDIR,base)
      print "searching for %s " % fname

      try:
        self.fp = gzip.open(fname)
      except IOError:
        print "retrieving %s into %s " % (url,fname)
        fname=urllib.urlretrieve(url,fname,progress)[0]
        self.fp=gzip.open(fname)

      try:
        self.fp.read(1)
        self.fp=gzip.open(fname)
      except IOError:
        self.fp=open(fname)

    def next(self):
      if self.whois:
        return self.next_whois()
      else:
        return self.next_rir()
        
    def next_whois(self):
      entry = ""
      while(1):
        line = self.fp.readline()
        if line == '\n':
          break
        elif line == '':
          raise StopIteration
        entry += line
      if entry:
        return WhoisRec(entry, 'whois')

    def next_rir(self):
      while(1):
        line = self.fp.readline()
        cols = line.split('|')
        if len(cols) == 7 and cols[2] == 'ipv4':
          return WhoisRec(line, 'rir')
        if line == '':
          raise StopIteration

    def __iter__(self):
      return self
    
dbh = DB.DBO(None)
if config.delete:
  # create tables in master flag database
  # Since the whois entries often get split into many smaller
  # subnets for routing, we will use two tables to reduce space
  ## First drop the old tables
  dbh.execute("drop table if exists whois_sources")
  dbh.execute("drop table if exists whois")
  dbh.execute("drop table if exists whois_routes")
  dbh.execute("drop table if exists whois_cache")
  dbh.execute("""CREATE TABLE IF NOT EXISTS whois_sources (
  `id` int,
  `source` varchar(20),
  `url` varchar(255),
  `updated` datetime)""")

  whois_sources_id = 0

  dbh.execute("""CREATE TABLE IF NOT EXISTS whois (
  `id` int,
  `src_id` int,
  `start_ip` int(10) unsigned,
  `netname` varchar(250),
  `numhosts` int unsigned,
  `country` char(3),
  `adminc` varchar(250),
  `techc` varchar(250),
  `descr` text,
  `remarks` text,
  `status` enum('assigned','allocated','reserved','unallocated'))""")

  whois_id = 0

  dbh.execute("CREATE TABLE IF NOT EXISTS whois_routes ( `network` int(10) unsigned, `netmask` int(10) unsigned, `whois_id` int)")

  dbh.execute("""create table whois_cache (
  `id` int unsigned not NULL,
  `ip` int unsigned not NULL,
  `geoip_country` int unsigned NOT NULL,
  `geoip_city` int unsigned NOT NULL,
  `geoip_isp` int unsigned NOT NULL,
  `geoip_org` int unsigned NOT NULL
  ) engine=MyISAM""")

  # add default (fallthrough) route and reserved ranges
  dbh.insert('whois_sources',
             source='static',
             id = whois_sources_id,
             url='static',
             updated= ':'.join(["%i"% i for i in time.localtime()[:6]]))

  dbh.insert('whois',
             id=whois_id,
             src_id=str(dbh.cursor.lastrowid),
             start_ip=0,
             netname='Default',
             numhosts=0,
             country='--',
             adminc='',
             techc='',
             descr='Default Fallthrough Route: IP INVALID OR UNASSIGNED',
             remarks='',
             status='unallocated'
             )

  dbh.insert('whois_routes',
             network=0,
             netmask = 0,
             whois_id = whois_id)

else:
  dbh.execute("select max(id) as max from whois_sources")
  row = dbh.fetch()
  
  if not row or not row['max']:
    whois_sources_id = 1
  else:
    whois_sources_id = row['max'] + 1

  dbh.execute("select max(id) as max from whois")
  row = dbh.fetch()
  if not row:
    whois_id = 1
  else:
    whois_id = row["max"]+1

# process files
source_dbh = dbh.clone()
routes_dbh = dbh.clone()

source_dbh.mass_insert_start('whois_sources')
routes_dbh.mass_insert_start('whois_routes')
dbh.mass_insert_start('whois')

for k,url in urls.items():
#  if not getattr(config, k): continue

  print "Processing %s" % url
  try:
    db = Whois(url)
  except Exception, e:
    print "Error %s" % e
    continue

  # add this source to db
  source_dbh.mass_insert(
    source = db.source,
    url = url,
    id = whois_sources_id,
    updated = db.date)

  whois_sources_id+=1
  
  # process records
  for rec in db:
    ## Get a new whois_id number:
    whois_id += 1
    dbh.mass_insert(
      src_id = whois_sources_id,
      start_ip = "%u" % rec.start_ip,
      netname = rec.netname[:250],
      numhosts = rec.num_hosts,
      country = rec.country[:2],
      adminc = rec.adminc[:250],
      techc = rec.techc[:250],
      id = whois_id,
      __descr = rec.descr,
      remarks = rec.remarks,
      status = rec.status)  

    #now process the networks (routes)...
    # split into networks on bit boundaries
    left = rec.num_hosts
    masks = []
    while left:
      nm = largest_nm(left)
      masks.append(nm)
      left = left - num_hosts(nm)
      
    # sort masks, set initial network address
    network = rec.start_ip
    masks.sort() # smallest netmask (ie. largest network) will be first

    # process networks
    while masks:
      # get indexes of the ones that align
      align = [ x for x in range(len(masks)) if (network & masks[x]) == network ]
      if len(align) == 0:
        # none align, have to split smallest network in half and try again
        masks.append(largest_nm(num_hosts(masks.pop())/2))
        masks.append(masks[-1])
      else:
        # choose the largest network which is aligned and assign it
        routes_dbh.mass_insert(
          network = network & MASK32,
          netmask = "%u" % masks[align[0]],
          whois_id = whois_id)

        # advance network address and remove this from masks
        network = network + num_hosts(masks[align[0]])
        del masks[align[0]]

# add indexes
#dbh.check_index("whois_routes","network")
#dbh.check_index("whois_routes","netmask")
#dbh.check_index("whois","id")
