from .base import PolarType
from dataclasses import dataclass
from singularity.utils import get_extension

@dataclass
class ContentKey(PolarType):
    '''
    Available key methods:
    
    - `AES-128`
    - `Widevine` (Only on Singularity)
    '''
    url: str
    raw_key: str
    method: str

@dataclass
class Stream(PolarType):
    '''
    ### Stream guidelines:
    - Languages' names must be the actual name in that language
    
        >>> ...
        # Bad
        >>> self.name = 'Spanish'
        # Good
        >>> self.name = 'Español'
    - Languages' codes must be [ISO 639-2 codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
    - On extra_* streams 
    '''
    url: str
    id: str
    preferred: bool
    name: dict
    language: dict
    key: dict

    extra_audio = False
    extra_sub = False

@dataclass   
class Segment:
    url: str
    number: int
    media_type: type
    key: ContentKey
    group: str
    init: bool
    ext: str
    mpd_range: None
    _finished = False
        
@dataclass
class SegmentPool:
    segments: list
    format: str
    id: str
    track_id: str
    pool_type: str
    _finished = False
    _reserved = False
    _reserved_by = None
    
    def get_ext_from_segment(self, segment=0) -> str:
        if not self.segments:
            return
        return self.segments[segment].ext
    
    def get_init_segment(self) -> Segment:
        return [s for s in self.segments if s.init]
    
    
class M3U8Pool:
    ext = '.m3u8'
    
class DASHPool:
    ext = '.mp4'