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
import logging, inspect, datetime, time, json, requests

from orchestration.core.base import BaseOrchestration
from orchestration.core.staggered import StaggeredImplementation

from orchestration.utils.canary import CanaryImplementation
from orchestration.utils.edge_cache import EdgeCache
from orchestration.utils.fabric_handler import FabricHandler
from orchestration.utils.lb import LB
from orchestration.utils.zabbix_handler import ZabbixHandler

from space.utils.db_handler import DBHandler

logger = logging.getLogger(__name__)


class DCDeploy(BaseOrchestration, StaggeredImplementation):
    def __init__(self, task_obj=None, params={}, lbobj=None):
        BaseOrchestration.__init__(self, task_obj=task_obj, params=params)
        StaggeredImplementation.__init__(self)
        self.lbobj = LB(task_id=task_obj.id) if lbobj is None else lbobj
        self.cacheobj = EdgeCache(self.task_obj.id, self.params.get('zone'))
        self.dbobj = DBHandler()
        self.batch_servers_bypool = {}
        # The below param can be updated from ELK on object initialization, needed for Canary Implementation --- Discussion Later
        # deployed_server_list also contains the failed servers as well.
        self.deployed_server_list = []
        self.is_canary = False
        self.all_servers_with_status = []
        self.pool_servers_with_status = []
        self.success_healthcheck = []
        self.action = None
        self.is_hard = False
        self.taken_oop_to_is = False

    @classmethod
    def get_task_details(cls, action):
        try:
            if action.lower() == "restart":
                return ["take_oos", "session_drain", "stop_command", "start_command", "health_check", "take_is"]
            elif action.lower() == "deploy":
                return ["take_oos", "session_drain", "stop_command", "install", "start_command", "health_check", "take_is"]
            elif action.lower() == "hard_restart":
                return ["stop_command", "start_command"]
            elif action.lower() == "hard_deploy":
                return ["stop_command", "install", "start_command"]
            else:
                return []
        except Exception, e:
            logger.error(e)
            return {}

    def take_is(self, serverlist, datacenter):
        status = True
        exception = None
        elk_logger_message = []
        batch_count = len(serverlist)
        try:
            starttime = datetime.datetime.now()
            is_servers = []
            for server in serverlist:
                for item in self.all_servers_with_status:
                    if item.get('server', None) == server and item.get('enabled_status', False) is True:
                        is_servers.append(server)
                    elif item.get('server', None) == server and item.get('enabled_status') is False:
                        result = self.lbobj.get_lb_logs(server)
                        if result.get('action') != '':
                            if result.get('action') == 'force_disable' and result.get('user') == 'edge':
                                is_servers.append(server)
                                self.taken_oop_to_is = True
            logger.debug("servers receieved to take IS - %s, servers taking IS - %s for project - %s with Action Task ID - %s" % (serverlist, is_servers, self.task_obj.project, self.task_obj.id))
            response = self.lbobj.get_node_is(is_servers, datacenter)
            for server in response:
                status = response.get(server, False)
                if status is False:
                    self.failed_server_list.append(server)
                elk_logger_message.extend(
                    self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        starttime=starttime, description="Taking Server IS", batch_count=batch_count
                    )
                )

        except Exception, e:
            message = "Unable to take servers - %s IS, Error - %s" %(serverlist, e)
            logger.error(message)
            exception = message
            status = False
            elk_logger_message.extend(
                self._get_elk_format(
                    status, serverlist, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="Taking Server IS", batch_count=batch_count
                )
            )
            self.failed_server_list.extend(serverlist)
        finally:
            self._send_to_elk(elk_logger_message, detailed=True)
            return self._get_update_batch_server_list(serverlist)

    def healthcheck(self, serverlist, pool, datacenter):
        elk_logger_message = []
        starttime=datetime.datetime.now()
        batch_count = len(serverlist)
        success_servers = []
        failed_servers = serverlist
        success_healthcheck_servers = []
        uri = None
        recv = None
        try:
            healthcheck_string = self.config.get('healthcheck_string', None)
            if healthcheck_string is None or len(healthcheck_string) == 0:
                elk_logger_message.extend(self._get_elk_format(
                    True, failed_servers, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    starttime=starttime, description="Health Check Not Configured", batch_count=batch_count
                ))
                success_healthcheck_servers.extend(serverlist)
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
                    logger.debug("current pool_servers_with_status %s" % (self.pool_servers_with_status))
                    response, uri, recv = self.lbobj.check_http_healthcheck(failed_servers, self.pool_servers_with_status, pool, datacenter, healthcheck_string)
                    for server in failed_servers:
                        if response.get(server, False) is True:
                            success_servers.append(server)
                            success_healthcheck_servers.append(server)
                            elk_message.extend(self._get_elk_format(
                                True, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                                starttime=starttime, description="Health Check Verification", batch_count=batch_count
                            ))
                    failed_servers = list(set(failed_servers) - set(success_servers))
                    status = False if i == healthcheck_count-1 else None
                    elk_message.extend(self._get_elk_format(
                        status, failed_servers, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        starttime=starttime, description="Health Check Verification", batch_count=batch_count,
                        exception='Checked %s to match %s' % (uri, recv)
                    ))
                    self._send_to_elk(elk_message, detailed=True, delete_query=delete_query)
                    if len(failed_servers) == 0:
                        break
                self.failed_server_list.extend(failed_servers)
        except Exception, e:
            self.failed_server_list.extend(serverlist)
            message = "Unable to verify_healthcheck for servers - %s, Error - %s" %(serverlist, e)
            logger.error(message)
            exception = message
            status = False
            elk_logger_message.extend(
                self._get_elk_format(
                    status, serverlist, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="Health Check Verification", batch_count=batch_count
                )
            )
        finally:
            self._send_to_elk(elk_logger_message, detailed=True)
            self.success_healthcheck.extend(success_healthcheck_servers)
            return self._get_update_batch_server_list(serverlist)

    def take_oos(self, serverlist, datacenter):
        status = True
        exception = None
        elk_logger_message = []
        try:
            batch_count = len(serverlist)
            starttime = datetime.datetime.now()
            oos_servers = []
            already_oos_servers = []
            for server in serverlist:
                for item in self.all_servers_with_status:
                    if item.get('server', None) == server and item.get('enabled_status', True) is True:
                        oos_servers.append(server)
                    elif item.get('server', None) == server and item.get('enabled_status', True) is False:
                        already_oos_servers.append(server)
            logger.debug("servers receieved to take oos - %s, servers taking oos - %s, servers already oos %s, for project - %s with task - %s" % (serverlist, oos_servers, already_oos_servers, self.task_obj.project, self.task_obj.id))

            # setting server in logs which are already_oos_servers
            for server in already_oos_servers:
                status = None
                exception = 'server was OOS before this task'
                elk_logger_message.extend(
                    self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        exception=exception, starttime=starttime, description="Taking Server OOS", batch_count=batch_count,
                    )
                )

            # taking server [oos_servers] oos
            response = self.lbobj.get_node_oos(oos_servers, datacenter)
            for server in response:
                status = response.get(server, False)
                if status is False:
                    self.failed_server_list.append(server)
                elk_logger_message.extend(
                    self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        starttime=starttime, description="Taking Server OOS", batch_count=batch_count,
                    )
                )
        except Exception, e:
            message = "Unable to take servers - %s OOS, Error - %s" %(serverlist, e)
            logger.error(message)
            exception = message
            status = False
            elk_logger_message.extend(
                self._get_elk_format(
                    status, serverlist, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="Taking Server OOS", batch_count=batch_count
                )
            )
            self.failed_server_list.extend(serverlist)
        finally:
            elk_logger_message = self._send_to_elk(elk_logger_message, detailed=True)
            return self._get_update_batch_server_list(serverlist)

    def get_max_outpool_count(self, dc, pool, inpool_limit, all_servers):
        enable_count=0
        disable_count=0
        for servers in all_servers:
            if servers.get('enabled_status', False) is True:
                enable_count+=1
            else:
                disable_count+=1
        if enable_count == 0:
            logger.warn("For Task ID - %s, datacenter - %s, no server is IS, so returning all OOS server for deployment" %(self.task_obj.id, self.params.get('zone')))
            return disable_count
        total_count = len(all_servers)
        outpool_limit = int((total_count * (100-int(inpool_limit)))/100)
        return outpool_limit - disable_count if outpool_limit > disable_count else 0

    def session_drain(self, datacenter, pool, serverlist):
        delete_query = {"task" : "session_drain", "server": serverlist}
        try:
            sleep_time = 30
            starttime = datetime.datetime.now()
            elk_logger_message = []
            if len(serverlist) == 0:
                raise Exception("No Server given for checking member session for project - %s and task id - %s" %(self.task_obj.project, self.task_obj.id))
            count = 1    # Random Value Natural Number
            max_wait_time = int(self.dbobj.getValue("member_session_wait_time"))
            temp_max_wait_time = self.config.get("member_session_wait_time", None)
            if temp_max_wait_time is not None:
                max_wait_time = temp_max_wait_time
            if max_wait_time < 0:
                max_wait_time = 0
            session_start_time = time.time()
            while(count > 0 and time.time() <= (session_start_time + max_wait_time + sleep_time)):
                count, session_info = self.lbobj.get_member_session(serverlist, pool, datacenter)
                elk_message = []
                for server, session in session_info.items():
                    status = True if session == 0 else None
                    elk_message.extend(self._get_elk_format(
                        status, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                        starttime=starttime, description="waiting for session to drain", session=session
                    ))
                self._send_to_elk(elk_message, detailed=True, delete_query=delete_query)
                if time.time() > (session_start_time + max_wait_time):
                    count = -1
                if count > 0:
                    time.sleep(sleep_time)
        except Exception, e:
            exception = str(e)
            logger.error(exception)
            self.failed_server_list.extend(serverlist)
            elk_logger_message.extend(
                self._get_elk_format(
                    False, serverlist, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3],
                    exception=exception, starttime=starttime, description="waiting for session to drain"
                )
            )
            elk_logger_message = self._send_to_elk(elk_logger_message, detailed=True, delete_query=delete_query)
        finally:
            return self._get_update_batch_server_list(serverlist)

    def create_batch_bypool(self, serverlist=[], pool_info=[]):
        try:
            datacenter = self.params.get('zone', None)
            pool_info = self.params.get('pool_info', []) if not pool_info else pool_info
            servers = self.params.get('servers', []) if not serverlist else serverlist
            logger.info("Parameters receieved for Creating Batch by Pool for task id - %s, datacenter - %s, pool_info - %s, servers - %s" %(self.task_obj.id, datacenter, pool_info, servers))
            # Need to remove those servers which has been deployed or Failed
            servers = list(set(servers) - set(self.failed_server_list).union(self.deployed_server_list))
            logger.debug("Failed - %s, Deployed - %s, servers - %s" %(self.failed_server_list, self.deployed_server_list, servers))
            batch_server_bypool = {}

            for pooldetail in pool_info:
                pool = pooldetail.get('pool_name')
                inpool_threshold = pooldetail.get('inpool_threshold')
                # logger.info("Starting Task for deployment for TaskId - %s, ENV - %s, Pool - %s" %(task_id, datacenter, pool))
                # Don't update from here all_servers_with_status
                servers_with_status = self.lbobj.get_memberlist(pool, datacenter, status=True)
                logger.debug("All servers with status for task id - %s - %s" % (self.task_obj.id, servers_with_status))
                all_servers = [ servers_detail.get('server') for servers_detail in servers_with_status ]
                deployment_servers = list(set(all_servers).intersection(set(servers)))
                max_oop_count = self.get_max_outpool_count(datacenter, pool, inpool_threshold, servers_with_status)

                self.pool_servers_with_status.extend(servers_with_status)

                for server_detail in servers_with_status:
                    s = filter(lambda i: i['server'] == server_detail.get('server'), self.pool_servers_with_status)
                    if len(s) == 0:
                        self.pool_servers_with_status.append(server_detail)

                batch_server_bypool[pool] = []
                logger.info("Deployment Servers for task id - %s is - %s, max_oop_count - %s" % (self.task_obj.id, deployment_servers, max_oop_count))
                #  Need to handle if server in 2 pools
                if max_oop_count == 0:
                    # If MAX_OOP_COUNT == 0, we will check if there is any server which is OOS. If yes, we can do deployment on those server.
                    oos_batch_server = []
                    for server_detail in self.all_servers_with_status:
                        if server_detail.get('enabled_status') is False:
                            oos_server = server_detail.get('server')
                            if oos_server in deployment_servers:
                                oos_batch_server.append(oos_server)
                    if oos_batch_server:
                        batch_server_bypool[pool].append(oos_batch_server)

                while(len(deployment_servers) > 0 and max_oop_count > 0):
                    batch_servers = deployment_servers[0:max_oop_count]
                    del deployment_servers[0:max_oop_count]
                    batch_server_bypool[pool].append(batch_servers)
            self.batch_servers_bypool = batch_server_bypool
            logger.debug("Batch Created for id - %s, Batch - %s" %(self.task_obj.id, self.batch_servers_bypool))
        except Exception, e:
            message = "Unable to create batch for id - %s, dc - %s, pooldetail - %s, Error - %s" % (self.task_obj.id, datacenter, pool_info, e)
            logger.error(message)
            raise Exception(message)

    def deploy_server_by_pool(self):
        success_deployed = True
        datacenter = self.params.get('zone', None)
        failed_server_list_count = len(self.failed_server_list)
        for pool in self.batch_servers_bypool:
            serverlist = self.batch_servers_bypool[pool]
            if len(serverlist) == 0:
                message = "No Server avilable for task id - %s to deploy for pool - %s " %(self.task_obj.id, pool)
                logger.info(message)
                success_deployed = True
            else:
                logger.debug("Starting task - %s for id - %s on datacenter - %s on pool - %s with servers - %s"
                             % (inspect.getouterframes(inspect.currentframe(), 2)[1][3], self.task_obj.id, datacenter, pool, serverlist))

                # disable zabbix host configured for this pool
                is_scaling_enabled = self.config.get('scaling_enabled', False)
                logger.debug("is_scaling_enabled for task %s - %s" % (self.task_obj.id, is_scaling_enabled))
                zabbix_host = None
                zabbix_hostname = None
                if is_scaling_enabled:
                    zabbix_host = None
                    zabbix_hostname = None
                    pool_info = self.config.get('pool_info', {}).get(datacenter, [])
                    for item in pool_info:
                        if item.get('pool_name') == pool:
                            zabbix_host = item.get("zabbix_host")
                            zabbix_hostname = item.get("hostname")
                            break

                    logger.info("task - %s, scaling is enabled and hostname is - %s, zabbix is - %s" % (self.task_obj.id, zabbix_hostname, zabbix_host))
                    if zabbix_host is not None and zabbix_hostname is not None:
                        if type(zabbix_hostname) is list:
                            for host in zabbix_hostname:
                                zabbix_status = ZabbixHandler(zabbix=zabbix_host, hostname=host).take_action("disable")
                        else:
                            zabbix_status = ZabbixHandler(zabbix=zabbix_host, hostname=zabbix_hostname).take_action("disable")

                        self.es.write_logs(exception="disabled[{status}] scaling from {zabbix} for {hostname}".format(status=zabbix_status, zabbix=zabbix_host, hostname=str(zabbix_hostname)), level='info')

                for batch_servers in serverlist:

                    # set start time for the batch_servers
                    elk_logger_message = []
                    starttime = datetime.datetime.now()
                    for server in batch_servers:
                        elk_logger_message.extend(
                            self._get_elk_format(
                                True, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3], task=starttime.strftime("%Y-%m-%d %H:%M:%S"),
                                starttime=None, description="edge process started", batch_count=None
                            )
                        )

                    self._send_to_elk(elk_logger_message, detailed=True)

                    self.stop(datacenter, pool, batch_servers)
                    self.install(datacenter, pool, batch_servers)
                    self.start(datacenter, pool, batch_servers)
                    self.deployed_server_list.extend(batch_servers)
                    self.update_metadata(batch_servers)

                    # check status of task and raise error manual failed
                    current_task_status = self.dbobj.getActionInfoObj(id=self.task_obj.id).status.name
                    if current_task_status in ["MANUAL_FAILED", "REVOKED"]:
                        raise Exception("stopping task as task is %s" % current_task_status)

                    if len(self.failed_server_list) != failed_server_list_count:
                        logger.error("Few Servers has been failed via deployment and hence need to re-shuffle, Failed Server List - %s" %(self.failed_server_list))
                        failed_server_list_count = len(self.failed_server_list)
                        success_deployed=False
                        break

                    # set end time for the batch_servers
                    elk_logger_message = []
                    starttime = datetime.datetime.now()
                    for server in batch_servers:
                        elk_logger_message.extend(
                            self._get_elk_format(
                                True, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3], task=starttime.strftime("%Y-%m-%d %H:%M:%S"),
                                starttime=None, description="edge process completed", batch_count=None
                            )
                        )

                    self._send_to_elk(elk_logger_message, detailed=True)

                # enable zabbix scaling
                if is_scaling_enabled:
                    if zabbix_host is not None and zabbix_hostname is not None:
                        if type(zabbix_hostname) is list:
                            for host in zabbix_hostname:
                                zabbix_status = ZabbixHandler(zabbix=zabbix_host, hostname=host).take_action("enable")
                        else:
                            zabbix_status = ZabbixHandler(zabbix=zabbix_host, hostname=zabbix_hostname).take_action("enable")

                        self.es.write_logs(exception="enabled[{status}] scaling from {zabbix} for {hostname}".format(status=zabbix_status, zabbix=zabbix_host, hostname=str(zabbix_hostname)), level='info')

                if self.taken_oop_to_is is True:
                    # check if all servers are in deployed_server_list, via re-creating the batch
                    success_deployed=False
                    self.taken_oop_to_is = False

                if success_deployed is True:
                    for batch_servers in serverlist:
                        self.remove_tar(datacenter, batch_servers)
                if success_deployed is False:
                    # Need to Re-shuffle the Batch / would be re-shuffled from deploy_server_by_pool
                    break

        # this is very much required to return True or False from this method.
        return success_deployed

    def restart_server_by_pool(self):
        success_deployed = True
        datacenter = self.params.get('zone', None)
        failed_server_list_count = len(self.failed_server_list)
        for pool in self.batch_servers_bypool:
            serverlist = self.batch_servers_bypool[pool]
            if len(serverlist) == 0:
                message = "No Server avilable for task id - %s for restarting for pool - %s " %(self.task_obj.id, pool)
                logger.error(message)
                success_deployed = True
            else:
                logger.debug("Starting task - %s for id - %s on datacenter - %s on pool - %s with servers - %s"
                             % (inspect.getouterframes(inspect.currentframe(), 2)[1][3], self.task_obj.id, datacenter, pool, serverlist))
                for batch_servers in serverlist:
                    # Setting start time for batch servers
                    elk_logger_message = []
                    starttime = datetime.datetime.now()
                    for server in batch_servers:
                        elk_logger_message.extend(
                            self._get_elk_format(
                                True, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3], task=starttime.strftime("%Y-%m-%d %H:%M:%S"),
                                starttime=None, description="edge process started", batch_count=None
                            )
                        )

                    self._send_to_elk(elk_logger_message, detailed=True)
                    self.stop(datacenter, pool, batch_servers)
                    self.start(datacenter, pool, batch_servers)
                    self.deployed_server_list.extend(batch_servers)
                    self.update_metadata(batch_servers, action='restarted')
                    # check status of task and raise error manual failed
                    current_task_status = self.dbobj.getActionInfoObj(id=self.task_obj.id).status.name

                    if current_task_status in ["MANUAL_FAILED"]:
                        raise Exception("stopping task as task is %s" % current_task_status)
                    if len(self.failed_server_list) != failed_server_list_count:
                        logger.error("Few Servers has been failed via restart and hence need to re-shuffle, Failed Server List - %s" %(self.failed_server_list))
                        failed_server_list_count = len(self.failed_server_list)
                        success_deployed=False
                        break

                    # set end time for the batch_servers
                    elk_logger_message = []
                    starttime = datetime.datetime.now()
                    for server in batch_servers:
                        elk_logger_message.extend(
                            self._get_elk_format(
                                True, server, method=inspect.getouterframes(inspect.currentframe(), 2)[1][3], task=starttime.strftime("%Y-%m-%d %H:%M:%S"),
                                starttime=None, description="edge process completed", batch_count=None
                            )
                        )

                    self._send_to_elk(elk_logger_message, detailed=True)
                if success_deployed is False:
                    # Need to Re-shuffle the Batch
                    break

        # this is very much required to return True or False from this method.
        return success_deployed

    def deploy_staggered(self, datacenter):
        logger.info("Staggered Information for task id - %s, Staggered Batches - %s, Staggered Servers - %s, Current Staggered Label - %s, Canary - %s"
                    %(self.task_obj.id, self.staggered_batch, self.staggered_servers, self.get_current_staggered_label(), self.is_canary))
        while self.is_staggered and self.get_current_staggered_label() is not None:
            servers = self.staggered_servers.get(self.get_current_staggered_label(), [])
            if servers:
                self.create_batch_bypool(servers)
            else:
                self.update_next_staggered_label()
                continue
            need_to_update_staggered_label = self.deploy_server_by_pool()
            if need_to_update_staggered_label:
                current_staggered_servers = self.staggered_servers.get(self.get_current_staggered_label(), [])
                # No need to update the next staggered Label if all servers in current staggered label is not deployed.
                if not len(list(set(current_staggered_servers).intersection(set(self.deployed_server_list)))) == len(list(set(current_staggered_servers))):
                    need_to_update_staggered_label = False
                    message = "As server w- %s didn't get deployed due to Pool Strength, so raising Exception" % current_staggered_servers
                    logger.error(message)
                    raise Exception(message)
                # No need to update the next staggered Label if any of the servers in current staggered label failed.
                failed_server_list = set(current_staggered_servers).intersection(set(self.failed_server_list))
                if failed_server_list:
                    need_to_update_staggered_label = False
                    message = "As deployment on server - %s failed, so raising Exception" % failed_server_list
                    logger.error(message)
                    raise Exception(message)
                else:
                    if self.is_canary is True and self.get_current_staggered_label() not in self.non_canary_staggered_label:
                        # update data in cache
                        data = {
                            'current_staggered_label' : self.get_current_staggered_label(),
                            'staggered_servers' : self.staggered_servers,
                            'staggered_batch' : self.staggered_batch,
                            'failed_server_list' : self.failed_server_list,
                            'deployed_server_list' : self.deployed_server_list,
                            'all_servers_with_status' : self.all_servers_with_status,
                            'non_canary_staggered_label' : self.non_canary_staggered_label,
                            'params' : self.params,
                        }
                        # find staggered servers
                        staggered_servers = self.get_servers_till_current_staggered_label()
                        non_staggered_servers = self.get_servers_after_current_staggered_label(len(staggered_servers))
                        # Call Canary
                        response = CanaryImplementation.schedule_canary_task(action_task_id=self.task_obj.id,
                                                                             jira_id=self.config.get('jira_id'),
                                                                             project_name=self.task_obj.project.name,
                                                                             staggered_label=self.get_current_staggered_label(),
                                                                             zone=datacenter,
                                                                             staggered_servers=staggered_servers,
                                                                             non_staggered_servers=non_staggered_servers
                                                                             )
                        # Checking whether the task has been successfully scheduled or not.
                        logger.debug("Response from Canary Calling Method - %s" % response)
                        if response.get('status') is not True:
                            # Looks like Canary has not scheduled the task due to some config issue,
                            # so proceeding to next server.
                            if response.get('code') != 499:
                                self.es.write_logs(exception=response.get('message', "") + " - so proceeding further")
                                self.update_next_staggered_label()
                            else:
                                raise Exception(response.get('message'))
                        else:
                            # Writing Status to ELK
                            canary_uri = self.dbobj.getValue('canary_status_uri')
                            canary_uri = canary_uri.format(project=self.task_obj.project.name, id=str(self.task_obj.id))
                            message="Canary for %s [%s], %s" % (datacenter, self.get_current_staggered_label(), canary_uri)
                            self.es.write_logs(exception=message, level='info')
                            # Writing Cache Data to ELK, if needed in future
                            self.es.write_logs(category='canary', **data)
                            if response.get('code') in [200, 119]:
                                self.cacheobj.set(task_status='WAITING', **data)
                            # stopping the task
                            break
                    elif self.is_canary is True:
                        self.cacheobj.delete()
                        self.update_next_staggered_label()
                    else:
                        self.update_next_staggered_label()

    def canary_check(self):
        if self.action in ["deploy"]:
            self.is_canary = True if self.config.get("is_canary", False) is True else False
        else:
            self.is_canary = False

    def deploy(self,is_hard=False):
        try:
            self.is_hard = is_hard
            self.action = "deploy" if self.action is None else self.action
            self.canary_check()
            # Assuming is_staggered will always be True if is_canary is True
            self.is_staggered = True if self.config.get("is_staggered", False) is True or self.is_canary is True else False
            servers = self.params.get('servers', [])
            datacenter = self.params.get('zone', None)
            self.all_servers_with_status = self.lbobj.get_node_status(servers, datacenter)
            servers_with_status = []
            other_serverlist = []
            use_cache = False

            if self.is_canary is True:
                data = self.cacheobj.get()
                if type(data) is dict and len(data) > 0:
                    self.set_current_staggered_label(data.get('current_staggered_label'))
                    self.staggered_servers = data.get('staggered_servers')
                    self.staggered_batch = data.get('staggered_batch')
                    self.failed_server_list = data.get('failed_server_list')
                    self.deployed_server_list = data.get('deployed_server_list')
                    self.all_servers_with_status = data.get('all_servers_with_status')
                    self.non_canary_staggered_label = data.get('non_canary_staggered_label')
                    use_cache = True
                else:
                    # check whether the cache has been corrupted or it is fresh deployment.
                    # For now assuming fresh deployment
                    canary_pools = self.config.get('canary_pool', {}).get(datacenter, [])

                    main_pools = [pools.get('pool_name') for pools in self.params.get('pool_info', [])]
                    # canary_pools must be subset of main pools
                    canary_pools = set(canary_pools).intersection(set(main_pools))

                    if len(canary_pools) == 0:
                        canary_pools = main_pools
                        non_canary_pools = [pools.get('pool_name') for pools in self.params.get('pool_info', []) if pools.get('is_canary', True) is False]
                        canary_pools = list(set(canary_pools) - set(non_canary_pools))
                        rest_pools = non_canary_pools
                    else:
                        rest_pools = list(set(main_pools) - set(canary_pools))

                    for pool in canary_pools:
                        members_detail = self.lbobj.get_memberlist(pool, datacenter, status=True)
                        for member in members_detail:
                            if member.get('server') in servers:
                                servers_with_status.append(member)

                    for pool in rest_pools:
                        members_detail = self.lbobj.get_memberlist(pool, datacenter, status=True)
                        for member in members_detail:
                            if member.get('server') in servers:
                                # Check whether we have any any pool in canary pool config,
                                # if it is not treat this as main pool.
                                # if len(canary_pools) > 0:
                                other_serverlist.append(member)
                                # else:
                                #    servers_with_status.append(member)
            else:
                servers_with_status = self.all_servers_with_status

            if self.is_staggered is True:
                if use_cache is False:
                    staggered_batch = self.config.get('staggered_batch', None)
                    self.create_staggered_batches(serverlist=servers_with_status, otherserverlist=other_serverlist, staggered_batch=staggered_batch)
                self.deploy_staggered(datacenter)
            else:
                # The below is for non - Staggered Deployment and must be deployed on all given servers
                all_servers_has_been_deployed = False
                pool_info = self.params.get('pool_info', [])
                for pooldetail in pool_info:
                    all_servers_has_been_deployed=False
                    while all_servers_has_been_deployed is False:
                        # There is no meaning to create batch for all pools once, while we are deploying the build one pool at a time
                        self.create_batch_bypool(pool_info=[pooldetail])
                        all_servers_has_been_deployed = self.deploy_server_by_pool()
                if not len(self.params.get('servers')) == len(self.deployed_server_list):
                    raise Exception("Not Able to deploy on all servers due to pool strength for task id - %s datacenter - %s" %(self.task_obj.id, self.params.get('zone')))
                else:
                    logger.info("All servers has been deployed for task id - %s and datacenter - %s" %(self.task_obj.id, self.params.get('zone')))
        except Exception, e:
            logger.exception(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)

    def hard_deploy(self):
        try:
            logger.info("Executing hard deploy for project %s and task id %s" % (self.task_obj.project.name, self.task_obj.id))
            self.action = "hard_deploy"
            self.deploy(is_hard=True)
        except Exception, e:
            logger.error(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)

    def rollback(self):
        self.action = "rollback"
        self.deploy()

    def hard_rollback(self):
        self.action = "hard_rollback"
        self.deploy(is_hard=True)

    def restart(self, is_hard=False):
        try:
            self.is_hard = is_hard
            self.action = "restart"
            pool_info = self.params.get('pool_info', [])
            servers = self.params.get('servers', [])
            datacenter = self.params.get('zone', None)
            self.all_servers_with_status = self.lbobj.get_node_status(servers, datacenter)
            for pooldetail in pool_info:
                all_servers_has_been_restarted=False
                while all_servers_has_been_restarted is False:
                    # datacenter = self.params.get('dc', None)
                    # There is no meaning to create batch for all pools once, while we are deploying the build on one pool at a time, datacentere
                    self.create_batch_bypool(pool_info=[pooldetail])
                    all_servers_has_been_restarted = self.restart_server_by_pool()
            if not len(self.params.get('servers')) == len(self.deployed_server_list):
                raise Exception("Not Able to restart on all servers due to pool strength for task id - %s datacenter - %s" %(self.task_obj.id, self.params.get('zone')))
            else:
                logger.info("All servers has been deployed for task id - %s and datacenter - %s" %(self.task_obj.id, self.params.get('zone')))
        except Exception, e:
            logger.error(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)

    def hard_restart(self):
        try:
            logger.info("Executing hard restart for project %s and task id %s" % (self.task_obj.project.name, self.task_obj.id))
            self.action = "hard_restart"
            self.restart(is_hard=True)
        except Exception, e:
            logger.error(e)
            self.es.write_logs(exception=str(e))
            raise Exception(e)


    def install(self, datacenter, pool, serverlist):
        logger.info("install - %s for %s on DC - %s on pool - %s - %s" % (inspect.stack()[0][3], self.task_obj.id, datacenter, pool, serverlist))
        serverlist = self._get_update_batch_server_list(serverlist)
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

    def start(self, datacenter, pool, serverlist):
        logger.info("Starting task - %s for id - %s on datacenter - %s on pool - %s with servers - %s"
                    % (inspect.stack()[0][3], self.task_obj.id, datacenter, pool, serverlist))
        serverlist = self._get_update_batch_server_list(serverlist)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            # Call Start Command

            start_command = self.config.get("start_command", None)
            serverlist = self.execute_command(serverlist, start_command, "start_command")
            if self.is_hard is False:
                # Verify HealthCheck
                serverlist = self.healthcheck(serverlist, pool, datacenter)

                # Take only those servers IS which were already IS, before starting the task and return servers which has been taken IS
                serverlist = self.take_is(serverlist, datacenter)
        except Exception, e:
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
                raise Exception("start method failed on all servers - %s" % all_servers)

    def stop(self, datacenter, pool, serverlist):
        logger.info("Starting task - %s for id - %s on datacenter - %s on pool - %s with servers - %s is_hard - %s"
                    % (inspect.stack()[0][3], self.task_obj.id, datacenter, pool, serverlist,self.is_hard))
        serverlist = self._get_update_batch_server_list(serverlist)
        starttime = datetime.datetime.now()
        status = True
        exception = None
        all_servers = serverlist
        try:
            if self.is_hard is False:
                # This will return all the servers which has been taken OOS.
                serverlist = self.take_oos(serverlist, datacenter)

                # Check Member Sessions
                serverlist = self.session_drain(datacenter, pool, serverlist)

            # Call Stop Command
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
                # if entire batch got failed do health check on failed server and take is
                if self.action == "restart":
                    self.healthcheck(self.failed_server_list, pool, datacenter)
                    logger.info("server list for taking is - {s_list}".format(s_list=self.success_healthcheck))
                    if len(self.success_healthcheck) > 0:
                        serverlist = self.take_is(self.success_healthcheck, datacenter)
                raise Exception("stop method failed on all servers - %s" % all_servers)

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
