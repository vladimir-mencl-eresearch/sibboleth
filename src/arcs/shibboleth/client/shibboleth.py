##############################################################################
#
# Copyright (c) 2009 Victorian Partnership for Advanced Computing Ltd and
# Contributors.
# All Rights Reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import urllib2
from urllib2 import HTTPCookieProcessor, HTTPRedirectHandler
from urllib2 import HTTPBasicAuthHandler
from time import time
import logging
import re
from arcs.shibboleth.client.forms import FormParser, getFormAdapter


log = logging.getLogger('arcs.shibboleth.client')




class ShibbolethHandler(HTTPRedirectHandler, HTTPCookieProcessor):

    def __init__(self, cookiejar=None, **kwargs):
        HTTPCookieProcessor.__init__(self, cookiejar ,**kwargs)

    def http_error_302(self, req, fp, code, msg, headers):
        log.debug("GET %s" % req.get_full_url())
        result = HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
        result.status = code
        return result

    http_error_301 = http_error_303 = http_error_307 = http_error_302


class ShibbolethAuthHandler(HTTPBasicAuthHandler, ShibbolethHandler):

    def __init__(self, credentialmanager=None, cookiejar=None, **kwargs):
        HTTPBasicAuthHandler.__init__(self)
        ShibbolethHandler.__init__(self, cookiejar=cookiejar)
        self.credentialmanager = credentialmanager

    def http_error_401(self, req, fp, code, msg, headers):
        """Basic Auth handler"""
        url = req.get_full_url()
        authline = headers.getheader('www-authenticate')
        authobj = re.compile(
            r'''(?:\s*www-authenticate\s*:)?\s*(\w*)\s+realm=['"]([^'"]+)['"]''',
            re.IGNORECASE)
        matchobj = authobj.match(authline)
        realm = matchobj.group(2)
        self.credentialmanager.print_realm(realm)
        user = self.credentialmanager.get_username()
        self.credentialmanager.get_password()
        passwd = self.credentialmanager.get_password()
        self.add_password(realm=realm, uri=url, user=user, passwd=passwd)
        return self.http_error_auth_reqed('www-authenticate',
                                          url, req, headers)


def list_shibboleth_idps(sp):
    """
    return a list of idps protecting a service provider.

    :param sp: the URL of the service provider you want to connect to

    """
    opener = urllib2.build_opener(ShibbolethAuthHandler())
    request = urllib2.Request(sp)
    log.debug("GET: %s" % request.get_full_url())
    response = opener.open(request)
    parser = FormParser()
    for line in response:
        parser.feed(line)
    type, adapter = getFormAdapter(parser.title, parser.forms)
    if type == 'wayf':
        return adapter.data['origin']
    raise("Unknown error: Shibboleth auth chain lead to nowhere")


def open_shibprotected_url(idp, sp, cm, cj):
    """
    return a urllib response from the service once shibboleth authentication is complete.

    :param idp: the Identity Provider that will be selected at the WAYF
    :param sp: the URL of the service provider you want to connect to
    :param cm: a :class:`~slick.passmgr.CredentialManager` containing the URL to the service provider you want to connect to
    :param cj: the cookie jar that will be used to store the shibboleth cookies
    """
    cookiejar = cj
    opener = urllib2.build_opener(ShibbolethAuthHandler(credentialmanager=cm, cookiejar=cookiejar))
    request = urllib2.Request(sp)
    response = opener.open(request)

    slcsresp = None
    tries = 0
    while(not slcsresp):
        parser = FormParser()
        for line in response:
            parser.feed(line)
        parser.close()
        type, adapter = getFormAdapter(parser.title, parser.forms)

        if type == 'wayf':
            log.info('Submitting form to wayf')
            adapter.prompt()
            request, response = adapter.submit(opener, response, idp)
            continue
        if type.endswith('login'):
            if tries > 2:
                raise Exception("Too Many Failed Attempts to Authenticate")
            adapter.prompt()
            request, response = adapter.submit(opener, response, cm)
            tries += 1
            continue
        if type == 'idp':
            log.info('Submitting IdP SAML form')
            adapter.prompt()
            request, response = adapter.submit(opener, response)
            set_cookies_expiries(cj)
            return response
        raise("Unknown error: Shibboleth auth chain lead to nowhere")


def set_cookies_expiries(cookiejar):
    """
    Set the shibboleth session cookies to the default SP expiry, this way
    the cookies can be used by other applications.
    The cookes that are modified are ``_shibsession_`` and ``_shibstate_``

    :param cj: the cookie jar that stores the shibboleth cookies
    """
    for cookie in cookiejar:
        if cookie.name.startswith('_shibsession_'):
            if not cookie.expires:
                cookie.expires = int(time()) + 28800
                cookie.discard = False

from arcs.shibboleth.client.credentials import CredentialManager, Idp
from cookielib import CookieJar

try:
    from au.org.arcs.auth.shibboleth import ShibbolethClient as shib_interface
except:
    shib_interface = object


class Shibboleth(shib_interface):
    def __init__(self):
        self.cj = CookieJar()

    def shibopen(self, url, username, password, idp):

        def antiprint(*args):
            pass

        idp = Idp(idp)
        c = CredentialManager(username, password, antiprint)
        r = open_shibprotected_url(idp, url, c, self.cj)
        del c, idp
        return r

    def open(self, url):
        opener = urllib2.build_opener(ShibbolethHandler(cookiejar=self.cj))
        request = urllib2.Request(url)
        return opener.open(request)

