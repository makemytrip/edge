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

from __future__ import unicode_literals
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from django.utils import timezone

import logging, json, re

logger = logging.getLogger(__name__)


class Env(models.Model):
    name = models.CharField(unique=True, max_length=30)
    script_file_name = models.CharField(default=None, max_length=50)
    config = models.TextField(null=True, blank=True)
    history = HistoricalRecords()

    def __unicode__(self):
        return self.name

    def config_dict(self):
        return json.loads(self.config)


class Configs(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=300, unique=False)
    is_expression = models.BooleanField(default=False, blank=True)
    history = HistoricalRecords()

    def getValue(self, key):
        """Return Value of a given key from Model Properties."""
        obj = Configs.objects.get(key=key)
        if obj.is_expression:
            return eval(obj.value)
        return obj.value

    class Meta:
        verbose_name = "Application Properties"


class Space(models.Model):
    name =  models.CharField(unique=True, max_length=30)
    admin_dl = models.CharField(verbose_name="DL(s) for admin access to space", max_length=500, default=None)
    operator_dl = models.CharField(verbose_name="DL(s) for read access to space", max_length=500, default=None)
    nav_color = models.CharField(verbose_name="Theme color for space", max_length=20, blank=True)
    history = HistoricalRecords()

    def __unicode__(self):
        return self.name

    def dls(self):
        return list(set([self.admin_dl, self.operator_dl]))


class Project(models.Model):
    name = models.CharField(unique=True, max_length=110)
    space = models.ForeignKey(Space, verbose_name="associated space", default=None)
    env = models.ForeignKey(Env, verbose_name="Infra enviornment", default=None)
    config = models.TextField(null=True, blank=True)
    history = HistoricalRecords()

    def __unicode__(self):
        return self.name

    def config_dict(self):
        return json.loads(self.config)

    def total_config_dict(self):
        conf = self.env.config_dict()
        conf.update(self.config_dict())
        return conf

    def get_project_info(self, search_term, search_value, project_name):
        project_info = []
        for project in project_name:
            for name, value in project.items():
                custom_values = json.loads(value)
                if custom_values.get(search_term, None) == search_value:
                    project_name = custom_values.get("project_name", None)
                    project_info.append(project_name)
                else:
                    if search_term == 'fqdn':
                        split_val = search_value.split("-")
                        split_val = "-".join(split_val[:2])
                        term_value = custom_values.get(search_term, None)
                        if term_value is not None:
                            if term_value.startswith(split_val):
                                project_name = custom_values.get("project_name", None)
                                project_info.append(project_name)
        return project_info

    def get_projects(self,search_term=None,search_value=None):
        project_name = Project.objects.filter().values('config')
        final_project_name = []
        project_info = self.get_project_info(search_term, search_value, project_name)
        if project_info:
            final_project_name = Project.objects.filter(name__in=project_info)
        return final_project_name

class ProjectTale(models.Model):
    project = models.ForeignKey(Project)
    version = models.CharField(max_length=30, db_index=True)
    timestamp = models.DateTimeField(auto_now=True)


class ProjectConfigs(models.Model):
    project_id = models.ForeignKey(Project)
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=200)

    class Meta:
        unique_together = ("project_id", "key")


class Plan(models.Model):
    name = models.CharField(max_length=20, default=None)
    method_list = models.CharField(max_length=100, default=None)
    # order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('name',)

    def __unicode__(self):
        return self.name


class ActionStatus(models.Model):
    status_choices = (
        ('BUILDING', 'BUILDING'),
        ('SCHEDULED', 'SCHEDULED'),
        ('INPROGRESS', 'INPROGRESS'),
        ('FAILED', 'FAILED'),
        ('REVOKED', 'REVOKED'),
        ('COMPLETED', 'COMPLETED'),
        ('WAITING', 'WAITING'),
        ('MANUAL_FAILED', 'MANUAL_FAILED'),
    )

    name = models.CharField(choices=status_choices, max_length=20, unique=True)
    order = models.SmallIntegerField(default=-1)

    def get_action_status(self):
        return list(ActionStatus.objects.all().values_list('name', flat=True))

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ['order']


class ActionInfo(models.Model):
    project = models.ForeignKey(Project)
    action = models.ForeignKey(Plan)
    user = models.ForeignKey(User, default=None)
    servers = models.TextField(null=False, blank=False)
    config = models.TextField(null=False, blank=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.ForeignKey(ActionStatus)
    task_start_time = models.DateTimeField(default=None, null=True)
    task_end_time = models.DateTimeField(default=None, null=True)
    task_ids = models.CharField(default=None, null=True, blank=True, max_length=1000)
    script_file_name = models.CharField(default=None, max_length=50)
    history = HistoricalRecords()

    class Meta:
        unique_together = ("project", "timestamp")

    def server_list(self):
        return json.loads(self.servers)

    def config_dict(self):
        return json.loads(self.config)

    def __unicode__(self):
        return str(self.id)

    def update_status(self, status):
        status_obj = ActionStatus.objects.get(name=status)
        self.status = status_obj
        self.save()

    def update_start_time(self, start_time=None):
        task_time = timezone.now() if start_time is None else start_time
        self.task_end_time = task_time
        self.save()


class Dendrogram(models.Model):
    project = models.ForeignKey(Project)
    user = models.ForeignKey(User, default=None)
    server = models.CharField(max_length=30, db_index=True)
    version = models.CharField(max_length=300, db_index=True)

    def __unicode__(self):
        return str(self.id)

    class Meta:
        unique_together = ("project", "server")

    def get_project_name(self,server=None,version=None):
        if server is not None:
            project_list = Dendrogram.objects.filter(server=server)
        else:
            project_list = Dendrogram.objects.filter(version=version)
        return project_list

class ActionQueue(models.Model):
    space = models.ForeignKey(Space)
    project = models.ForeignKey(Project)
    servers = models.TextField(null=False, blank=False)
    action = models.ForeignKey(Plan)
    config = models.TextField(null=False, blank=False)
    user = models.ForeignKey(User, default=None)
    retries = models.IntegerField()

    def __unicode__(self):
        return str(self.id)

    class Meta:
        unique_together = ("project", "action")

    def server_list(self):
        return json.loads(self.servers)

@receiver(post_save, sender=Space)
def set_space_list(sender, instance, **kwargs):
    logger.info("---in set space lists method---")


@receiver(post_save, sender=ActionInfo)
def action_info_cleanup(sender, instance, **kwargs):
    logger.debug("action info cleanup for %s" % instance.project)

    project_deploy_action = ActionInfo.objects.filter(project=instance.project,action__name='deploy').values_list('id', flat=True)
    project_deploy_action = sorted(project_deploy_action, reverse=True)

    project_restart_action = ActionInfo.objects.filter(project=instance.project,action__name='restart').values_list('id', flat=True)
    project_restart_action = sorted(project_restart_action, reverse=True)

    del_project_action = project_deploy_action[15:] + project_restart_action[15:]

    logger.info(del_project_action)
    if del_project_action:
        logger.debug("entries for %s = %s" % (instance.project, len(del_project_action)))
        logger.info("delete %s for %s" % (del_project_action, instance.project))
        ActionInfo.objects.filter(id__in=del_project_action).delete()
