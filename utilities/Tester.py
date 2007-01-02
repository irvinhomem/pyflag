# ******************************************************
# Michael Cohen <scudette@users.sourceforge.net>
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
""" This is a test harness for running Unit tests.

Unit tests are defined in plugins as derived unittest.TestCase
classes. These are then picked off by the registry and run within the
harness.

Eventually all plugins will have complete unit tests.
"""
import pyflag.Registry as Registry
import unittest,re
import pyflag.conf
from optparse import OptionParser

parser = OptionParser(usage = """%prog [options]""")
parser.add_option('-m','--match', default=None, help='Run only tests matching this RE')

options,args = pyflag.conf.parse_command_line("Generic Test harness for running unit tests.",parser=parser)

Registry.Init()

## Start up some workers:
import pyflag.Farm as Farm
Farm.start_workers()

test_registry = Registry.InitTests()
if not options.match:
    classes = test_registry.classes
else:
    classes = [ x for x in test_registry.classes if re.search(options.match,"%s" % x)]

for test_class in classes:
    print "---------------------------------------"
    print "Running tests in %s" % test_class
    print "---------------------------------------"
    suite = unittest.makeSuite(test_class)
    unittest.TextTestRunner(verbosity=2).run(suite)