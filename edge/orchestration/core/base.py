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

import logging, datetime, inspect

from orchestration.utils.elk_handler import ELKHandler
from orchestration.utils.fabric_handler import FabricHandler


logger = logging.getLogger(__name__)


class BaseOrchestration(object):
    def __init__(self, task_obj=None, params=None):
        self.params = params if params is not None else {}
        self.es = ELKHandler(task_obj.id)
        self.task_obj = task_obj
        self.config = task_obj.config_dict()
        self.failed_server_list = []

    def _get_update_batch_server_list(self, server_list):
        temp_server_list = set(server_list) - set(self.failed_server_list)
        return list(temp_server_list)

    def deploy(self):
        raise NotImplementedError("Deploy method must be implemented")

    def restart(self):
        raise NotImplementedError("Restart method must be implemented")

    def install(self):
        raise NotImplementedError("Install method must be implemented")

    def configure(self):
        raise NotImplementedError("Configure method must be implemented")

    def start(self):
        raise NotImplementedError("Start method must be implemented")

    def stop(self):
        raise NotImplementedError("Stop method must be implemented")

    def _get_elk_format(self, status, servers, method=None, action=None, exception=None, starttime=None, endtime=None, task=None,
                        description=None, batch_count=None, staggered_label=None, **kwargs):
        if starttime is None:
            starttime = datetime.datetime.now()

        if endtime is None:
            endtime = datetime.datetime.now()

        duration = (endtime - starttime).total_seconds()
        serverlist = servers if type(servers) is list else [servers]
        data =[]
        if action is None:
            action = self.task_obj.action.name

        if method is None:
            method = inspect.getouterframes(inspect.currentframe(), 2)[1][3]

        if task is None:
            task = inspect.getouterframes(inspect.currentframe(), 2)[1][3]

        if description is None:
            description = task

        if batch_count is None:
            batch_count = len(serverlist)

        try:
            if staggered_label is None:
                staggered_label = self.get_current_staggered_label() if self.is_staggered is True else None
        except Exception, e:
            logger.debug(e)
            staggered_label = None

        for server in serverlist:
            tmpdata = {
                'status': status,
                'server': server,
                'method': method,
                'action': action,
                'exception': exception,
                'starttime': starttime,
                'endtime': endtime,
                'duration': duration,
                'task': task,
                'description': description,
                'batch_count': batch_count,
                'staggered_label': staggered_label,
            }
            tmpdata.update(kwargs)
            data.append(tmpdata)
        return data

    def _send_to_elk(self, data, detailed=False, delete_query=None):
        try:
            """for r in data:
                logger.info("Message Writing in ELK ----  %s" % r )
                self.es.send(r, detailed)"""
            # For Bulk Writing
            delete_query = delete_query if delete_query is not None else {}
            logger.info("Data receieved for ELK Writing - %s, Delete Query - %s" %(data, delete_query))
            if data:
                if delete_query and type(delete_query) is dict and len(delete_query) > 0:
                    self.es.delete(**delete_query)
                self.es.send(data, detailed)
        except Exception, e:
            logger.error("Unable to Write to ELK for id - %s, Error - %s" %(self.task_obj.id, e))

    @staticmethod
    def get_task_details(cls):
        raise NotImplementedError("Stop method must be implemented")

    def execute_command(self, server_list, command, task, do_log=True, do_return_stdout=False):
        elk_logger_message = []
        try:
            if type(server_list) is not list or len(server_list) == 0:
                raise Exception("No Server - %s given to execute Command - %s" %(server_list, command))
            batch_count=len(server_list)
            starttime = datetime.datetime.now()
            logger.debug("Executing Command - %s" % command)
            if command is None or len(command.strip()) == 0:
                raise Exception("Command - %s is not given" % command)
            command_output = FabricHandler(hosts=server_list, command=command).exec_remote_command()
            logger.debug("command %s output %s" % (command, command_output))
            success_server_list=[]
            for server, response in command_output.items():
                if type(response) is not dict or len(response) == 0:
                    elk_logger_message.extend(
                        self._get_elk_format(
                            False, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                            exception="Unable to get Output of the Command, might be SSH Failed",
                            starttime=starttime, task=task, batch_count=batch_count, description=task
                        )
                    )
                    self.failed_server_list.append(server)
                for command, output in response.items():
                    if output[1] is False:
                        elk_logger_message.extend(
                            self._get_elk_format(
                                False, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3], exception=str(output[2]),
                                starttime=starttime, task=task, batch_count=batch_count, description=task
                            )
                        )
                        self.failed_server_list.append(server)
                        break
                if server not in self.failed_server_list:
                    success_server_list.append(server)

            if do_log:
                elk_logger_message.extend(self._get_elk_format(
                    True, success_server_list, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3], starttime=starttime,
                    task=task, batch_count=batch_count, description=task
                ))
        except Exception, e:
            status = False
            exception = str(e)
            logger.exception(e)
            self.failed_server_list.extend(server_list)
            elk_logger_message.extend(
                self._get_elk_format(status, server_list, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3], exception=exception, starttime=starttime, task=task)
            )
        finally:
            self._send_to_elk(elk_logger_message, detailed=True)
            if do_return_stdout:
                return {'server_list': self._get_update_batch_server_list(server_list),'output': command_output}
            else:
                return self._get_update_batch_server_list(server_list)

    def update_metadata(self, batch_servers, action='deployed'):
        success_servers = list(set(batch_servers) - set(self.failed_server_list))
        project_name = self.task_obj.project.name
        version = self.config.get('version')
        for server in success_servers:
            self.es.write_logs(category='report', server=server, project=project_name, action=action, version=version)
