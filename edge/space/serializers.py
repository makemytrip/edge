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

from rest_framework import serializers
from space.models import ActionInfo, ActionStatus, Project, Space, Env, Dendrogram


class ActionSerializer(serializers.ModelSerializer):

    project = serializers.CharField(source='project.name', read_only=True)
    status = serializers.CharField(source='status.name', read_only=True)
    action = serializers.CharField(source='action.name', read_only=True)
    user = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ActionInfo
        fields = ('id', 'project', 'status', 'action', 'timestamp','servers', 'user')


class ProjectSerializer(serializers.ModelSerializer):
    env = serializers.CharField(source='env.name', read_only=True)
    space = serializers.CharField(source='space.name', read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        extra_kwargs = { 'name' : {'read_only':True}}


class SpaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Space
        fields = '__all__'


class EnvSerializer(serializers.ModelSerializer):
    class Meta:
        model = Env
        fields = '__all__'

class DendrogramSerializer(serializers.ModelSerializer):
    project = serializers.CharField(source='project.name', read_only=True)
    class Meta:
        model = Dendrogram
        fields = '__all__'
