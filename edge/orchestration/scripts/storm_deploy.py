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

import logging, datetime

from orchestration.core.base import BaseOrchestration
from space.utils.db_handler import DBHandler
from orchestration.utils.storm import Storm

logger = logging.getLogger(__name__)


class StormDeploy(BaseOrchestration):
    def __init__(self, task_obj=None, params={}, lbobj=None):
        BaseOrchestration.__init__(self, task_obj=task_obj, params=params)
        self.storm_obj = None
        self.dbobj = DBHandler()
        self.topology_config = {}

    @classmethod
    def get_task_details(cls, action):
        try:
            if action.lower() == "restart":
                return ["stop_command", "start_command"]
            elif action.lower() == "deploy":
                return ["stop_command", "install", "start_command"]
            else:
                return []
        except Exception, e:
            logger.error(e)
            return {}

    def _set_configs(self):
        topology_name = self.config.get('topology_name')
        if topology_name is None or len(topology_name.strip()) == 0:
            topology_name = self.task_obj.project.name
        self.topology_config['topology_name'] = topology_name
        wait_time = self.config.get('kill_wait_time', 60)
        self.topology_config['wait_time'] = wait_time
        self.topology_config['java_params'] = self.config.get('java_params', None)
        class_name = self.config.get('class_name', None)
        if class_name is None:
            raise Exception("Class Name is Required Parameter in Project Configs.")
        self.topology_config['class_name'] = class_name
        class_params = self.config.get('class_params', None)
        self.topology_config['class_params'] = class_params
        storm_binary_path = "%s/bin/%s" % (self.config.get('storm_dir'), self.config.get('storm_binary', 'storm'))
        self.topology_config['storm_binary_path'] = storm_binary_path
        deliverable_version = self.config.get('version')
        if deliverable_version.strip().endswith('tar.gz') is True:
            self.topology_config['tar_deployment'] = True
        else:
            self.topology_config['tar_deployment'] = False

    def restart(self):
        zone = self.params.get('zone')
        nimbus_server_list = self.params.get('nimbus_server_list')
        servers = self.params.get('servers')
        protocol = self.config.get('protocol', "http")
        self._set_configs()
        for server_detail in nimbus_server_list:
            host = server_detail.get('server')
            port = server_detail.get('port')
            version = server_detail.get('version')
            java_config_params = server_detail.get('java_params', None)
            class_config_params = server_detail.get('class_params', None)
            if host in servers:
                self.storm_obj = Storm(host, port, version, protocol)
                self.stop(host, zone, raise_on_failure=True)
                self.start(host, zone, java_config_params, class_config_params)
                self.update_metadata([host])

    def deploy(self):
        zone = self.params.get('zone')
        nimbus_server_list = self.params.get('nimbus_server_list')
        servers = self.params.get('servers')
        protocol = self.config.get('protocol', "http")
        self._set_configs()
        for server_detail in nimbus_server_list:
            host = server_detail.get('server')
            port = server_detail.get('port')
            version = server_detail.get('version')
            java_config_params = server_detail.get('java_params', None)
            class_config_params = server_detail.get('class_params', None)
            if host in servers:
                self.storm_obj = Storm(host, port, version, protocol)
                self.stop(host, zone)
                self.install(host, zone)
                self.start(host, zone, java_config_params, class_config_params)
                self.update_metadata([host])

    def stop(self, server, zone, raise_on_failure=False):
        logger.debug("Starting method Stop on server - %s" %(server))
        start_time = datetime.datetime.now()
        message = None
        status = True
        try:
            topology_name = self.topology_config.get('topology_name')
            wait_time = self.topology_config.get('wait_time')
            response = self.storm_obj.kill_topology(topology_name, wait_time, raise_on_failure)
            if response.get('status') is True and response.get('message', None) is not None:
                self.es.write_logs(exception=response.get('message') + " however proceeding", level='warn')
                status = None
            if response.get('status') is False:
                logger.error("Unable to Kill Topology from Storm Host - %s, Error - %s"
                                %(self.storm_obj.uri, response.get('message')))
        except Exception, e:
            logger.exception(e)
            message = str(e)
            status = False
        finally:
            task = "COMPLETED" if status is True or None else "FAILED"
            self._send_to_elk(self._get_elk_format(status, server, exception=message, starttime=start_time, task="stop_command"), detailed=True)
            self._send_to_elk(self._get_elk_format(status, server, exception=message, starttime=start_time, task=task))
            if status is False:
                raise Exception("Unable to run stop_command on server - %s" % server)

    def install(self, server, zone):
        logger.info("Starting method install on server - %s" % server)
        status = True
        exception = None
        md5_checksum = False
        tar_deployment = False
        try:
            start_time = datetime.datetime.now()
            server_list = server if type(server) is list else [server]
            server_list = self._get_update_batch_server_list(server_list)
            if len(server_list) == 0:
                raise Exception("No Server Pending to deploy")
            create_repo_dir_cmd = 'mkdir -p %s' % (self.config.get('repo_dir'))
            logger.debug("create_repo_dir_cmd %s" % create_repo_dir_cmd)
            server_list = self.execute_command(server_list, create_repo_dir_cmd, "create_repo_dir", False)

            # 2 download deliverable from repo server
            repo_server = self.dbobj.getValue('bizeye_url')[zone]
            deliverable_version = self.config.get('version')
            md5_checksum = self.config.get('md5_checksum', False)
            if self.topology_config['tar_deployment'] is True:
                md5_checksum = True
                tar_deployment = True

            deliverable_loc = "http://%s/%s/%s" % (repo_server, self.config.get('bizeye_folder').upper(), deliverable_version)
            download_deliverable_cmd = "wget '%s' -O %s/%s" % (format(deliverable_loc), self.config.get('repo_dir'), deliverable_version)
            logger.debug("download_deliverable_cmd %s" % download_deliverable_cmd)
            task_name = "install" if md5_checksum is False else "download_deliverable"
            do_log = True if md5_checksum is False else False
            server_list = self.execute_command(server_list, download_deliverable_cmd, task_name, do_log)

            if md5_checksum:
                deliverable_loc = "http://%s/%s/%s.md5" % (repo_server, self.config.get('bizeye_folder').upper(), self.config.get('version'))
                download_md_cmd = "wget '%s' -O %s/%s.md5" % (format(deliverable_loc), self.config.get('repo_dir'), self.config.get('version'))
                logger.debug("download_md_cmd %s" % download_md_cmd)
                server_list = self.execute_command(server_list, download_md_cmd, "download_md", False)

                # 3 MD5 checksum
                md5sum_cmd = "cd %s && md5sum -c %s/%s.md5" % (self.config.get('repo_dir'), self.config.get('repo_dir'), self.config.get('version'))
                logger.debug("md5sum_cmd %s" % md5sum_cmd)
                task_name = "install" if tar_deployment is False else "md5sum"
                do_log = True if tar_deployment is False else False
                server_list = self.execute_command(server_list, md5sum_cmd, task_name, do_log)

            if tar_deployment is True:
                rm_context = self.config.get('rm_context', False)
                context_dir = self.config.get('context_dir', None)
                if rm_context and context_dir:
                    rm_context_dir_cmd = "rm -rf %s" % (context_dir)
                    logger.info("rm_context_dir_cmd %s" % rm_context_dir_cmd)
                    server_list = self.execute_command(server_list, rm_context_dir_cmd, "rm_context_dir", False)

                # 5 untar deliverable to create context
                untar_cmd = "tar -xf %s/%s -C /" % (self.config.get('repo_dir'), self.config.get('version'))
                logger.info("untar_cmd %s" % untar_cmd)
                server_list = self.execute_command(server_list, untar_cmd, "install", True)

            if server not in server_list:
                raise Exception("Unable to complete Install Method on server - %s" %(server))
        except Exception, e:
            logger.exception(e)
            status = False
            exception = str(e)
        finally:
            task = "COMPLETED" if status is True else "FAILED"
            self._send_to_elk(
                self._get_elk_format(status, server_list, exception=exception, starttime=start_time, task=task)
            )
            if status is False:
                raise Exception("Unable to run install method on server - %s" % server)

    def start(self, server, zone, java_config_params, class_config_params):
        logger.debug("Starting method Start on server - %s" %(server))
        start_time = datetime.datetime.now()
        message = None
        status = True
        try:
            server_list = server if type(server) is list else [server]
            topology_name = self.topology_config.get('topology_name')
            if self.topology_config.get('tar_deployment', False) is True:
                jar_path = "%s/%s" %(self.config.get('context_dir'), self.config.get('jar_version'))
            else:
                jar_path = "%s/%s" % (self.config.get('repo_dir'), self.config.get('version'))
            start_cmd = "%s jar %s" %(self.topology_config.get('storm_binary_path'), jar_path)
            # Java Params
            if java_config_params is not None:
                start_cmd = start_cmd + " %s" %(java_config_params)
            elif java_config_params is None and self.topology_config.get('java_params') is not None:
                start_cmd = start_cmd + " %s" %(self.topology_config.get('java_params'))
            start_cmd = start_cmd + " %s" % (self.topology_config.get('class_name'))
            # Class Params
            if class_config_params is not None:
                start_cmd = start_cmd + " %s" %(class_config_params)
            elif class_config_params is None and self.topology_config.get('class_params') is not None:
                start_cmd = start_cmd + " %s" %(self.topology_config.get('class_params'))
            logger.info("Executing Command - %s on server - %s" %(start_cmd, server_list))
            server_list = self.execute_command(server_list, start_cmd, "start_command", False)
            if server not in server_list:
                raise Exception("Unable to Run Start Command - %s on server - %s" %(start_cmd, server_list))
            if self.storm_obj.get_topology_id(topology_name) is None:
                raise Exception("Unable to Start Topology with Command - %s on server - %s" % (start_cmd, server_list))
            self._send_to_elk(self._get_elk_format(status, server, exception=message, starttime=start_time, task="start_command"), detailed=True)
        except Exception, e:
            logger.exception(e)
            message = str(e)
            status = False
        finally:
            task = "COMPLETED" if status is True else "FAILED"
            self._send_to_elk(self._get_elk_format(status, server, exception=message, starttime=start_time, task=task))
            if status is False:
                raise Exception("Unable to run start_command on server - %s" % server)
