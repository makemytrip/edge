# Copyright 2018 MakeMyTrip (Paritosh Anand)
#
# This file is part of edge.
#
# edge is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# edge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dataShark.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import logging

from django.test import TestCase

from orchestration.scripts.dc_deploy import DCDeploy
from orchestration.utils.fabric_handler import FabricHandler
from orchestration.utils.lb import LB

logger = logging.getLogger(__name__)

# Create your tests here.


class OrchestrationTest(TestCase):

    fixtures = ['space/fixtures/configs.json',]

    def test_fabric(self):
        hosts = ['x.x.x.x']
        command = "hostname"
        fb = FabricHandler(hosts=hosts, command=command).exec_remote_command()

        for host in hosts:
            self.assertTrue(fb[host][command][1])

    def test_get_node_operation(self):
        # pool = "sitemum_datamonster.mmt.mmt_http_pool"
        server = "x.x.x.x"
        dc = "MUM"
        lbobj = LB()
        self.assertTrue(lbobj.get_node_oos(server, dc))

        self.assertTrue(lbobj.get_node_is(server, dc))


'''
class OrchestrationTest(TestCase):

    def test_dummy_install(self):
        d=DCDeploy()
        self.assertTrue(getattr(d, 'install')())

    def test_dummy_configure(self):
        d=DCDeploy()
        self.assertTrue(getattr(d, 'configure')())

class LBTest(TestCase):
    pool = "sitemum_datamonster.mmt.mmt_http_pool"
    server = "x.x.x.x"
    dc = "MUM"
    lbobj = None

    def test_get_node_OOS(self):
        lbobj = LB()
        if lbobj.get_node_OOS(server, dc) is True:
            return True
        return False

    """def test_get_node_OOS(self):
        if self.lbobj.get_node_IS(server, dc) is True:
            return True
        return False

    def test_get_pool_info(self):
        print self.lbobj.get_pool_info(pool, dc)

    def test_get_member_session(self):
        print self.lbobj.get_member_session(server, pool, dc)

    def test_get_member_pool(self):
        print self.lbobj.get_memberlist_pool(pool, dc)

    def test_get_node_status(self):
        print self.lbobj.get_node_status(server, dc)"""
'''
