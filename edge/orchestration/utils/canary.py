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

import logging, requests, json
from space.utils.db_handler import DBHandler
from orchestration.core.staggered import StaggeredImplementation

logger = logging.getLogger(__name__)


class CanaryImplementation():
    dbobj = DBHandler()

    def __init__(self):
        pass

    @classmethod
    def schedule_canary_task(cls, action_task_id, jira_id, project_name, staggered_label, zone, staggered_servers,
                             non_staggered_servers):
        try:
            data = {
                'ccrid' : action_task_id,
                'jiraid' : jira_id,
                'project_name' : project_name,
                'staggered_status' : staggered_label,
                'datacenter' : zone.lower(),
                'verf_server' : ",".join(staggered_servers),
                'prod_server' : ",".join(non_staggered_servers),
                'respond_to' : 'edge',
            }
            logger.info("Parameter Receieved to Schedule CANARY Task - %s" % data)
            canary_uri = cls.dbobj.getValue("canary_schedule_api")
            canary_success_code = [200, 119]
            canary_config_failure_code = [111]
            message = None
            status = None
            code = 200
            response = requests.post(canary_uri, data=json.dumps(data))
            if response.status_code == 200:
                response_data = response.json()
                logger.info("Response from Canary for ActionInfo Task Id - %s, zone - %s, staggered_label - %s, Data - %s" % (
                    action_task_id, zone, staggered_label, response_data))
                if response_data.get('status') is True or response_data.get('code') in canary_success_code:
                    logger.info("Successfully Called Canary for ActionInfo Task Id - %s, zone - %s, Staggered_label - %s" % (
                        action_task_id, zone, staggered_label))
                    status = True
                elif response_data.get('status') is True or response_data.get('code') in canary_config_failure_code:
                    status = False
                    message = response_data.get('message')
                    code = response_data.get('code')
                else:
                    error_message = response_data.get('message')
                    raise Exception(error_message)
            else:
                error_message = "Unknown Error Occured via calling canary API, Status - %s, Error -  %s" % (response.status_code, response.text)
                logger.error(error_message)
                raise Exception(error_message)
        except Exception, e:
            status = False
            message = str(e)
            code = 499
            logger.exception(e)
        finally:
            return { 'status': status, 'message': message, 'code': code }
