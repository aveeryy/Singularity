import cloudscraper

from requests.adapters import HTTPAdapter
from urllib.parse import urljoin
from urllib3.util.retry import Retry

from singularity.config import lang
from singularity.downloader.penguin.protocols.base import StreamProtocol
from singularity.types.stream import *
from singularity.utils import vprint, request_xml

class MPEGDASHStream(StreamProtocol):
    SUPPORTED_EXTENSIONS = ('.mpd')
    def open_playlist(self):
        
        def process_audio_repr(repr: dict):
            if adap_set['@audioTrackId'] not in audio_bitrate:
                audio_bitrate[adap_set['@audioTrackId']] = (None, 0)
            if int(repr['@bandwidth']) > int(audio_bitrate[adap_set['@audioTrackId']][1]):
                audio_bitrate[adap_set['@audioTrackId']] = (repr, int(repr['@bandwidth']))            
        
        self.manifest_data = request_xml(self.url)[0]
        self.processed_tracks = {
            'video': -1,
            'audio': -1,
            'unified': -1,
            'subtitles': -1
        }
        resolution_list = []
        audio_bitrate = {}
        
        for adap_set in self.manifest_data['MPD']['Period']['AdaptationSet']:
            if adap_set['@contentType'] == 'video':
                for repr in adap_set['Representation']:
                    resolution_list.append((repr, int(repr['@height'])))
                resolution = min(resolution_list, key=lambda x:abs(x[1]-self.options['resolution']))
                streams = [s for s in resolution_list if s[1] == resolution[1]]
                # Pick stream with higher bandwidth
                if len(streams) > 1:
                    print(':D')
                    bandwidth_values = [s[0]['@bandwidth'] for s in streams]
                    # stream = streams[bandwidth_values.index(max(bandwidth_values))][0]
                    stream = streams[-1][0]
                    vprint(stream['BaseURL'])
                    vprint(max(bandwidth_values))
                    vprint(bandwidth_values)
                else:
                    stream = self.streams[0][0]
                self.get_stream_fragments(stream, 'video', 'video')
            elif adap_set['@contentType'] == 'audio':
                if type(adap_set['Representation']) == list:
                    for repr in adap_set['Representation']:
                        process_audio_repr(repr)
                else:
                    process_audio_repr(adap_set['Representation'])
        
        for ident, repr in audio_bitrate.items():
            self.get_stream_fragments(repr[0], ident, 'audio')

    def get_stream_fragments(self, representation: dict, track_id: str, force_type=None):
        def build_segment_pool(media_type=str):
            self.processed_tracks[media_type] += 1
            seg_pool = SegmentPool([], media_type, f'{media_type}{self.processed_tracks[media_type]}', track_id, DASHPool)
            seg_pool.segments = [
                # Create a Segment object
                Segment(
                    url=self.stream_url,
                    number=list(representation['SegmentList']['SegmentURL']).index(s),
                    media_type=media_type,
                    key=None,
                    group=f'{media_type}{self.processed_tracks[media_type]}',
                    init=False,
                    ext=get_extension(self.stream_url),
                    mpd_range=s['@mediaRange']
                    )
                for s in representation['SegmentList']['SegmentURL']
                ]
            return seg_pool
        def create_init_segment(pool: str) -> None:
            self.segment_pool.segments.append(
                Segment(
                    url=self.stream_url,
                    number=-1,
                    init=True,
                    media_type=pool,
                    key=None,
                    group=f'{pool}{self.processed_tracks[pool]}',
                    ext=get_extension(self.stream_url),
                    mpd_range=representation['SegmentList']['Initialization']['@range']
                )                
            )
        self.stream_url = urljoin(self.url, representation['BaseURL'])
        vprint(lang['penguin']['protocols']['getting_stream'], 3, 'penguin/dash', 'debug')

        if force_type is not None:
            self.segment_pool = build_segment_pool(force_type)
            if 'Initialization' in representation['SegmentList']:
                create_init_segment(pool=force_type)
            self.segment_pools.append(self.segment_pool)
            return

    def extract(self):
        self.retries = Retry(total=30, backoff_factor=1, status_forcelist=[502, 503, 504, 403, 404])
        # Spoof a Firefox Android browser to (usually) bypass CaptchaV2
        self.browser = {
            'browser': 'firefox',
            'platform': 'android',
            'desktop': False,
        }
        vprint(lang['penguin']['protocols']['getting_playlist'], 3, module_name='penguin/dash', error_level='debug')
        self.open_playlist()
        return {'segment_pools': self.segment_pools, 'tracks': self.processed_tracks}