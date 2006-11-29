""" This module provides a report that allows the analyst to browse email 
traffic. It complements the RFC2822 scanner that is part of the Disk Forensics 
family."""

# Michael Cohen <scudette@users.sourceforge.net>
# David Collett <daveco@users.sourceforge.net>
# Gavin Jackson <gavz@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.82 Date: Sat Jun 24 23:38:33 EST 2006$
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

import pyflag.Reports as Reports
import pyflag.FlagFramework as FlagFramework
from pyflag.TableObj import ColumnType, TimestampType, InodeType

class BrowseEmail(Reports.report):
    """ Slightly modified report for displaying emails in the network forensics family """
    name = "Browse Email"
    family = "Network Forensics"
    description = "This report displays an email item from an email vfs entry as a nicely formatted email message"
    hidden = False

    def form(self, query, result):
        result.case_selector()
       
    def display(self, query, result):
	result.heading("Email sessions")
        result.table(
            elements = [ InodeType('Inode','inode',
                           link = query_type(family='Disk Forensics',
                                             case=query['case'],
                                             __target__='inode',
                                             report='View File Contents',
                                             mode="Text")),
                         ColumnType('Date','date'),
                         ColumnType('From','from'),
                         ColumnType('To','to'),
                         ColumnType('Subject','subject') ],
            table=('email'),
            case=query['case'],
        )
