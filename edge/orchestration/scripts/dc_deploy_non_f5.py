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

# import future division
import logging, inspect, datetime

from orchestration.core.base import BaseOrchestration
from orchestration.utils.fabric_handler import FabricHandler
from space.utils.db_handler import DBHandler

logger = logging.getLogger(__name__)


class DCDeployNonF5(BaseOrchestration):
    def __init__(self, task_obj=None, params={}, lbobj=None):
        BaseOrchestration.__init__(self, task_obj=task_obj, params=params)
        self.dbobj = DBHandler()
        self.failed_server_list = []
        self.deployed_server_list = []

    @classmethod
    def get_task_details(cls, action):
        try:
            if action.lower() == "restart":
                return [ "stop_command", "start_command" ]
            elif action.lower() == "deploy":
                return [ "stop_command", "install", "start_command" ]
            else:
                return []
        except Exception, e:
            logger.error(e)
            return {}

    def __get_update_batch_server_list(self, serverlist):
        temp_serverlist = set(serverlist) - set(self.failed_server_list)
        return list(temp_serverlist)

    def deploy(self):
        try:
            servers = self.params.get('servers', [])
            datacenter = self.params.get('zone', [])
            for server in servers:
                batch_server = [server] if type(server) is not list else server
                self.stop(datacenter, batch_server)
                self.install(datacenter, batch_server)
                self.start(datacenter, batch_server)
                self.deployed_server_list.extend(batch_server)
                self.update_metadata(batch_server)
                if self.config.get('stop_on_failure') is True and len(self.failed_server_list) >= len(batch_server):
                    raise Exception("Task Deploy is got failed on server - %s and Stop on Failure is True,"
                                    " so failing the task" % batch_server)
                else:
                    self.remove_tar(datacenter, batch_server)
            logger.info("All servers has been deployed for task id - %s and datacenter - %s" % (
                self.task_obj.id, self.params.get('zone')))
        except Exception, e:
            logger.error(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)

    def remove_tar(self,datacenter, serverlist):
        serverlist = self._get_update_batch_server_list(serverlist)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            version = self.config.get('version', None)
            deliverables_prefix = version[:version.rfind('-')]
            get_deliverables_cmd = 'ls %s/%s-*' % (self.config.get('repo_dir'), deliverables_prefix)
            logger.debug("get_deliverables_cmd -- %s" % get_deliverables_cmd)
            cmd_output = self.execute_command(serverlist, get_deliverables_cmd, "get_old_deliverable", False, do_return_stdout=True)
            output = cmd_output.get('output', {})
            serverlist = cmd_output.get('server_list', [])
            build_no = []
            items_to_remove = []
            for server, result in output.items():
                for cmd, val in result.items():
                    for i in val:
                        if type(i) is list:
                            output_items = i
            output_items = [f for f in output_items if 'md5' not in f]
            for item in output_items:
                pivot = item.rfind('-')
                val = int(item[pivot + 1:].replace('.tar.gz', ''))
                build_no.append(val)
            build_no.sort()
            if len(build_no) > 3:
                logger.info(build_no)
                for item in output_items:
                    for num in build_no[0:-3]:
                        pivot = item.find(str(num))
                        if pivot > 0:
                            items_to_remove.append(item)
                            items_to_remove.append(item + ".md5")
                for build in items_to_remove:
                    remove_projects_cmd = 'rm -f %s' % (build)
                    delete_cmd = self.execute_command(serverlist, remove_projects_cmd, "delete_old_deliverable", False)
        except Exception as e:
            # by passing exception for analysis.
            logger.exception(e)
            status = True
            exception = str(e)
            # self.failed_server_list.extend(serverlist)

    def rollback(self):
        self.deploy()

    def restart(self):
        try:
            servers = self.params.get('servers', [])
            datacenter = self.params.get('zone', [])
            for server in servers:
                batch_server = [server] if type(server) is not list else server
                self.stop(datacenter, batch_server)
                self.start(datacenter, batch_server)
                self.deployed_server_list.extend(batch_server)
                self.update_metadata(batch_server, action='restarted')
                if self.config.get('stop_on_failure') is True and len(self.failed_server_list) >= len(batch_server):
                    raise Exception("Task Restart is got failed on server - %s and stop on Failure is True so failing the task" % batch_server)
            logger.info("All servers has been deployed for task id - %s and datacenter - %s" % (
                self.task_obj.id, self.params.get('zone')))
        except Exception, e:
            logger.exception(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)

    def install(self, datacenter, serverlist):
        logger.info("Starting method install for %s on DC - %s with servers - %s" % (self.task_obj.id, datacenter, serverlist))
        serverlist = self.__get_update_batch_server_list(serverlist)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            # 1 create mmtrepos dir (if not present)
            create_repo_dir_cmd = 'mkdir -p %s' % (self.config.get('repo_dir'))
            logger.debug("create_repo_dir_cmd %s" % create_repo_dir_cmd)
            serverlist = self.execute_command(serverlist, create_repo_dir_cmd, "create_repo_dir", False)

            # 2 download deliverable from repo server
            repo_server = self.dbobj.getValue('bizeye_url')[datacenter]
            deliverable_loc = "http://%s/%s/%s" % (repo_server, self.config.get('bizeye_folder').upper(),
                                                   self.config.get('version'))
            download_deliverable_cmd = "wget '%s' -O %s/%s" % (format(deliverable_loc), self.config.get('repo_dir'),
                                                               self.config.get('version'))
            logger.debug("download_deliverable_cmd %s" % download_deliverable_cmd)
            serverlist = self.execute_command(serverlist, download_deliverable_cmd, "install")

            deliverable_loc = "http://%s/%s/%s.md5" % (repo_server, self.config.get('bizeye_folder').upper(),
                                                       self.config.get('version'))
            download_md_cmd = "wget '%s' -O %s/%s.md5" % (format(deliverable_loc), self.config.get('repo_dir'),
                                                          self.config.get('version'))
            logger.debug("download_md_cmd %s" % download_md_cmd)
            serverlist = self.execute_command(serverlist, download_md_cmd, "download_md", False)

            # 3 MD5 checksum
            md5sum_cmd = "cd %s && md5sum -c %s/%s.md5" % (self.config.get('repo_dir'), self.config.get('repo_dir'), self.config.get('version'))
            logger.debug("md5sum_cmd %s" % md5sum_cmd)
            serverlist = self.execute_command(serverlist, md5sum_cmd, "md5sum", False)

            # 4 remove existing context
            rm_context = self.config.get('rm_context', False)
            context_dir = self.config.get('context_dir', None)
            if rm_context and context_dir:
                rm_context_dir_cmd = "rm -rf %s" % (context_dir)
                logger.info("rm_context_dir_cmd %s" % rm_context_dir_cmd)
                serverlist = self.execute_command(serverlist, rm_context_dir_cmd, "rm_context_dir", False)

            # 5 untar deliverable to create context
            untar_cmd = "tar -xf %s/%s -C /" % (self.config.get('repo_dir'), self.config.get('version'))
            logger.info("untar_cmd %s" % untar_cmd)
            serverlist = self.execute_command(serverlist, untar_cmd, "untar", False)

            # 6 set mmytu permissions
            if self.config.get('set_mmytu', True):
                ownership = self.config.get('set_owner', 'mmytu')
                set_mmytu_cmd = "chown -R {owner}:{owner} {context_dir}".format(owner=ownership, context_dir=context_dir)
                serverlist = self.execute_command(serverlist, set_mmytu_cmd, "set_mmytu", False)
        except Exception as e:
            logger.exception(e)
            status = False
            exception = str(e)
            self.failed_server_list.extend(serverlist)
            serverlist = self.__get_update_batch_server_list(serverlist)
        finally:
            status = True if status and len(serverlist) > 0 else False
            task = "COMPLETED" if status is True else "FAILED"
            self._send_to_elk(
                self._get_elk_format(status, all_servers, exception=exception, starttime=starttime, task=task)
            )
            if status is False:
                raise Exception("install method failed on all servers - %s" % all_servers)

    def start(self, datacenter, serverlist):
        logger.info("Starting task - %s for id - %s on datacenter - %s with servers - %s"
                    % (inspect.stack()[0][3], self.task_obj.id, datacenter, serverlist))
        serverlist = self.__get_update_batch_server_list(serverlist)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            # Call Start Command
            start_command = self.config.get("start_command", None)
            serverlist = self.execute_command(serverlist, start_command, "start_command")
        except Exception, e:
            logger.exception(e)
            status = False
            exception = str(e)
            self.failed_server_list.extend(serverlist)
            serverlist = self.__get_update_batch_server_list(serverlist)
        finally:
            status = True if status and len(serverlist) > 0 else False
            task = "COMPLETED" if status is True else "FAILED"
            self._send_to_elk(
                self._get_elk_format(status, all_servers, exception=exception, starttime=starttime, task=task)
            )
            if status is False:
                raise Exception("start method failed on all servers - %s" % all_servers)

    def stop(self, datacenter, serverlist):
        logger.info("Starting task - %s for id - %s on datacenter - %s with servers - %s"
                    % (inspect.stack()[0][3], self.task_obj.id, datacenter, serverlist))
        serverlist = self.__get_update_batch_server_list(serverlist)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            # Call Stop Command
            stop_command = self.config.get("stop_command", None)
            serverlist = self.execute_command(serverlist, stop_command, "stop_command")
        except Exception, e:
            logger.exception(e)
            status = False
            exception = str(e)
            self.failed_server_list.extend(serverlist)
            serverlist = self.__get_update_batch_server_list(serverlist)
        finally:
            status = True if status and len(serverlist) > 0 else False
            task = "COMPLETED" if status is True else "FAILED"
            self._send_to_elk(
                self._get_elk_format(status, all_servers, exception=exception, starttime=starttime, task=task)
            )
            if status is False:
                raise Exception("stop method failed on all servers - %s" % all_servers)
