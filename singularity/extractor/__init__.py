
from .base import BaseExtractor
from .primevideo import PrimeVideoExtractor

EXTRACTORS =  {
    name.lower().replace('extractor', ''):
    (name.replace('Extractor', ''), klass, getattr(klass, 'HOST'))
    for (name, klass) in globals().items()
    if name.endswith('Extractor') and 'Base' not in name
}