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

"""This File will be used to handle with Django cache."""

import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


class EdgeCache(object):
    """This Class will be used to handle with Django Cache."""
    def __init__(self, correlation=None, datacenter=None):
        if correlation is None:
            raise Exception("Correlation key is required while creating edge cache.")
        if datacenter is None:
            self.key = correlation
        else:
            self.key = "%s-%s" %(correlation, datacenter)
        # Adding key in cache, if it doesn't exist
        cache.add(self.key, {})

    def set(self, key=None, **kwargs):
        if len(kwargs) == 0:
            raise Exception("Value is required while writing any key in cache.")
        if key is None:
            key = self.key
        data = cache.get(key, {})
        data.update(kwargs)
        cache.set(key, data)

    def get(self, key=None, param=None):
        if key is None:
            key = self.key
        data = cache.get(key)
        if param is not None:
            return data.get(param)
        return data

    def delete(self, key=None):
        if key is None:
            key = self.key
        cache.delete(key)

    def build(self, key=None):
        pass
