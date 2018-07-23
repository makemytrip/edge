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

import logging

from space.utils.db_handler import DBHandler

logger = logging.getLogger(__name__)


class StaggeredImplementation(object):
    """The Staggered Implementation works on servers not on pools, it created batch depending on the number of servers."""

    def __init__(self, ):
        self.is_staggered = False
        self.__current_staggered_label = None
        self.staggered_batch = None
        self.staggered_servers = {}
        self.non_canary_staggered_label=[]

    def get_current_staggered_label(self):
        return self.__current_staggered_label

    def _get_next_staggered_label(self):
        staggered_batches = self.staggered_batch.split(",")
        current_index = staggered_batches.index(self.get_current_staggered_label()) if self.get_current_staggered_label() in staggered_batches else None
        next_staggered_label = staggered_batches[current_index + 1] if current_index is not None and current_index < len(staggered_batches) - 1 else None
        return next_staggered_label

    def get_servers_till_current_staggered_label(self):
        servers=[]
        staggered_batches = self.staggered_batch.split(",")
        current_staggered_label_index = staggered_batches.index(self.get_current_staggered_label())
        for i in xrange(current_staggered_label_index+1):
            servers.extend(self.staggered_servers.get(staggered_batches[i]))
        return servers

    def get_servers_after_current_staggered_label(self, count):
        servers=[]
        staggered_batches = self.staggered_batch.split(",")
        current_staggered_label_index = staggered_batches.index(self.get_current_staggered_label())
        next_staggered_label = staggered_batches[current_staggered_label_index+1]
        servers.extend(self.staggered_servers.get(next_staggered_label))
        return servers[0:count]

    def update_next_staggered_label(self):
        self.__current_staggered_label = self._get_next_staggered_label()

    def set_current_staggered_label(self, staggered_label):
        self.__current_staggered_label = staggered_label

    def validate_staggered_batch(self, staggered_batch):
        pass

    def create_staggered_batches(self, serverlist, otherserverlist=[], staggered_batch=None):
        oos_servers = []
        is_servers = []
        # Serverlist may contains duplicate servers
        for servers in serverlist:
            if servers.get('enabled_status', False) is True:
                is_servers.append(servers.get('server'))
            else:
                oos_servers.append(servers.get('server'))
        is_servers = list(set(is_servers))
        oos_servers = list(set(oos_servers) - set(is_servers))

        staggered_batch_config = DBHandler().getValue("staggered_batch_config")
        batch_size = None
        if staggered_batch is not None:
            if self.validate_staggered_batch(staggered_batch):
                batch_size = staggered_batch

        if batch_size is None:
            if len(is_servers) >= 10:
                batch_size = staggered_batch_config.get("10")
            elif len(is_servers) >= 8:
                batch_size = staggered_batch_config.get("8")
            elif len(is_servers) >= 4:
                batch_size = staggered_batch_config.get("4")
            elif len(is_servers) >= 2:
                batch_size = staggered_batch_config.get("2")
            elif len(is_servers) >= 1:
                batch_size = staggered_batch_config.get("1")

        batch_servers = {}
        if batch_size is not None:
            old_batch_count=0
            for batch in batch_size.split(","):
                batch_number = int(batch.strip('%'))
                batch_count = int((len(is_servers) * batch_number)/100)
                batch_servers[batch] = is_servers[old_batch_count:batch_count]
                old_batch_count = batch_count

        otherservers = [ servers.get('server') for servers in otherserverlist ]
        otherservers = list(set(otherservers) - set(is_servers).union(set(oos_servers)))
        otherservers.extend(oos_servers)

        if otherservers:
            batch_size = staggered_batch_config.get("0").strip() if batch_size is None else batch_size+","+staggered_batch_config.get("0").strip()
            batch_servers[batch_size.split(",")[-1]] = otherservers
        self.non_canary_staggered_label = [staggered_batch_config.get("0").strip(), staggered_batch_config.get("1").strip()]
        self.staggered_batch = batch_size
        self.__current_staggered_label = batch_size.split(",")[0]
        self.staggered_servers = batch_servers

    def deploy_staggered(self):
        raise NotImplementedError("Deploy method must be implemented")
