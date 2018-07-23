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

# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from space.models import Env, Space, Project, Configs, ActionStatus, Plan, ProjectConfigs, ActionInfo, Dendrogram, ActionQueue
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.


class SpaceAdmin(SimpleHistoryAdmin):
    list_display = ['name']
    search_fields = ['name']


class ProjectConfigsAdmin(admin.TabularInline):
    model = ProjectConfigs
    extra = 0


class ProjectAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'env']
    list_display = ['name']
    inlines = [ProjectConfigsAdmin]

    list_display = ['name', 'space', 'env']
    search_fields = ['name', 'space__name', 'env__name']

    def save_formset(self, request, form, formsets, change):
        super(ProjectAdmin, self).save_formset(request, form, formsets, change)
        print formsets, dir(formsets)
        custom_dict = {}
        if change:
            for row in formsets.queryset:
                custom_dict[row.key] = row.value
        else:
            instances = formsets.save(commit=False)
            for row in instances:
                custom_dict[row.key] = row.value
        form.instance.config = custom_dict
        form.instance.save()


class PlanAdmin(SimpleHistoryAdmin):
    list_display = ['name']


class ActionStatusAdmin(SimpleHistoryAdmin):
    list_display = ['name']


class ActionInfoAdmin(SimpleHistoryAdmin):
    list_display = ['project', 'action','status', 'timestamp', 'user']
    search_fields = ['project__name']


class ConfigsAdmin(SimpleHistoryAdmin):
    list_display = ('key', 'value', 'is_expression')
    search_fields = ['key', ]

class DendrogramAdmin(admin.ModelAdmin):
    list_display = ['project', 'server', 'version']
    search_fields = ['project__name', 'server', 'version']

class ActionQueueAdmin(admin.ModelAdmin):
    list_display = ['project', 'servers', 'retries', 'action']
    search_fields = ['project__name', 'space__name', 'action__name']

admin.site.register(Configs, ConfigsAdmin)
admin.site.register(Space, SpaceAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Env, SimpleHistoryAdmin)
admin.site.register(Plan, PlanAdmin)
admin.site.register(ActionStatus, ActionStatusAdmin)
admin.site.register(ActionInfo, ActionInfoAdmin)
admin.site.register(Dendrogram, DendrogramAdmin)
admin.site.register(ActionQueue, ActionQueueAdmin)
