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

from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from orchestration.utils.fabric_handler import FabricHandler

import logging, requests, json

logger = logging.getLogger(__name__)


class RPCView(APIView):
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        content = {
            'user': unicode(request.user),  # `django.contrib.auth.User` instance.
            'auth': unicode(request.auth),  # None
        }
        return Response(content)

    def post(self, request, format=None):

        command = None
        hosts = None
        output = None
        message = None
        try:
            request_payload = json.loads(request.body)
            command = request_payload.get('command', 'hostname')
            hosts = request_payload.get('hosts', [])
            with_sudo = request_payload.get('with_sudo', True)
            logger.info("executing command - %s, over hosts %s, by user %s" % (command, ",".join(hosts), request.user))
            output = FabricHandler(hosts=hosts, command=command, with_sudo=with_sudo).exec_remote_command()
            logger.info(json.dumps(output))
        except Exception as e:
            logger.exception(e)
            message = str(e)

        content = {
            'user': unicode(request.user),  # `django.contrib.auth.User` instance.
            'auth': unicode(request.auth),  # None
            'command': command,
            'hosts': hosts,
            'output': output,
            'message': message,
        }
        return Response(content)
