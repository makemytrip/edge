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
from jira import JIRA
from space.utils.db_handler import DBHandler

logger = logging.getLogger(__name__)


class Jira(object):
    """This class will be used to connect to JIRA"""
    def __init__(self, jira_id):
        dbobj = DBHandler()
        host = dbobj.getValue("jira_uri")
        user = dbobj.getValue("jira_user")
        password = dbobj.getValue("jira_password")
        self.jira_obj = JIRA(server=host, basic_auth=(user, password))
        self.jira_id = jira_id

    def comment(self, message=None, jira_id=None):
        try:
            if message is not None:
                jira_id = self.jira_id if jira_id is None else jira_id
                self.jira_obj.add_comment(jira_id, message)
        except Exception, e:
            logger.error(e)

    def _get_available_transitions(self, jira_id=None):
        if jira_id is None:
            return [t['name'] for t in self.jira_obj.transitions(self.jira_id)]
        else:
            return [t['name'] for t in self.jira_obj.transitions(jira_id)]

    def update_transition(self, transition=None, jira_id=None):
        try:
            jira_id = self.jira_id if jira_id is None else jira_id
            available_transitions = self._get_available_transitions(jira_id)
            if transition in available_transitions:
                self.jira_obj.transition_issue(issue=jira_id, transition=transition)
            else:
                raise Exception("%s Transition is not available for Jira id - %s" %(transition, jira_id))
        except Exception, e:
            logger.error(e)
