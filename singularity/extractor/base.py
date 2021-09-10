import json
from singularity.config import config, save_config, lang
from singularity.paths import ACCOUNTS
from singularity.types import * 
from singularity.utils import vprint, is_download_id
from getpass import getpass
from http.cookiejar import LWPCookieJar
from tqdm.std import tqdm

from colorama import Fore

import os
import sys

class BaseExtractor:
    
    def __init__(self, url=None, options=None, external=False):
        self.url = url
        self.extractor_name = self.return_class()[:-9]
        self.info = None
        if options is not None:
            self.options = {**self.DEFAULTS, **config['extractor'][self.extractor_name.lower()], **options}
        else:
            self.options = {**self.DEFAULTS, **config['extractor'][self.extractor_name.lower()]}
        self.external_tool = external
        if self.extractor_name.lower() in lang:
            self.extractor_lang = lang[self.extractor_name.lower()]

        if 'JSON_COOKIE_JAR' in self.FLAGS:
            self.cjar = []
            # Create a cookiejar for the extractor
            if not os.path.exists(ACCOUNTS + f'{self.extractor_name}.cjar'):
                with open(ACCOUNTS + f'{self.extractor_name}.cjar', 'w', encoding='utf-8') as c:
                    c.write('[]')
            with open(ACCOUNTS + f'{self.extractor_name}.cjar', 'r', encoding='utf-8') as c:
                self.cjar = json.load(c)
        else:
            # Create a cookiejar for the extractor
            if not os.path.exists(ACCOUNTS + f'{self.extractor_name}.cjar'):
                with open(ACCOUNTS + f'{self.extractor_name}.cjar', 'w', encoding='utf-8') as c:
                    c.write('#LWP-Cookies-2.0\n')
            # Open that cookiejar
            self.cjar = LWPCookieJar(ACCOUNTS + f'{self.extractor_name}.cjar')
            self.cjar.load(ignore_discard=True, ignore_expires=True)

        self.extraction = False
        self.search_results = []
        if hasattr(self, 'load_at_init'):
            self.load_at_init()
        # Login if there's an user-inputted username and password in the options
        if 'username' in self.options and 'password' in self.options:
            self.login(self.options['username'], self.options['password'])

    def set_main_info(self, media_type: str):
        if media_type == 'series':
            self.info = Series()

        elif media_type == 'movie':
            self.info = Movie()


    def create_progress_bar(self, *args, **kwargs):
        color = Fore.MAGENTA if sys.platform != 'win32' else ''
        self.progress_bar = tqdm(*args, **kwargs)
        self.progress_bar.desc = f'{color}[extraction]{Fore.RESET} {self.progress_bar.desc}'
        self.progress_bar.update(0)
        

    def login_with_form(self, user: str, password: str):
        if not user:
            user = input(lang['extractor']['base']['login_email_prompt'])
        else:
            user = user
        if not password:
            password = getpass(lang['extractor']['base']['login_password_prompt'])
        else:
            password = password
        self.login(user=user, password=password)


    def save_cookies_in_jar(self, cookies: list, filter_list=None):
        if 'JSON_COOKIE_JAR' in self.FLAGS:
            raise ExtractorCodingError
        for cookie in cookies:
            if cookie.name not in filter_list:
                continue
            self.cjar.set_cookie(cookie)
        self.cjar.save(ignore_discard=True, ignore_expires=True)

    def cookie_exists(self, cookie_name: str):
        return bool([c for c in self.cjar if c.name == cookie_name])

    def save_json_jar(self):
        with open(ACCOUNTS + f'{self.extractor_name}.cjar', 'w', encoding='utf-8') as c:
            json.dump(self.cjar, c)


    def create_season(self, independent=False, **metadata):
        'Metadata parameter is optional'
        if not independent and type(self.info) != Series:
            raise ExtractorCodingError
        self.season = Season()
        if not independent:
            # Link season to series
            self.info.link_season(season=self.season)
        if metadata:
            self.season.set_metadata(**metadata)

    def create_episode(self, independent=False, **metadata):
        if not independent and type(self.info) != Series:
            raise ExtractorCodingError('You can only create an episode with a series')
        if not independent and not hasattr(self, 'season'):
            raise ExtractorCodingError('You need to create a season before creating an episode!')
        self.episode = Episode()
        if not independent:
            self.season.link_episode(episode=self.episode)
        if metadata:
            self.episode.set_metadata(**metadata)
            
    def create_stream(self, independent=False, **metadata):
        self.stream = Stream()
        if not independent and type(self.info) == Series:
            self.episode.link_stream(stream=self.stream)
        elif not independent and type(self.info) == Movie:
            self.info.link_stream(stream=self.stream)
        elif not independent and self.info is None:
            self.episode.link_stream(stream=self.stream)
        self.stream.set_metadata(**metadata)

    def create_search_result(self, name: str, media_type: PolarType, low_id: str, url: str):
        self.search_result = SearchResult()
        self.search_result.name = name
        self.search_result.url = url
        self.search_result.type = media_type
        self.search_result.id = f'{self.extractor_name.lower()}/{media_type.__name__.lower()}-{low_id}'
        self.search_results.append(self.search_result)
        
class ExtractorError(Exception):
    pass

class InvalidURLError(Exception):
    pass

class LoginError(Exception):
    pass

class ContentUnavailableError(Exception):
    def __init__(self, msg='Content is unavailable in your region or has been taken out of the platform', *args, **kwargs):
        super().__init__(msg, *args, **kwargs)

class ExtractorCodingError(Exception):
    'This is only used on BaseExtractor, do not use!'
    pass