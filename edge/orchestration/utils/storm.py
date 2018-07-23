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

import requests, time, logging

logger = logging.getLogger(__name__)


class Storm(object):
    def __init__(self, host, port, version, protocol="http", timeout=20):
        self.uri = "%s://%s:%s" %(protocol, host, port)
        self.topology_uri = "/api/v1/topology"
        self.summary_uri = "/summary"
        self.action_uri = "/{id}/kill/{wait_time}"
        self.timeout=timeout

    def kill_topology(self, topology_name, wait_time, raise_on_failure):
        topology_uri = "%s%s%s" %(self.uri, self.topology_uri, self.action_uri)
        topology_id = self.get_topology_id(topology_name)
        wait_time = int(wait_time)
        if topology_id is None:
            logger.error("Unable to find topology id for topology name - %s, URI - %s"
                         %(topology_name, topology_uri))
            status = False if raise_on_failure is True else True
            return { 'status': status, 'message' : "Topology With Name - %s doesn't exist on cluster - %s" %(topology_name, self.uri) }

        topology_uri = topology_uri.format(id=topology_id, wait_time=wait_time)
        retry_count=3
        # Run the loop till the topology is killed so that its id becomes to None
        while topology_id is not None and retry_count > 0:
            response = requests.post(topology_uri, timeout=self.timeout)
            while response.status_code != 200 and retry_count > 0:
                time.sleep(5)
                response = requests.post(topology_uri, timeout=self.timeout)
                retry_count -= 1
            if response.status_code != 200:
                raise Exception("Unable to Kill topology name - %s, with id - %s, URI - %s"
                                %(topology_name, topology_id, topology_uri))
            data = response.json()
            logger.debug("Data Received while killing topology - %s from host - %s, Data - %s"
                         %(topology_name, topology_uri, data))
            time.sleep(wait_time + 1)
            topology_id = self.get_topology_id(topology_name)
        if topology_id is not None:
            # raise Exception(" Unable to kill topology - %s on host uri - %s" %(topology_name, topology_uri))
            logger.info("Unable to kill topology - %s on host uri - %s" %(topology_name, topology_uri))
        # {"topologyOperation": "kill", "topologyId": "wordcount-1-1420308665", "status": "success"}
        status = True if data.get('status').lower() in [ 'success', 'killed' ] else False
        return {'status' : status}

    def get_topology_id(self, topology_name):
        summary_uri = "%s%s%s" %(self.uri, self.topology_uri, self.summary_uri)

        response = requests.get(summary_uri)
        retry_count=3
        while response.status_code != 200 and retry_count > 0:
            time.sleep(10)
            response = requests.get(summary_uri)
            retry_count -= 1
        if response.status_code != 200:
            raise Exception("Can not get topology ID for topology name - %s, URI - %s" %(topology_name, summary_uri))
        data = response.json()
        data = data.get('topologies', [])
        topology_id = [i.get('id') for i in data if i.get('name') == topology_name ]
        topology_id = topology_id[0] if len(topology_id) > 0 else None
        return topology_id
