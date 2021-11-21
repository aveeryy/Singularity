from singularity.types.stream import Stream
from urllib import parse

from singularity.browser import get_driver, browser
from singularity.config import lang
from singularity.extractor.base import BaseExtractor, ExtractorError
from singularity.types import Series, Season, Episode
from singularity.utils import request_webpage, request_xml, vprint, request_json

import json
import re

from bs4 import BeautifulSoup as bs
from time import sleep
from urllib.parse import urlparse, urlunparse

class PrimeVideoExtractor(BaseExtractor):

    HOST = r'(?:http(?:s://|://|)|)(?:www.|)primevideo.com'

    DEFAULTS = {
        'all_seasons': False,
        'dolby_audio': True,
        }

    API_URL = None

    LOGIN_REQUIRED = True

    ARGUMENTS = [
    ]

    FLAGS = {
        'REQUIRES_LOGIN',
        'REQUIRES_BROWSER',
        'JSON_COOKIE_JAR',
        # 'DEBUG_DUMP'
    }
    
    AUDIO_REGEX = r'(?:/(?:dm|d)/)(?:2\$.+~)'

    ADVERT_REGEX = r'/\d@[0-9a-z]+/'
    
    @classmethod
    def return_class(self): return __class__.__name__
 
    def is_logged_in(self, ): return self.cookie_exists('session-token')

    def load_at_init(self):
        # Disable autoplay
        if self.url is not None:
            self.url = self.url.replace('autoplay=1', 'autoplay=0')
            parsed_url = urlparse(self.url)
            char = '?' if parsed_url.query == '' else '&'
            self.url += f'{char}episodeListSize=727'
        
        browser.start()
        
        self.driver = get_driver()

    def identify_url(self, url: str) -> str:
        url = url.replace('autoplay=1', 'autoplay=0')
        if not self.extraction:
            self.driver.get(url)
        url_gti = re.search(r'detail/(?P<comp_gti>\w+)/', url,).group('comp_gti')
        self.extract_jsons()

        seasons = [s for gti, s in self.season_info_json['props']['state']['self'].items() if s['compactGTI'] == url_gti]
        if seasons:
            return seasons[0]['titleType']

        episodes = [s for gti, s in self.episode_info_json['props']['state']['self'].items() if s['compactGTI'] == url_gti]
        if episodes:
            return episodes[0]['titleType']


    def login(self, username=str, password=str):
        
        # Login with local cookies
        if self.cjar:
            self.driver.get('https://primevideo.com')
            for c in self.cjar:
                self.driver.add_cookie(cookie_dict=c)
            self.driver.refresh()
            return

        self.driver.get('https://www.primevideo.com/auth-redirect')

        print('waiting for log in')

        while urlparse(self.driver.current_url).netloc not in ('www.primevideo.com', 'primevideo.com'):
            sleep(0.5)

        self.cjar = self.driver.get_cookies()
        self.save_json_jar()

    def get_series_info(self, title_id=None) -> Series:
        if not self.extraction and title_id is None:
            raise ExtractorError('no title id !')
        elif not self.extraction and title_id is not None:
            # TODO: support this shit
            pass
        self.extract_jsons()
        self.set_main_info('series')
        d = list(self.season_info_json['props']['state']['detail']['detail'].values())[0]
        self.info.title = d['parentTitle']
        self.info.synopsis = d['synopsis']
        self.info.year = d['releaseYear']

    def get_seasons(self, title_id=None) -> list: 
        if not self.extraction and title_id is None:
            raise ExtractorError('no title id !')
        elif not self.extraction and title_id is not None:
            # TODO: support this shit
            pass
        self.extract_jsons()
        seasons = []
        for gti, info in self.season_info_json['props']['state']['detail']['detail'].items():
            # id: GTI, title_id: compactGTI
            season = {
                'name': info['title'],
                'id': gti,
                'title_id': self.season_info_json['props']['state']['self'][gti]['compactGTI'],
                'number': info['seasonNumber'],
                'info': info
                }
            seasons.append(season)
        return seasons
             
    def parse_season_info(self, raw_info: dict, gti: str) -> Season:
        self.create_season(self.extraction is False)
        self.extract_jsons()
        self.season.title = raw_info['title']
        self.season.id = self.season_info_json['props']['state']['self'][gti]['compactGTI']
        self.season.synopsis = raw_info['synopsis']
        # self.season.year = raw_info['year']
        self.season.number = raw_info['seasonNumber']

        return self.season
    
    def get_episodes_from_season(self, title_id=None):
        # Get the season's page
        penis = []
        if title_id is not None:
            self.driver.get(f'https://primevideo.com/detail/{title_id}?episodeListSize=727')
        self.extract_jsons()
        for gti, info in self.episode_info_json['props']['state']['detail']['detail'].items():
            if gti not in self.episode_info_json['props']['state']['self']:
                break
            penis.append((gti, self.episode_info_json['props']['state']['self'][gti]['compactGTI'], info))
        return penis

    def parse_episode_info(self, raw_info: dict, gti: str, is_movie=False) -> Episode:
        if is_movie:
            self.set_main_info('movie')
            self.episode = self.info
            self.episode.id = self.season_info_json['props']['state']['self'][gti]['compactGTI']
            self.episode.year = raw_info['releaseYear']
        else:
            self.create_episode(self.extraction is False)
            self.episode.id = self.episode_info_json['props']['state']['self'][gti]['compactGTI']
            self.episode.number = raw_info['episodeNumber']
        self.episode.title = raw_info['title']
        
        vprint(lang['extractor']['get_media_info'] % (
            lang['types']['alt']['episode'],
            raw_info['title'],
            self.episode.id
        ), 3, 'primevideo')
        
        self.episode.synopsis = raw_info['synopsis']    
        
        self.driver.get(f'https://primevideo.com/detail/{self.episode.id}?autoplay=1')

        while True:
            requests = browser.get_network_requests()
            request = [r for r in requests if gti in r.url and 'PlaybackUrls' in r.url]
            if request:
                request = request[0]
                break
        
        # Recreate the request
        player_info = request_json(
            url=request.url,
            headers=request.headers,
        )[0]
        
        default_stream_id = player_info['playbackUrls']['defaultUrlSetId']
        
        stream_url = player_info['playbackUrls']['urlSets'][default_stream_id]['urls']['manifest']['url']
        
        # Get the stream with the good quality audio by removing a part of the stream's url
        # Don't know why it's like that
        # I literally had to use mitmproxy with AnyStream to figure this out lmao
        stream_url = re.sub(self.AUDIO_REGEX, '', stream_url)

        stream_url = re.sub(self.ADVERT_REGEX, '/', stream_url)
        
        vprint(f'Stream URL: {stream_url}', 3, 'primevideo', 'debug')
        
        keys_retries = 0

        sleep(5)

        while True:
            vprint(f'Attempting to get keys, attempt {keys_retries}', 3, 'primevideo', 'debug')
            try:
                keys = browser.get_widevine_keys()
                self.keys = self.filter_keys(stream_url, keys)
                break
            except (KeyError, IndexError):
                keys_retries += 1
                # Try to refresh the page in case an error happens
                if keys_retries == 7:
                    self.driver.refresh()
                if keys_retries >= 10:
                    vprint('Giving up on key extraction after 10 attempts, skipping...', 1, 'primevideo', 'error')
                    self.episode.skip_download = 'Failed to get Widevine key'
                    return self.episode
                sleep(keys_retries + 0.5)

        metadata_names = {}
        metadata_languages = {}
        if len(player_info['playbackUrls']['audioTracks']) > 1:
            for audio in player_info['playbackUrls']['audioTracks']:
                metadata_names[audio['audioTrackId']] = audio['displayName']
                metadata_languages[audio['audioTrackId']] = audio['languageCode'][:2]
        elif len(player_info['playbackUrls']['audioTracks']) == 1:
            audio = player_info['playbackUrls']['audioTracks'][0]
            metadata_names['audio'] = audio['displayName']
            metadata_languages['audio'] = audio['languageCode'][:2]
        
        stream = Stream(stream_url, 'main', True, metadata_names, metadata_languages, self.keys)
        
        self.episode.link_stream(stream=stream)
        
        for subt in player_info['subtitleUrls']:
            subt_stream = Stream(
                url=subt['url'],
                id=subt['timedTextTrackId'],
                preferred=True,
                name=subt['displayName'],
                language=subt['languageCode'][:2],
                key=None,
            )
            subt_stream.extra_sub = True
            self.episode.link_stream(subt_stream)

        del self.mpd_playlist

        return self.episode
    
    def filter_keys(self, manifest_url: str, keys: list):
        if not hasattr(self, 'mpd_playlist'):
            self.mpd_playlist = request_xml(
                url=manifest_url
            )[0]
            
        vprint('Attempting to match correct kid:key combination', 3, 'primevideo', 'debug')
        
        for adap_set in self.mpd_playlist['MPD']['Period']['AdaptationSet']:
            if adap_set['@contentType'] == 'video':
                video_key = [c['@cenc:default_KID'] for c in adap_set['ContentProtection'] if '@cenc:default_KID' in c][0]
                break
        for adap_set in self.mpd_playlist['MPD']['Period']['AdaptationSet']:
            if adap_set['@contentType'] == 'audio':
                audio_key = [c['@cenc:default_KID'] for c in adap_set['ContentProtection'] if '@cenc:default_KID' in c][0]
                break
        video_key = video_key.replace('-', '').lower()
        audio_key = audio_key.replace('-', '').lower()
        
        return {'video': [k for k in keys if video_key in k.raw_key][-1], 'audio': [k for k in keys if audio_key in k.raw_key][-1]}

    def extract_jsons(self):
        soup = bs(self.driver.page_source, features='html5lib')
        # Get all JSON information from page source
        unparsed_data = soup.find_all(type="text/template")
        json_data = [json.loads(a.string) for a in unparsed_data]
        self.season_info_json = json_data[len(json_data) - 3]
        self.episode_info_json = json_data[len(json_data) - 2]

    def extract(self):
        self.extraction = True
        self.login()
        self.driver.get(self.url)
        
        soup = bs(self.driver.page_source, features='html5lib')
        # Get all JSON information from page source
        unparsed_data = soup.find_all(type="text/template")

        if 'DEBUG_DUMP' in self.FLAGS:
            # Dump JSON information to file
            i = 0
            for _dat in unparsed_data:
                with open(f'amzn-dump_{i}.json', 'w', encoding='utf-8') as fp:
                    fp.write(_dat.string)
                i -=- 1
        
        url_type = self.identify_url(url=self.url)
        if url_type == 'season':
            
            self.set_main_info('series')
            self.get_series_info()
            seasons = self.get_seasons()
            if not self.options['all_seasons']:
                url_gti = re.search(r'detail/(?P<comp_gti>\w+)/', self.url,).group('comp_gti')
                season = [s for s in seasons if s['title_id'] == url_gti][0]
                self.parse_season_info(season['info'], season['id'])
                for gti, comp_gti, info in self.get_episodes_from_season():
                    self.parse_episode_info(raw_info=info, gti=gti)
            else:
                for season in seasons:
                    self.parse_season_info(season['info'], season['id'])
                    self.driver.get(f'https://primevideo.com/detail/{season["title_id"]}?episodeListSize=727')
                    for gti, comp_gti, info in self.get_episodes_from_season():
                        self.parse_episode_info(raw_info=info, gti=gti)

        elif url_type == 'episode':
            self.set_main_info('series')
            self.get_series_info()
            episodes = self.get_episodes_from_season()
            url_gti = re.search(r'detail/(?P<comp_gti>\w+)/', self.url,).group('comp_gti')
            episode = [e for e in episodes if url_gti == e[1]][0]
            seasons = self.get_seasons()
            season = [s for s in seasons if s['id'] == self.season_info_json['props']['state']['pageTitleId']][0]
            self.parse_season_info(season['info'], season['id'])
            self.parse_episode_info(episode[2], episode[0])

        elif url_type == 'movie':
            self.extract_jsons()
            movie = list(self.season_info_json['props']['state']['detail']['headerDetail'].items())[0]
            self.parse_episode_info(movie[1], movie[0], True)

        return self.info