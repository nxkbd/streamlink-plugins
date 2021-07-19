import json
import re

import requests

from urllib.parse import urljoin, urlparse, urlunparse
from streamlink.exceptions import PluginError, NoStreamsError
from streamlink.plugin.api import validate, useragents
from streamlink.plugin import Plugin
from streamlink.stream import HLSStream
from streamlink.utils import update_scheme


CONST_HEADERS = {}
CONST_HEADERS['User-Agent'] = useragents.CHROME
CONST_HEADERS['X-Requested-With'] = 'XMLHttpRequest'

url_re = re.compile(r"(http(s)?://)?(\w{2}.)?(bongacams\d*?\.com)/([\w\d_-]+)")

schema = validate.Schema({
    "status": "success"
})


class bongacams(Plugin):
    @classmethod
    def can_handle_url(self, url):
        return url_re.match(url)

    def _get_streams(self):
        match = url_re.match(self.url)

        LISTING_PATH = 'tools/listing_v3.php'

        stream_page_scheme = 'https'
        stream_page_domain = match.group(4)
        model_name = match.group(5)

        baseurl = urlunparse((stream_page_scheme, stream_page_domain, '', '', '', ''))
        listing_url = urlunparse((stream_page_scheme, stream_page_domain, LISTING_PATH, '', '', ''))

        # create http session and set headers
        http_session = self.session.http
        http_session.headers.update(CONST_HEADERS)

        # get cookies
        r = http_session.get(baseurl)
        if len(http_session.cookies) == 0:
            raise PluginError("Can't get a cookies")
        
        # is online?
        params = {
            "model_search[display_name][text]": model_name,
            "_count": 1
        }
        r = http_session.get(listing_url, params=params)
        if r.status_code != 200:
            self.logger.debug("response for {0}:\n{1}", r.request.url, r.text)
            raise PluginError("unexpected status code for {0}: {1}", r.url, r.status_code)
        if r.json()['online'] != 1:
            raise NoStreamsError(self.url)

        # get all online models
        listing_params = {
            "livetab": "female",
            "online_only": True,
            "offset": 0,
            "can_pin_models": True,
            "limit": 3000,
            "model_search[th_type]": "live",
            "model_search[sorting]": "camscore",
            "model_search[display]": "medium"
        }
        models_list = http_session.get(listing_url, params=listing_params)
        if models_list.status_code != 200:
            self.logger.debug("response for {0}:\n{1}", models_list.request.url, r.text)
            raise PluginError("unexpected status code for {0}: {1}", r.url, r.status_code)
        http_session.close()

        models_list = models_list.json()
        schema.validate(models_list)

        esid = None
        for model in models_list['models']:
            if model['username'] == model_name:
                if model['room'] != 'public':
                    raise NoStreamsError(self.url)
                esid = model['esid']

        if not esid:
            raise PluginError("unknown error, esid={0}", esid)

        hls_url = f'https://{esid}.bcvcdn.com/hls/stream_{model_name}/playlist.m3u8'

        if hls_url:
            self.logger.debug('HLS URL: {0}'.format(hls_url))
            try:
                for s in HLSStream.parse_variant_playlist(self.session, hls_url).items():
                    yield s
            except Exception as e:
                if '404' in str(e):
                    self.logger.error('Stream is currently offline or private')
                else:
                    self.logger.error(str(e))
                return


__plugin__ = bongacams
