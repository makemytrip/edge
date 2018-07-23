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

from django.db import IntegrityError

from orchestration.utils.lb import LB
from space.models import ActionInfo, ActionQueue, Project

logger = logging.getLogger(__name__)


class DashUtils():

    @staticmethod
    def update_session(request, key, val):
        request.session[key] = val

    @staticmethod
    def get_server_object(project):
        """
            To get the server details.
            To add a new type of env. or logic please do add a new method
            by same name as server_info value in the env. config
        """
        try:
            server_object = []

            server_info = project.env.config_dict().get('server_info', {})
            server_object = getattr(DashUtils(), server_info)(project.total_config_dict().get(server_info, None))

        except Exception as e:
            logger.exception(e)
        finally:
            return server_object

    def aws_lb_info(self,aws_lb_info):
        try:
            d = []
            for key, val in aws_lb_info.items():
                for i in val:
                    servers = LB(use_cache=0).get_instances(lb_name=i.get('lb_name'),profile_name=i.get('profile_name'),lb_type=i.get('lb_type'))
                    logger.info("Recieved instances from aws - {ins}".format(ins=servers))
                    server_list = servers.get(i.get('lb_name'))
                    d.append({"pool": {"pool_name":i.get('lb_name')}, "servers":server_list})
            return d
        except Exception as e:
            logger.error(e)

    def pool_info(self, pool_info):

        pool_dict = []
        for dc, pools in pool_info.iteritems():
            for pool in pools:
                logger.info("%s, %s" % (pool, dc))
                servers = []
                try:
                    servers = LB(use_cache=1).get_memberlist(pool['pool_name'], dc)
                    logger.info(servers)
                except Exception as e:
                    logger.exception(e)
                finally:
                    pool_dict.append({'pool': pool, 'servers': servers})

        return pool_dict

    def server_list(self, server_list):
        d = []
        for zone, servers in server_list.iteritems():
            d.append({"pool": {"pool_name": zone}, "servers": servers})
        return d

    def nimbus_server_list(self, nimbus_server_list):
        d=[]
        for zone, servers in nimbus_server_list.iteritems():
            nimbus_servers = []
            for server_detail in servers:
                nimbus_servers.append(server_detail.get('server'))
            d.append({"pool" : {"pool_name" : zone}, "servers" : nimbus_servers})
        return d

    def check_active_servers(self, servers=[], space=None, project=None, action=None):
        active_status = ['BUILDING','SCHEDULED','INPROGRESS']
        active_action_list = ActionInfo.objects.filter(status__name__in=active_status)
        total_action_servers = []
        if action == "deploy":
            active_project_list = []
            for active_action in active_action_list:
                active_project_list.append(active_action.project.name)
            unique_project = list(set([project]).intersection(active_project_list))
            return unique_project
        else:
            for active_action in active_action_list:
                server_list = active_action.server_list()
                total_action_servers.extend(server_list)
            total_action_servers = set(total_action_servers)
            unique_servers = list(set(servers).intersection(total_action_servers))
            return unique_servers

    def get_active_tasks(self, project=None):
        active_status = ['BUILDING','SCHEDULED','INPROGRESS']
        active_action_list = ActionInfo.objects.filter(status__name__in=active_status, project__name=project).values_list('id', flat=True)
        return active_action_list

    def check_existing_queue_servers(self, project=None, space=None, action=None, servers=[]):
        serverlist = []
        queue_items = ActionQueue.objects.filter(project__name=project, space__name=space, action=action)
        for i in queue_items:
            active_servers = i.server_list()
            serverlist.extend(active_servers)
        serverlist = set(serverlist)
        servers = set(servers)
        total_servers = servers.intersection(serverlist)
        return total_servers

    def add_entry_to_action_queue(self, space=None, project=None, servers=[], action=None, user=None, retries=0, config={}):

        try:
            action_queue = ActionQueue(space=space, project=project, servers=json.dumps(servers), action=action, user=user, retries=retries, config=config)
            action_queue.save()
            return action_queue
        except IntegrityError as e:
            logger.exception(e)
            raise Exception("Entry already exists in queue !!")

    def get_fqdn_from_pool(self, pool_name=None, dc=None):
        project_list = []
        try:
            pool_name = pool_name.strip()
            if pool_name is not None:
                all_projects = Project.objects.all()
                for conf in all_projects:
                    config = json.loads(conf.config)
                    try:
                        pool_info = config.get('pool_info').get(dc)
                        for pool in pool_info:
                            if pool.get('pool_name') == pool_name:
                                project_list.append(conf.name)
                            else:
                                pass
                    except:
                        pool_info = None
                if len(project_list) > 0:
                    logger.info("Returning project list - %s found for pool - %s" % (project_list,pool_name))
                    projects = Project.objects.filter(name__in=project_list)
                    return projects
                else:
                    return []
        except Exception as e:
            logger.exception(e)
            return []

