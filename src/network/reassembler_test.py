#!/usr/bin/env python
import _dissect
import reassembler
import DB

hnd = reassembler.init("/var/tmp/results/")

print hnd

def Callback(stream):
#    print stream
#    raise IOError
    print "%s: %s" % (stream['con_id'], stream)

reassembler.set_tcp_callback(hnd, Callback)

filename = "/var/tmp/demo/ftp3.pcap"
fd=open(filename)
dbh = DB.DBO("demo")

dbh.execute("select * from pcap order by id")
for row in dbh:
    fd.seek(row['offset'])
    data = fd.read(row['length'])
    try:
        reassembler.process_tcp(hnd, data, row['id'], row['link_type'])
    except RuntimeError:
        pass

reassembler.clear_stream_buffers(hnd)
