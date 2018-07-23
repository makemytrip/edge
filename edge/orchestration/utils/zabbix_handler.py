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
import requests, logging
from space.utils.db_handler import DBHandler

logger = logging.getLogger(__name__)


class ZabbixHandler():

    def __init__(self, zabbix=None, hostname=None):
        try:
            self.zabbix = zabbix
            self.hostname = hostname
            logger.debug(self.zabbix)
            if not self.zabbix:
                raise ValueError('zabbix host is mandatory')
        except Exception as e:
            logger.error("exeption for zabbix host - %s" %(self.zabbix))
            raise e


    def take_action(self, action=None):
        scaling_status = 400
        try:
            if not action:
                raise ValueError('action is mandatory')

            endpoint = "http://{zabbix}/zabbix/snooze.php?action={action}&hostname={hostname}".format(zabbix=self.zabbix, action=action, hostname=self.hostname)
            logger.info("zabbix action %s for %s, endpoint %s" % (action, self.hostname, endpoint))
            scaling_status = requests.get(endpoint, timeout=5).status_code

        except Exception as e:
            logger.error("%s Got exception while %s for %s at %s -" %(action, self.hostname, self.zabbix))
            logger.exception(e)
            return e
        finally:
            return scaling_status
