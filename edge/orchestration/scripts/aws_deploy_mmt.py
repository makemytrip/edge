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
import logging, inspect, datetime, time

from orchestration.core.base import BaseOrchestration
from orchestration.utils.fabric_handler import FabricHandler
from space.utils.db_handler import DBHandler
from orchestration.utils.lb import LB

logger = logging.getLogger(__name__)


class AWSMmt(BaseOrchestration):
    def __init__(self, task_obj=None, params={}, lbobj=None):
        BaseOrchestration.__init__(self, task_obj=task_obj, params=params)
        self.lbobj = LB(task_id=task_obj.id) if lbobj is None else lbobj
        self.dbobj = DBHandler()
        self.failed_server_list = []
        self.deployed_server_list = []
        self.profile = self.config.get('profile')
        self.action = None
        self.aws_lb_info = self.config.get('aws_lb_info')
        self.all_servers_with_status = []
        self.all_instances = []
        self.already_oos_servers = []
        self.all_servers_with_instances = []
        self.success_healthcheck = []

    @classmethod
    def get_task_details(cls, action):
        try:
            if action.lower() == "restart":
                return [ "deregister", "session_drain", "stop", "start", "healthcheck", "register"]
            elif action.lower() == "deploy":
                return [ "deregister", "session_drain", "stop", "install", "start", "healthcheck", "register"]
            else:
                return []
        except Exception, e:
            logger.error(e)
            return {}

    def __get_update_batch_server_list(self, serverlist):
        temp_serverlist = set(serverlist) - set(self.failed_server_list)
        return list(temp_serverlist)

    def deregister(self, lb_name, profile_name, lb_type,server_list):
        try:
            servers_to_take_oos = []
            instances_to_take_oos = []
            elk_logger_message = []
            starttime = datetime.datetime.now()
            batch_count = 1
            for server in server_list:
                if server not in self.already_oos_servers:
                    servers_to_take_oos.append(server)
            for server in servers_to_take_oos:
                for instance in self.all_servers_with_instances:
                    if instance.get(server) is not None:
                        instances_to_take_oos.append(instance.get(server))
            logger.info("Servers to deregister - {server}".format(server=servers_to_take_oos))

            # setting server in logs which are already_oos_servers
            for server in self.already_oos_servers:
                status = None
                exception = 'server was already deregistered before this task'
                elk_logger_message.extend(
                    self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        exception=exception, starttime=starttime, description="Deregistering instance", batch_count=batch_count,
                    )
                )

            for instance in instances_to_take_oos:
                response = self.lbobj.take_aws_action(lb_name, [instance], "deregister", profile_name, lb_type)
                status_code = response.get('result').get('ResponseMetadata').get('HTTPStatusCode')
                status = True if status_code == 200 else False
                if status_code != 200:
                    self.failed_server_list.append(instance)
                for instance in self.all_servers_with_instances:
                    for key, val in instance.items():
                        if val == instance:
                            server = key
                elk_logger_message.extend(
                    self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        starttime=starttime, description="Deregistering instance", batch_count=batch_count,
                    )
                )
        except Exception, e:
            message = "Unable to deregister instances - %s, Error - %s" %(servers_to_take_oos, e)
            logger.error(message)
            exception = message
            status = False
            elk_logger_message.extend(
                self._get_elk_format(
                    status, server_list, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="Deregistering instance", batch_count=batch_count
                )
            )
            self.failed_server_list.extend(server_list)
        finally:
            elk_logger_message = self._send_to_elk(elk_logger_message, detailed=True)
            return self._get_update_batch_server_list(server_list)

    def register(self, lb_name, profile_name, lb_type, server_list):
        try:
            servers_to_take_oos = []
            instances_to_take_oos = []
            elk_logger_message = []
            starttime = datetime.datetime.now()
            batch_count = 1
            for server in server_list:
                if server not in self.already_oos_servers:
                    servers_to_take_oos.append(server)
            for server in servers_to_take_oos:
                for instance in self.all_servers_with_instances:
                    if instance.get(server) is not None:
                        instances_to_take_oos.append(instance.get(server))
            logger.info("Servers to take oos - {server}".format(server=servers_to_take_oos))

            # setting server in logs which are already_oos_servers
            for server in self.already_oos_servers:
                status = None
                exception = 'server was OOS before this task'
                elk_logger_message.extend(
                    self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        exception=exception, starttime=starttime, description="Taking Server OOS", batch_count=batch_count,
                    )
                )

            for instance in instances_to_take_oos:
                response = self.lbobj.take_aws_action(lb_name, [instance], "register", profile_name, lb_type)
                status_code = response.get('result').get('ResponseMetadata').get('HTTPStatusCode')
                status = True if status_code == 200 else False
                if status_code != 200:
                    self.failed_server_list.append(instance)
                for instance in self.all_servers_with_instances:
                    for key, val in instance.items():
                        if val == instance:
                            server = key
                elk_logger_message.extend(
                    self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        starttime=starttime, description="Taking Server OOS", batch_count=batch_count,
                    )
                )
        except Exception, e:
            message = "Unable to take servers - %s OOS, Error - %s" %(servers_to_take_oos, e)
            logger.error(message)
            exception = message
            status = False
            elk_logger_message.extend(
                self._get_elk_format(
                    status, server_list, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="Taking Server OOS", batch_count=batch_count
                )
            )
            self.failed_server_list.extend(server_list)
        finally:
            elk_logger_message = self._send_to_elk(elk_logger_message, detailed=True)
            return self._get_update_batch_server_list(server_list)

    def session_drain(self, lb_name, profile_name, lb_type, server_list):
        delete_query = {"task" : "session_drain", "server": server_list}
        elk_message = []
        try:
            sleep_time = self.config.get('session_drain_time', 600)
            starttime = datetime.datetime.now()
            elk_logger_message = []
            session_start_time = time.time()
            logger.info("Session drain time - %s" %(sleep_time))
            for server in server_list:
                elk_message.extend(self._get_elk_format(
                    True, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    starttime=starttime, description="Waiting for session to drain", session=0
                ))
            time.sleep(sleep_time)
            self._send_to_elk(elk_message, detailed=True, delete_query=delete_query)
        except Exception, e:
            exception = str(e)
            logger.error(exception)
            self.failed_server_list.extend(server_list)
            elk_logger_message.extend(
                self._get_elk_format(
                    False, server_list, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="waiting for session to drain"
                )
            )
            elk_logger_message = self._send_to_elk(elk_logger_message, detailed=True, delete_query=delete_query)
        finally:
            return self._get_update_batch_server_list(server_list)

    def healthcheck(self, lb_name, profile_name, lb_type, server_list):
        elk_logger_message = []
        starttime=datetime.datetime.now()
        success_servers = []
        failed_servers = server_list
        success_healthcheck_servers = []
        try:
            if self.config.get('check_healthcheck', True) is False:
                elk_logger_message.extend(self._get_elk_format(
                    True, failed_servers, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    starttime=starttime, description="Health Check Not Configured", batch_count=0
                ))
                success_healthcheck_servers.extend(server_list)
            else:
                healthcheck_count = self.config.get('healthcheck_count', 1)
                initial_delay = self.config.get('healthcheck_delay', 0)
                subsequent_delay = self.config.get('healthcheck_smart_delay', 0)
                time.sleep(initial_delay)
                for i in xrange(healthcheck_count):
                    delete_query = {"task": "healthcheck", "server": failed_servers}
                    elk_message = []
                    if (i != 0):
                        time.sleep(subsequent_delay)
                    for server in failed_servers:
                        response= self.lbobj.check_aws_healthcheck(lb_name, profile_name, lb_type, server)
                        status = True if response.get('response') is True else False
                        if response.get('response', False) is True:
                            success_servers.append(server)
                            success_healthcheck_servers.append(server)
                            elk_message.extend(self._get_elk_format(
                                True, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                                starttime=starttime, description="Health Check Verification", batch_count=0
                            ))
                    failed_servers = list(set(failed_servers) - set(success_servers))
                    elk_message.extend(self._get_elk_format(
                        status, failed_servers, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        starttime=starttime, description="Health Check Verification", batch_count=0,
                        exception='Healthcheck not ok'
                    ))
                    self._send_to_elk(elk_message, detailed=True, delete_query=delete_query)
                self.failed_server_list.extend(failed_servers)
        except Exception, e:
            self.failed_server_list.extend(server_list)
            message = "Unable to verify_healthcheck for servers - %s, Error - %s" %(server_list, e)
            logger.error(message)
            exception = message
            status = False
            elk_logger_message.extend(
                self._get_elk_format(
                    status, server_list, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="Health Check Verification", batch_count=0
                )
            )
        finally:
            self._send_to_elk(elk_logger_message, detailed=True)
            self.success_healthcheck.extend(success_healthcheck_servers)
            return self._get_update_batch_server_list(server_list)

    def stop(self, lb_name, profile_name, lb_type, server_list):
        logger.info("Starting task - %s for id - %s with servers - %s"
                    % (inspect.stack()[0][3], self.task_obj.id, server_list))
        serverlist = self._get_update_batch_server_list(server_list)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            # This method will deregister instances
            serverlist = self.deregister(lb_name,profile_name,lb_type,serverlist)
            # This method will perform session drain
            serverlist = self.session_drain(lb_name,profile_name,lb_type,serverlist)
            # Now perform stop command
            stop_command = self.config.get("stop_command", None)
            serverlist = self.execute_command(serverlist, stop_command, "stop_command")
        except Exception, e:
            logger.exception(e)
            status = False
            exception = str(e)
            self.failed_server_list.extend(serverlist)
            serverlist = self._get_update_batch_server_list(serverlist)
        finally:
            status = True if status and len(serverlist) > 0 else False
            task="COMPLETED" if status is True else "FAILED"
            self._send_to_elk(
                self._get_elk_format(status, all_servers, exception=exception, starttime=starttime, task=task)
            )
            if status is False:
                raise Exception("stop method failed on all servers - %s" % all_servers)

    def start(self, lb_name, profile_name, lb_type, server_list):
        logger.info("Starting task - %s for id - %s with servers - %s"
                    % (inspect.stack()[0][3], self.task_obj.id, server_list))
        serverlist = self._get_update_batch_server_list(server_list)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            start_command = self.config.get("start_command", None)
            serverlist = self.execute_command(serverlist, start_command, "start_command")
            # Perform healthcheck
            serverlist = self.healthcheck(lb_name,profile_name,lb_type,serverlist)
            # Register servers
            serverlist = self.register(lb_name,profile_name,lb_type,serverlist)
        except Exception, e:
            logger.exception(e)
            status = False
            exception = str(e)
            self.failed_server_list.extend(serverlist)
            serverlist = self._get_update_batch_server_list(serverlist)
        finally:
            status = True if status and len(serverlist) > 0 else False
            task="COMPLETED" if status is True else "FAILED"
            self._send_to_elk(
                self._get_elk_format(status, all_servers, exception=exception, starttime=starttime, task=task)
            )
            if status is False:
                raise Exception("start method failed on all servers - %s" % all_servers)

    def install(self, lb_name, profile_name, lb_type, server_list, datacenter):
        logger.info("install - %s for %s on LB - %s on profile - %s" % (inspect.stack()[0][3], self.task_obj.id, lb_name, profile_name))
        serverlist = self._get_update_batch_server_list(server_list)
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
            deliverable_loc = "http://%s/%s/%s" % (repo_server, self.config.get('bizeye_folder').upper(), self.config.get('version'))
            download_deliverable_cmd = "wget '%s' -O %s/%s" % (format(deliverable_loc), self.config.get('repo_dir'), self.config.get('version'))
            logger.debug("download_deliverable_cmd %s" % download_deliverable_cmd)
            serverlist = self.execute_command(serverlist, download_deliverable_cmd, "install")

            deliverable_loc = "http://%s/%s/%s.md5" % (repo_server, self.config.get('bizeye_folder').upper(), self.config.get('version'))
            download_md_cmd = "wget '%s' -O %s/%s.md5" % (format(deliverable_loc), self.config.get('repo_dir'), self.config.get('version'))
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

            # 7 custom command
            if self.config.get('custom_install_cmd', None) is not None:
                custom_cmd = self.config.get('custom_install_cmd')
                serverlist = self.execute_command(serverlist, custom_cmd, "custom_install_cmd", False)

        except Exception as e:
            logger.exception(e)
            status = False
            exception = str(e)
            self.failed_server_list.extend(serverlist)
            serverlist = self._get_update_batch_server_list(serverlist)
        finally:
            status = True if status and len(serverlist) > 0 else False
            task = "COMPLETED" if status is True else "FAILED"
            self._send_to_elk(
                self._get_elk_format(status, all_servers, exception=exception, starttime=starttime, task=task)
            )
            if status is False:
                raise Exception("install method failed on all servers - %s" % all_servers)

    def restart(self):
        try:
            self.action = "restart"
            aws_lb_info = self.params.get('aws_lb_info', [])
            server_list = self.params.get('servers', [])
            datacenter = self.params.get('zone', None)
            instance_list = self.params.get('instances',[])
            for key, val in self.aws_lb_info.items():
                for i in val:
                    current_instances = self.lbobj.get_instances(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'))
                    self.all_servers_with_instances.extend(current_instances.get('instances',[]))
                    self.all_instances.extend(current_instances.get(i.get('lb_name')))
            for server in server_list:
                if server in self.all_instances:
                    self.all_servers_with_status.append({server:'enabled'})
                else:
                    self.already_oos_servers.append(server)
                    self.all_servers_with_status.append({server:'disabled'})
            self.stop(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'),server_list=server_list)
            self.start(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'),server_list=server_list)
            self.deployed_server_list.extend(server_list)
            self.update_metadata(server_list, action='restarted')
            # check status of task and raise error manual failed
            current_task_status = self.dbobj.getActionInfoObj(id=self.task_obj.id).status.name
            if current_task_status in ["MANUAL_FAILED"]:
                raise Exception("stopping task as task is %s" % current_task_status)
        except Exception as e:
            logger.error(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)


    def deploy(self):
        try:
            self.action = "deploy"
            aws_lb_info = self.params.get('aws_lb_info', [])
            server_list = self.params.get('servers', [])
            datacenter = self.params.get('zone', None)
            instance_list = self.params.get('instances',[])
            for key, val in self.aws_lb_info.items():
                for i in val:
                    current_instances = self.lbobj.get_instances(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'))
                    self.all_servers_with_instances.extend(current_instances.get('instances',[]))
                    self.all_instances.extend(current_instances.get(i.get('lb_name')))
            for server in server_list:
                if server in self.all_instances:
                    self.all_servers_with_status.append({server:'enabled'})
                else:
                    self.already_oos_servers.append(server)
                    self.all_servers_with_status.append({server:'disabled'})
            self.stop(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'),server_list=server_list)
            self.install(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'),server_list=server_list,datacenter=datacenter)
            self.start(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'),server_list=server_list)
            self.deployed_server_list.extend(server_list)
            self.update_metadata(server_list)
            # check status of task and raise error manual failed
            current_task_status = self.dbobj.getActionInfoObj(id=self.task_obj.id).status.name
            if current_task_status in ["MANUAL_FAILED", "REVOKED"]:
                raise Exception("stopping task as task is %s" % current_task_status)
        except Exception as e:
            logger.error(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)
