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

from django.conf import settings
import consul, logging
from space.utils.db_handler import DBHandler

logger = logging.getLogger(__name__)


class ConsulOperation():

    def __init__(self):
        try:
            self.consul_client = None
            self.dbobj = DBHandler()
            self.consul_host = self.dbobj.getValue("consul_host")
            logger.debug(self.consul_host)
            if not self.consul_host:
                raise ValueError('consul host is mandatory')
            self.consul_client = consul.Consul(host=self.consul_host)

        except Exception as e:
            logger.error("exeption conneting to consul server - %s" %(self.consul_client))
            raise e

    def setKV(self, key,value):
            try:
                self.consul_client.kv.put(key, value)
                return ("sucessfully saved to consul")
            except Exception as e:
                logger.error("%s Got exception while seting KV to consul -" %(key))
                logger.exception(e)
                return e

    def getKV(self, key):
            try:
                index, data = self.consul_client.kv.get(key)
                logger.info("%s Sucessfully get key" %(key))
                return data['Value']
            except Exception as e:
                logger.error("failed to get key from consul")
                logger.exception(e)
                return e
