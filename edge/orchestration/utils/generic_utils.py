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

from space.utils.db_handler import DBHandler

import re


def separate_servers_by_zone(serverlist):
    servers = {}
    zone_prefix = DBHandler().getValue("zone_ip_prefix")
    for zone in zone_prefix:
        if zone not in servers:
            servers[zone] = []
        match = re.compile(zone_prefix[zone])
        for server in serverlist:
            if re.match(match, server):
                servers[zone].append(server)
    return servers


def get_script_class_name(script_name):
    uppercase_keywords = ['dc','aws']
    keywords = [word.lower() for word in script_name.strip().split("_")]
    class_name = []
    for word in keywords:
        if word in uppercase_keywords:
            class_name.append(word.upper())
        else:
            class_name.append(word.title())
    return "".join(class_name)
