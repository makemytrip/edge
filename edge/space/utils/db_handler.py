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

"""This File will be used for accessing Models of Space App."""

import logging

from django.utils import timezone
from space.models import ActionInfo, ActionStatus, Configs, Project


logger = logging.getLogger(__name__)


class DBHandler:
    """This class will be used for accessing Models of Space App."""

    def __init__(self):
        """Initialization Method."""
        pass

    @staticmethod
    def getValue(key):
        """Return Value of a given key from Model Properties."""
        obj = Configs.objects.get(key=key)
        if obj.is_expression:
            return eval(obj.value)
        return obj.value

    def getActionInfoObj(self, id):
        return ActionInfo.objects.get(id=id)

    def setActionInfoState(self, id, state, reason=None):
        """Update ActionStatus for an ActionInfo."""
        try:
            status = ActionStatus.objects.get(name=state)
            ActionInfo.objects.filter(id=id).update(status=status)
        except Exception as e:
            logger.exception(e)

    def updateActionInfoTaskIds(self, task_obj, task_id):
        """Update Task ids in ActionInfo Task ids column."""
        try:
            current_task_id = task_obj.task_ids
            if current_task_id is None:
                current_task_id=""
            new_task_id = (str(current_task_id) + "," + str(task_id)).strip().strip(",")
            task_obj.task_ids = new_task_id
            task_obj.save()
        except Exception, e:
            logger.error(e)

    def getActionInfoActionName(self, id):
        return self.getActionInfoObj(id).action.name

    def updateActionInfoStartTime(self, id, task_time=None):
        try:
            task_time = timezone.now() if task_time is None else task_time
            action_obj = ActionInfo.objects.get(id=id)
            action_obj.task_start_time = task_time
            action_obj.save()
        except Exception as e:
            logger.exception(e)

    def updateActionInfoEndTime(self, id, task_time=None):
        try:
            task_time = timezone.now() if task_time is None else task_time
            action_obj = ActionInfo.objects.get(id=id)
            action_obj.task_end_time = task_time
            action_obj.save()
        except Exception as e:
            logger.exception(e)

    def getActionStatus(self):
        return ActionStatus().get_action_status()

    def getSpaceName(self, project_name):
        try:
            return Project.objects.get(name=project_name).space.name
        except Exception, e:
            logger.exception(e)

    def getSpaceDLs(self, project_name):
        try:
            return list(set(Project.objects.get(name=project_name).space.dls()))
        except Exception, e:
            logger.exception(e)
