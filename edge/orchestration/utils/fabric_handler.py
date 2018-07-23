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

import logging

from django.conf import settings as app_settings
from fabric.api import env, settings, execute, sudo, parallel, hide, run

logger = logging.getLogger(__name__)


class FabricHandler():
    def __init__(self, hosts=[], command=None, with_sudo=True):
        self.hosts = hosts
        self.command = command
        self.white_list = app_settings.FABRIC_WHITE_LIST
        self.with_sudo = with_sudo

        if not hosts or not command:
            raise ValueError('hosts (as list) and command are mandatory')

        # fabric specific env settings, raise exception if env can't be created.
        if app_settings.FABRIC_USER_PASSWORD:
            env.password = app_settings.FABRIC_USER_PASSWORD
            env.use_ssh_config = True
            env.ssh_config_path = app_settings.FABRIC_SSH_CONFIG_PATH
            env.command_timeout = 600 # 10 mins
        else:
            raise ValueError('ssh user password should be set in env.')

    @parallel(pool_size=10)
    def __execute_parallel(self):

        command_output = {}
        try:
            if not self.command:
                raise ValueError("Command can not be None")

            with settings(warn_only=True):
                if self.with_sudo:
                    result = sudo(self.command)
                else:
                    result = run(self.command)
                command_output[result.command] = (result.return_code, result.succeeded, result.splitlines())

        except Exception as e:
            logger.exception(e)
        finally:
            logger.debug(command_output)
            return command_output

    def command_sanity(self):

        is_cmd_valid = False
        for i in self.white_list:
            if (self.command).startswith(i):
                is_cmd_valid = True
                break

        logger.debug('command %s verification %s' % (self.command, is_cmd_valid))

        return is_cmd_valid

    def exec_remote_command(self):
        with settings(hide('running', 'commands', 'stdout', 'stderr')):
            exec_output = None
            try:
                # verify command
                if self.with_sudo is False or self.command_sanity():
                    exec_output = execute(self.__execute_parallel, hosts=self.hosts)
                    return exec_output
                else:
                    raise ValueError('%s sanity failed' % self.command)
            except Exception as e:
                logger.exception(e)
                exec_output = e
                raise Exception(e)
