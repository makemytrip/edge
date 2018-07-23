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

"""This file will be used to get all information from LBManager eventually from F5."""

import json, time
import logging
import requests

from space.utils.db_handler import DBHandler
from space.models import Configs
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class LB:
    """This class will be used for doing all operations with LBManager."""

    def __init__(self, use_cache=0, task_id=None):
        """Initializing Method."""
        self.lbhost = Configs().getValue("lbhost")
        self.lbuser = Configs().getValue("lbuser")
        self.lbtimeout = int(Configs().getValue("lbtimeout"))
        self.use_cache = use_cache
        self.lb_retry_delay = int(Configs().getValue("lb_retry_delay"))
        self.task_id = task_id

    def get_pool_info(self, pool, dc):
        """This method will return the information about the given pool."""
        pool_api = "ltm/api"
        uri = "http://%s/%s" %(self.lbhost, pool_api)
        payload = {
            "user" : self.lbuser,
            "data_center" : dc,
            "search_name" : pool,
            "wildcards" : 0,
            "use_cache" : self.use_cache,
        }
        try:
            response = None
            lbretry = int(Configs().getValue("lbretry"))
            logger.debug("Parameters for fetching Pool information, URL - %s PAYLOAD - %s" %(uri, payload))
            while lbretry >= 0:
                try:
                    response = requests.post(uri, data=payload, timeout=self.lbtimeout)
                    if response.status_code != 200:
                        raise Exception("%s-%s" %(response.status_code, response.text))
                    break
                except Exception, e:
                    lbretry -= 1
                    time.sleep(self.lb_retry_delay)
                    if lbretry > 0:
                        logger.error("Unable to get pool information of pools - %s, dc - %s, Getting Error - %s, so retrying"
                                     % (pool, dc, e))
                    else:
                        raise Exception("Unable to get pool information of pools - %s, dc - %s, Getting Error - %s"
                                        % (pool, dc, e))

            if response.status_code == 200:
                data = response.json()
                logger.debug("Response Received - %s" % data)
                if data['error'] == 'None':
                    return data.get('pool_dict')
                else:
                    error_message = data.get('message', None)
                    raise Exception(error_message)
            else:
                message = "status_code - %s, Error - %s" %(response.status_code, response.text)
                raise Exception(message)
        except Exception, e:
            message = "Unable to get pool information of pools - %s, dc - %s, Getting Error - %s" %(pool, dc, e)
            logger.error(message)
            raise Exception(message)

    def get_member_session(self, server, pool, dc):
        """This method will return no. of session on the given server."""
        try:
            pool_info = self.get_pool_info(pool, dc)
            logger.debug("Pool Information fetched for Pool - %s is %s" %(pool, pool_info))
            serverlist = server if type(server) is list else [server]
            member_session = {}
            max_session = 0
            for pool in pool_info:
                for serverkey in pool_info[pool]:
                    keyserver = serverkey.split(":")[0]
                    if keyserver in serverlist:
                        if keyserver in member_session:
                            member_session[keyserver] = member_session[keyserver] + int(pool_info[pool][serverkey]['sessions'])
                        else:
                            member_session[keyserver] = int(pool_info[pool][serverkey]['sessions'])
                        if member_session[keyserver] > max_session:
                            max_session = member_session[keyserver]
            return max_session, member_session
        except Exception, e:
            message = "Unable to get member session information for server - %s, Error - %s" %(server, e)
            logger.error(message)
            raise Exception(message)

    def get_memberlist(self, pool, dc, status=False):
        """This method will be used to get members of a pool."""
        try:
            pool_info = self.get_pool_info(pool, dc)
            logger.debug("Pool Information fetched for Pool - %s is %s" %(pool, pool_info))
            serverlist=[]
            for pool in pool_info:
                for serverkey in pool_info[pool]:
                    server = serverkey.split(":")[0]
                    port = serverkey.split(":")[1]
                    enable_status = pool_info[pool][serverkey].get('enabled_status', False)
                    enable_status = True if enable_status == "ENABLED_STATUS_ENABLED" else False
                    if status is True:
                        serverlist.append({'server': server, 'enabled_status' : enable_status, 'port': port })
                    else:
                        serverlist.append(server)
            # Need to use SET before return
            return list(serverlist)
        except Exception, e:
            message="Unable to get serverlist for pool - %s, dc - %s, Error - %s" %(pool, dc, e)
            logger.error(message)
            raise Exception(message)

    def get_node_status(self, serverlist, dc):
        """This is Not Working because i don't have the clarity till now."""
        node_api = "ltm/node"
        uri = "http://%s/%s" %(self.lbhost, node_api)
        server = ",".join(serverlist) if type(serverlist) is list else serverlist

        payload = {
            "user" : self.lbuser,
            "data_center" : dc,
            "search_name" : server,
            "wildcards" : 0,
            "use_cache" : self.use_cache,
        }
        node_detail = []
        try:
            lbretry = int(Configs().getValue("lbretry"))
            logger.debug("Parameters for fetching Node information, URL - %s PAYLOAD - %s" %(uri, payload))
            while lbretry >= 0:
                try:
                    response = requests.post(uri, data=payload, timeout=self.lbtimeout)
                    if response.status_code != 200:
                        raise Exception("%s-%s" %(response.status_code, response.text))
                    break
                except Exception, e:
                    lbretry-=1
                    time.sleep(self.lb_retry_delay)
                    if lbretry > 0:
                        logger.error("Unable to get status of server - %s, dc - %s, Getting Error - %s, so retrying"
                                     % (server, dc, e))
                    else:
                        raise Exception("Unable to get status of server - %s, dc - %s, Getting Error - %s"
                                        % (server, dc, e))
            if response.status_code == 200:
                data = response.json()
                logger.debug("Response Received - %s" % data)
                if data['error'] =='None':
                    for server, value in data.get('node_dict', {}).items():
                        server_status = True if value.get('enabled_status',None) == 'ENABLED_STATUS_ENABLED' else False
                        node_detail.append({'server' : server, 'enabled_status': server_status})
                    return node_detail
                else:
                    error_message = data.get('message', None)
                    raise Exception(error_message)
            else:
                message = "status_code - %s, Error - %s" %(response.status_code, response.text)
                raise Exception(message)
        except Exception, e:
            message = "Unable to get status of server - %s, dc - %s, Getting Error - %s" %(server, dc, e)
            logger.error(message)
            raise Exception(message)

    def take_node_action(self, server, dc, action):
        """This method will be used to take action (IS/OOS) on the server from LBManager."""
        node_api = "ltm/change_node_state"
        uri = "http://%s/%s" %(self.lbhost, node_api)
        payload = {
            "user" : self.lbuser,
            "data_center" : dc,
            "pool" : "node",
            "member" : server,
            "port" : 0,
            "action" : action,
            "reason": "Edge Task %s" % self.task_id
        }
        try:
            lbretry = int(Configs().getValue("lbretry"))
            logger.debug("Parameters for Node Action, URL - %s PAYLOAD - %s" %(uri, payload))
            while lbretry >= 0:
                try:
                    response = requests.post(uri, data=payload, timeout=self.lbtimeout)
                    if response.status_code != 200:
                        raise Exception("%s-%s" %(response.status_code, response.text))
                    break
                except Exception, e:
                    lbretry-=1
                    time.sleep(self.lb_retry_delay)
                    if lbretry > 0:
                        logger.error("Unable to perform action - %s on server - %s on dc - %s, Getting Error - %s, so retrying"
                                     % (action, server, dc, e))
                    else:
                        raise Exception("Unable to perform action - %s on server - %s on dc - %s, Getting Error - %s"
                                        % (action, server, dc, e))

            if response.status_code == 200:
                data = response.json()
                logger.debug("Response Received - %s" % data)
                if data['result'] is True:
                    return True
                else:
                    error_message = data.get('message', None)
                    raise Exception(error_message)
            else:
                message = "status_code - %s, Error - %s" %(response.status_code, response.text)
                raise Exception(message)
        except Exception, e:
            message = "Unable to perform action - %s on server - %s on dc - %s, Getting Error - %s" %(action, server, dc, e)
            logger.error(message)
            raise Exception(message)

    def get_node_oos(self, server, dc):
        """This method will be used to take server OOS."""
        try:
            status = {}
            serverlist = server if type(server) is list else [server]
            for server in serverlist:
                try:
                    status[server] = self.take_node_action(server, dc, action="force_disable")
                except Exception, e:
                    status[server] = False
                    logger.error(e)
            return status
        except Exception, e:
            logger.error(e)
        finally:
            return status

    def get_node_is(self, server, dc):
        """This method will be used to take server IS."""
        try:
            status = {}
            serverlist = server if type(server) is list else [server]
            for server in serverlist:
                try:
                    status[server] = self.take_node_action(server, dc, action="enable")
                except Exception, e:
                    status[server] = False
                    logger.error(e)
            return status
        except Exception, e:
            logger.error(e)
        finally:
            return status

    def get_aws_lb_info(self, lb_name='', profile_name='mmt', lb_type='classic'):
        """This method will get detailed status of lb"""
        node_api = "aws/elb_api/"
        uri = "http://%s/%s" %(self.lbhost, node_api)
        payload = {
            "search_name": lb_name,
            "profile_name": profile_name,
            "lb_type": lb_type
        }
        try:
            lbretry = int(Configs().getValue("lbretry"))
            while lbretry >= 0:
                try:
                    response = requests.post(uri, data=payload, timeout=self.lbtimeout, auth=HTTPBasicAuth('<lb_user>', '<lb_pass>'))
                    if response.status_code != 200:
                        raise Exception("%s-%s" %(response.status_code, response.text))
                    break
                except Exception, e:
                    lbretry-=1
                    time.sleep(self.lb_retry_delay)
                    if lbretry > 0:
                        logger.error("Unable to get info for lb - %s Getting Error - %s, so retrying"
                                     % (lb_name, e))
                    else:
                        raise Exception("Unable to get info for lb - %s Getting Error - %s"
                                        % (lb_name, e))
            if response.status_code == 200:
                data_resp = response.json()
                if data_resp.get('error') is None:
                    return data_resp.get('data')[0]
                else:
                    message = "Error getting LB Info - %s" %(data_resp.get('error'))
                    raise Exception(message)
            else:
                message = "status_code - %s, Error - %s" %(response.status_code, response.text)
                raise Exception(message)
        except Exception, e:
            message = "Unable to get info for lb - %s Getting Error - %s" %(lb_name, e)
            logger.error(message)
            raise Exception(message)

    def get_instances(self, lb_name='', profile_name='mmt', lb_type='classic'):
        """This method will be used to get number of instances"""
        instances = {lb_name:[],'instances':[]}
        try:
            lb_info = self.get_aws_lb_info(lb_name, profile_name, lb_type) 
            lb_instance = lb_info.get(lb_name, None).get('instances', None)
            for instance in lb_instance:
                i_id = instance.get('Info').get('private_ip_address')
                instances[lb_name].append(i_id)
                instances['instances'].append({i_id:instance.get('InstanceId')})
            return instances
        except Exception as e:
            message = "Unable to get instances for lb - %s, profile - %s" %(lb_name, profile_name)
            logger.error(message)
            raise Exception(message)

    def get_session_drain_time(self, lb_name='', profile_name='mmt', lb_type='classic'):
        drain_time = 0
        try:
            lb_info = self.get_aws_lb_info(lb_name, profile_name, lb_type) 
            drain_time = lb_info.get(lb_name, None).get('health_check', None).get('Timeout', 10)
        except Exception as e:
            message = "Unable to get session drain time for lb - %s, profile - %s" %(lb_name, profile_name)
            logger.error(message)
            raise Exception(message)
        finally:
            return drain_time

    def check_aws_healthcheck(self, lb_name='', profile_name='mmt', lb_type='classic', server=''):
        try:
            status = {}
            healthcheck_url = None
            lb_info = self.get_aws_lb_info(lb_name, profile_name, lb_type) 
            url = lb_info.get(lb_name, None).get('health_check', None).get('Target', '')
            healthcheck_url = url.split(":",1)[1]
            uri = "http://"+server+":"+healthcheck_url
            request = requests.get(uri)
            response = request.json()
            logger.info("Healthcheck response - %s" %(response))
            status['status_code'] = request.status_code
            status['response'] = True
        except Exception as e:
            message = "healthcheck failed for server - %s, endpoint - %s, status - %s" %(server, healthcheck_url, request.status_code)
            logger.error(message)
            status['status_code'] = request.status_code
            status['response'] = False
        finally:
            return status

    def take_aws_action(self, load_balancer, instance_list, action, profile_name, lb_type):
        """This method will deregister/register instance from LB"""
        node_api = "aws/change_member_state/"
        uri = "http://%s/%s" %(self.lbhost, node_api)
        payload = {
            "server_ips": ",".join(instance_list),
            "state": action,
            "load_balancer": load_balancer,
            "profile_name": profile_name,
            "lb_type": lb_type
        }
        logger.info(payload)
        try:
            lbretry = int(Configs().getValue("lbretry"))
            while lbretry >= 0:
                try:
                    response = requests.post(uri, data=payload, timeout=self.lbtimeout, auth=HTTPBasicAuth('<lb_user>', '<lb_pass>'))
                    if response.status_code != 200:
                        raise Exception("%s-%s" %(response.status_code, response.text))
                    break
                except Exception, e:
                    lbretry-=1
                    time.sleep(self.lb_retry_delay)
                    if lbretry > 0:
                        logger.error("Unable to perform action - %s on lb - %s Getting Error - %s, so retrying"
                                     % (action, load_balancer, e))
                    else:
                        raise Exception("Unable to perform action - %s on lb - %s Getting Error - %s"
                                        % (action, load_balancer, e))
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                message = "status_code - %s, Error - %s" %(response.status_code, response.text)
                raise Exception(message)
        except Exception, e:
            message = "Unable to perform action - %s on lb - %s Getting Error - %s" %(action, load_balancer, e)
            logger.error(message)
            raise Exception(message)

    def take_pool_action(self, server, dc, pool, port, action):
        """This method will be used to take action (IS/OOS) on the pool from LBManager."""
        node_api = "ltm/change_member_state"
        uri = "http://%s/%s" %(self.lbhost, node_api)
        payload = {
            "user" : self.lbuser,
            "data_center" : dc,
            "pool" : pool,
            "member" : server,
            "port" : port,
            "action" : action,
            "reason": "Edge Task %s" % self.task_id
        }
        try:
            lbretry = int(Configs().getValue("lbretry"))
            logger.debug("Parameters for Node Action, URL - %s PAYLOAD - %s" %(uri, payload))
            while lbretry >= 0:
                try:
                    response = requests.post(uri, data=payload, timeout=self.lbtimeout)
                    if response.status_code != 200:
                        raise Exception("%s-%s" %(response.status_code, response.text))
                    break
                except Exception, e:
                    lbretry-=1
                    time.sleep(self.lb_retry_delay)
                    if lbretry > 0:
                        logger.error("Unable to perform action - %s on server - %s on dc - %s, Getting Error - %s, so retrying"
                                     % (action, server, dc, e))
                    else:
                        raise Exception("Unable to perform action - %s on server - %s on dc - %s, Getting Error - %s"
                                        % (action, server, dc, e))

            if response.status_code == 200:
                data = response.json()
                logger.debug("Response Received - %s" % data)
                if data['result'] is True:
                    return True
                else:
                    error_message = data.get('message', None)
                    raise Exception(error_message)
            else:
                message = "status_code - %s, Error - %s" %(response.status_code, response.text)
                raise Exception(message)
        except Exception, e:
            message = "Unable to perform action - %s on server - %s on dc - %s, Getting Error - %s" %(action, server, dc, e)
            logger.error(message)
            raise Exception(message)

    def get_pool_oos(self, server, dc, pool, servers_with_status):
        """This method will be used to take server OOS from pool level."""
        try:
            status = {}
            logger.info(servers_with_status)
            serverlist = server if type(server) is list else [server]
            poollist = pool if type(pool) is list else [pool]
            for server in serverlist:
                port_details = [i.get('port') for i in servers_with_status if server == i.get('server')]
                port = port_details[0] if len(port_details) > 0 else '80'
                for pool in poollist:
                    try:
                        status[server] = self.take_pool_action(server, dc, pool, port, action="force_disable")
                    except Exception, e:
                        status[server] = False
                        logger.error(e)
            return status
        except Exception, e:
            logger.error(e)
        finally:
            return status

    def get_pool_is(self, server, dc, pool, servers_with_status):
        """This method will be used to take server IS from pool level."""
        try:
            status = {}
            serverlist = server if type(server) is list else [server]
            poollist = pool if type(pool) is list else [pool]
            port_details = [i.get('port') for i in servers_with_status if server == i.get('server')]
            port = port_details[0] if len(port_details) > 0 else '80'
            for server in serverlist:
                for pool in poollist:
                    try:
                        status[server] = self.take_pool_action(server, dc, pool, port, action="enable")
                    except Exception, e:
                        status[server] = False
                        logger.error(e)
            return status
        except Exception, e:
            logger.error(e)
        finally:
            return status

    def get_lb_logs(self, server):
        log_dict = {'action': '', 'user': ''}
        try:
            url = "http://{lbhost}/console/get_logs?member={server}&size=1".format(lbhost=Configs().getValue("lbhost"),server=server)
            response = requests.get(url)
            result = response.json()
            logs = result.get('logs')
            if len(logs) > 0:
                log_dict['action'] = logs[0][3]
                log_dict['user'] = logs[0][2]
                return log_dict
            else:
                return log_dict
        except Exception as e:
            logger.exception(e)
            log_dict['error'] = e
            return log_dict

    def get_healthcheck_detail(self, pool, dc):
        """ Return a dictionary """
        pool_api = "ltm/pool_info"
        uri = "http://%s/%s" %(self.lbhost, pool_api)
        payload = {
            "user" : self.lbuser,
            "data_center" : dc,
            "search_name" : pool,
            "wildcards" : 0,
            "use_cache" : 0,
        }
        try:
            lbretry = int(Configs().getValue("lbretry"))
            logger.debug("Parameters for fetching Pool information, URL - %s PAYLOAD - %s" %(uri, payload))
            while lbretry >= 0:
                try:
                    response = requests.post(uri, data=payload, timeout=self.lbtimeout)
                    if response.status_code != 200:
                        raise Exception("%s-%s" % (response.status_code, response.text))
                    break
                except Exception, e:
                    lbretry -= 1
                    time.sleep(self.lb_retry_delay)
                    if lbretry > 0:
                        logger.error("Unable to get pool information of pools - %s, dc - %s, Getting Error - %s, so retrying"
                                     % (pool, dc, e))
                    else:
                        raise Exception("Unable to get pool information of pools - %s, dc - %s, Getting Error - %s"
                                        % (pool, dc, e))
            if response.status_code == 200:
                data = response.json()
                logger.debug("Response Received - %s" % data)
                if not data.get('error_code', 0) == 200:
                    raise Exception("Unable to get healthcheck for pool - %s, dc - %s" %(pool, dc))
                return data
            else:
                message = "status_code - %s, Error - %s" %(response.status_code, response.text)
                raise Exception(message)
        except Exception, e:
            message = "Unable to get pool information of pools - %s, dc - %s, Getting Error - %s" %(pool, dc, e)
            logger.error(message)
            raise Exception(message)

    def check_http_healthcheck(self, servers, servers_with_status, pool, dc, health_check_string=["http"]):
        healthcheck_detail = {}
        template_detail = {}
        serverlist = servers if type(servers) is list else [servers]
        try:
            if health_check_string is None or len(health_check_string) == 0:
                raise Exception("template specified - %s for pool - %s, datacenter - %s"
                                % (health_check_string, pool, dc))
            response = self.get_healthcheck_detail(pool, dc)
            for template in response.get('monitor_template'):
                temp = [template for i in health_check_string if i in template]
                if len(temp) > 0:
                    template = temp[0]
                    template_detail['template'] = template
                    template_detail['monitor_template'] = template
                    template_index = response.get('monitor_template').index(template)
                    template_detail['monitor_send'] = response.get('monitor_send')[template_index]
                    template_detail['monitor_recv'] = response.get('monitor_recv')[template_index]
                    break
            logger.info("Template Configuraion is - %s" % template_detail)
            if len(template_detail) < 3:
                raise Exception("%s template details not found for pool - %s, datacenter - %s, Response - %s" %(health_check_string, pool, dc, response))

            template = template_detail.get('template')
            method = template_detail.get('monitor_send').split()[0]
            template_uri = template_detail.get('monitor_send').split()[1]
            template_uri = template_uri.replace("\\\\r\\\\n", "").replace("\\r\\n", "").replace("\r\n", "")

            receieve_string = template_detail.get('monitor_recv')
            logger.debug("recieved pool_servers_with_status %s" % (servers_with_status))
            for server in serverlist:
                try:
                    port_details = [i.get('port') for i in servers_with_status if server == i.get('server')]
                    port = port_details[0] if len(port_details) > 0 else '80'
                    uri = "http://%s:%s%s" %(server, port, template_uri.strip())
                    if method.strip().lower() == 'get':
                        resp = requests.get(uri)
                        if not resp.status_code == 200:
                            raise Exception("Unable to verify the server - %s , URI - %s , Status Code - %s , Exception - %s" %(server, uri, resp.status_code, resp.text))
                        if receieve_string in resp.text:
                            healthcheck_detail[server] = True
                        else:
                            raise Exception("string - %s is not in response - %s for request - %s" %(receieve_string, resp.text, uri))
                    elif method.strip().lower() == 'post':
                        tmpdata = ' '.join(template_detail.get('monitor_send').split()[2:])
                        tmpdata.replace("\\\\r\\\\n", "\\r\\n")
                        tmpdata = tmpdata.split('\\r\\n')
                        tmpdata = [ element for element in tmpdata if len(str(element).strip()) > 0 ]
                        body = tmpdata[-1].strip().replace("\\", "") if len(tmpdata) > 0 else None
                        headers = {}
                        defined_headers = Configs().getValue('post_healthcheck_headers')
                        for element in tmpdata:
                            data = element.replace("\\", "")
                            try:
                                key, value = tuple(data.split(':'))
                                if key.lower() in defined_headers:
                                    headers[key] = value
                            except Exception, e:
                                logger.error(e)
                        logger.info("Requesting POST Healthcheck for string - %s, for request - %s, headers - %s, body - %s"
                                    % (receieve_string, uri, headers, body))
                        response = requests.post(uri, headers=headers, data=body)

                        if not response.status_code == 200:
                            raise Exception("Unable to verify the server - %s , URI - %s , Status Code - %s , Exception - %s" %(server, uri, resp.status_code, resp.text))
                        if receieve_string in response.text:
                            healthcheck_detail[server] = True
                        else:
                            raise Exception("string - %s is not in response - %s for request - %s, headers - %s, body - %s"
                                            % (receieve_string, response.text, uri, headers, body))
                    else:
                        raise Exception("method - %s not supported for getting Health Check" %(method))
                except Exception, e:
                    healthcheck_detail[server] = False
                    logger.error(e)
                    logger.exception(e)
        except Exception, e:
            logger.error(e)
        finally:
            return healthcheck_detail, template_detail.get('monitor_send'), template_detail.get('monitor_recv')
