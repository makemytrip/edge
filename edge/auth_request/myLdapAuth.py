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

from django_auth_ldap.backend import LDAPBackend
from django.contrib.auth.models import Group, User

import ldap,re
from django.conf import settings

import logging

logger = logging.getLogger(__name__)


class LDAPBackend1(LDAPBackend):

    settings_prefix = "AUTH_LDAP_"

    def authenticate(self, username=None, password=None):
        response = super(LDAPBackend1, self).authenticate(username, password)
        try:
            group = Group.objects.get(name='admins')
            userObj = User.objects.get(username=username)
            userObj.groups.add(group)
        except Exception, e:
            logger.info("Unable to Add User - %s" % str(e))
        finally:
            return response


class LDAPBackend2(LDAPBackend):
    settings_prefix = "AUTH_LDAP_2_"


class AuthLdap():
    """  This Class is used to get details from LDAP.
    """
    def __init__(self):
        ldapClient = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
        ldapClient.set_option(ldap.OPT_REFERRALS, 0)
        ldapClient.bind_s(settings.AUTH_LDAP_BIND_DN, settings.AUTH_LDAP_BIND_PASSWORD)
        self.ldapClient = ldapClient

    def getusermember(self, user):
        memberlist = []
        try:
            baseDN = settings.LDAP_BASE_DN
            searchScope = ldap.SCOPE_SUBTREE
            searchFilter = '(sAMAccountName=%s)' %(user)
            rsid = self.ldapClient.search_st(baseDN, searchScope, searchFilter)
            if 'memberOf' in rsid[0][1]:
                for key in rsid[0][1]['memberOf']:
                    tempstr = key.split(',')[0]
                    lst = re.findall('CN=(.*)',tempstr)
                    if lst:
                        memberlist.append(lst[0].lower())
            logger.info("Member List for User - %s is %s" %(user, memberlist))
            return memberlist
        except Exception, e:
            logger.error("Getting Error while getting usermember list - %s" % e)
            logger.exception(e)
            return memberlist
