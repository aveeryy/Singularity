import cloudscraper

from m3u8 import parse
from requests.adapters import HTTPAdapter
from urllib.parse import urljoin
from urllib3.util.retry import Retry

from singularity.config import lang
from singularity.downloader.penguin.protocols.base import StreamProtocol
from singularity.types.stream import *
from singularity.utils import vprint

class HTTPLiveStream(StreamProtocol):
    SUPPORTED_EXTENSIONS = ('.m3u', '.m3u8')
    def open_playlist(self):
        self.manifest_data = self.scraper.get(self.url).content
        self.parsed_data = parse(self.manifest_data.decode())
        self.processed_tracks = {
            'video': -1,
            'audio': -1,
            'unified': -1,
            'subtitles': -1
        }
        if self.parsed_data['is_variant']:
            # Get preferred resolution stream
            vprint(lang['penguin']['protocols']['picking_best_stream_0'], 3, 'penguin/hls', 'debug')
            self.resolutions = [
                (s, int(s['stream_info']['resolution'].split('x')[1] if 'resolution' in s['stream_info'] else 0))
                for s in self.parsed_data['playlists']
                ]
            self.resolution = min(self.resolutions, key=lambda x:abs(x[1]-self.options['resolution']))
            self.streams = [s for s in self.resolutions if s[1] == self.resolution[1]]
            # Pick higher bitrate stream
            if len(self.streams) > 1:
                vprint(lang['penguin']['protocols']['picking_best_stream_1'], 3, 'penguin/hls', 'debug')
                self.bandwidth_values = [s[0]['stream_info']['bandwidth'] for s in self.streams]
                self.stream = self.streams[self.bandwidth_values.index(max(self.bandwidth_values))][0]
            else:
                self.stream = self.streams[0][0]
            vprint(lang['penguin']['protocols']['selected_stream'] % self.stream['BaseURL'], 3, 'penguin/dash', 'debug')
        else:
            self.stream = self.parsed
            

    def get_stream_fragments(self, stream=dict, force_type=None):
        def build_segment_pool(media_type=str):
            self.processed_tracks[media_type] += 1
            seg_pool = SegmentPool()
            seg_pool.segments = [
                # Create a Segment object
                Segment(
                    url=urljoin(self.stream_url, s['uri']),
                    number=self.parsed_stream['segments'].index(s),
                    media_type=media_type,
                    key=ContentKey(s['key']['uri'], None, s['key']['method']),
                    group=f'{media_type}{self.processed_tracks[media_type]}',
                    )
                for s in self.parsed_stream['segments']
                ]
            seg_pool.format = media_type
            seg_pool.type = M3U8Pool
            return seg_pool
        def create_init_segment(pool: str) -> None:
            self.segment_pool.segments.append(
                Segment(
                    url=urljoin(self.stream_url, self.parsed_stream['segment_map']['uri']),
                    init=True,
                    type=pool,
                    group=f'{pool}{self.processed_tracks[pool]}'
                )                
            )
        self.stream_url = urljoin(self.url, stream['uri'])
        vprint(lang['penguin']['protocols']['getting_stream'], 3, 'penguin/hls', 'debug')
        self.stream_data = self.scraper.get(self.stream_url).content
        self.parsed_stream = parse(self.stream_data.decode())
        # Support for legacy m3u8 playlists
        # (Not having video and audio in different streams)
        if force_type is not None:
            self.segment_pool = build_segment_pool(force_type)
            if 'segment_map' in self.parsed_stream:
                create_init_segment(pool=force_type)
            self.segment_pools.append(self.segment_pool)
            return

        if 'audio' not in stream['stream_info']:
            self.segment_pool = build_segment_pool('unified')
            if 'segment_map' in self.parsed_stream:
                create_init_segment(pool='unified')
        else:
            self.segment_pool = build_segment_pool('video')
        self.segment_pools.append(self.segment_pool)
        if 'segment_map' in self.parsed_stream:
            create_init_segment(pool='video')    
        for media in self.parsed_data['media']:
            if media['type'] == 'AUDIO':
                self.get_stream_fragments(media, 'audio')
            elif media['type'] == 'SUBTITLES':
                if '.m3u' in media['uri']:
                    self.get_stream_fragments(media, 'subtitles')
                else:
                    contents = self.scraper.get(urljoin(self.url, media['uri'])).content
                    # Fuck whoever thought it was a good idea to disguise m3u8 playlists as .vtt subtitles
                    if b'#EXTM3U' in contents:
                        self.get_stream_fragments(media, 'subtitles')
                        continue
                    self.processed_tracks['subtitles'] += 1
                    subtitles = Segment(
                        url=urljoin(self.url, media['uri']),
                        number=0,
                        type='subtitles',
                        group=f'subtitles{self.processed_tracks["subtitles"]}',
                    )
                    subtitle_pool = SegmentPool()
                    subtitle_pool.segments = [subtitles]
                    subtitle_pool.format = 'subtitles'
                    subtitle_pool.id = f'subtitles{self.processed_tracks["subtitles"]}'
                    
                    self.segment_pools.append(self.subtitle_set)    

    def extract(self):
        self.retries = Retry(total=30, backoff_factor=1, status_forcelist=[502, 503, 504, 403, 404])
        # Spoof a Firefox Android browser to (usually) bypass CaptchaV2
        self.browser = {
            'browser': 'firefox',
            'platform': 'android',
            'desktop': False,
        }
        vprint(lang['penguin']['protocols']['getting_playlist'], 3, module_name='penguin/hls', error_level='debug')
        self.scraper = cloudscraper.create_scraper(browser=self.browser)
        self.scraper.mount('https://', HTTPAdapter(max_retries=self.retries))
        self.open_playlist()
        self.get_stream_fragments(self.stream)
        return {'segment_pools': self.segment_pools, 'tracks': self.processed_tracks}
