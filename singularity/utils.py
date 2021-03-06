from shutil import which
from sys import platform
from threading import Thread, current_thread
from urllib.parse import urljoin, urlparse
from time import sleep, time
import colorama
import requests
from requests.models import Response
from tqdm import tqdm
from json.decoder import JSONDecodeError
from xml.parsers.expat import ExpatError

import cloudscraper
import json
import logging
import os
import re
import subprocess
import toml
import unicodedata
import xmltodict

colorama.init()

def vprint(message, level=1, module_name='singularity', error_level=None, end='\n', use_print=False):
    '''
    ### Verbose print
    #### Prints a message based on verbose level

    ##### Example usage
    >>> from singularity.utils import vprint
    >>> vprint(
        message='Hello world!',
        level=1,
        module_name='demo',
        error_level='debug')
    [demo/debug] Hello world!  # Output
    >>>
    '''
    try:
        from singularity.config import verbose_level
    except ImportError:
        verbose_level = 1

    # Colors
    red = colorama.Fore.RED
    blu = colorama.Fore.CYAN
    yel = colorama.Fore.YELLOW
    gre = colorama.Fore.GREEN
    reset = colorama.Fore.RESET

    module = f'[{module_name}{f"/{error_level}" if error_level is not None else ""}]'
    
    print_method = tqdm.write if not use_print else print

    if error_level in ('error', 'critical', 'exception'):
        module = f'{red}{module}{reset}'
    elif error_level == 'warning':
        module = f'{yel}{module}{reset}'
    elif error_level == 'debug':
        module = f'{blu}{module}{reset}'
    else:
        module = f'{gre}{module}{reset}'
    
    msg = f'{module} {message}'

    if level <= int(verbose_level):
        # Print the message
        print_method(msg, end=end)

    if error_level is None and level <= 4:
        logging.info(f'[{module_name}] {message}')
    elif error_level is not None and level <= 4:
        getattr(logging, error_level)(f'[{module_name}] {message}')

def threaded_vprint(*args, lock, **kwargs):
    '''
    ### Threaded verbose print
    #### Same as verbose print, but avoids overlapping caused by threads
    ##### Example usage
    >>> from singularity.utils import threaded_vprint
    >>> from threading import Lock
    >>> my_lock = Lock()  # Create a global lock object
        # On a Thread
    >>> threaded_vprint(
        message=f'Hello world from {threading.current_thread.get_name()}!',
        level=1,
        module_name='demo',
        error_level='debug',
        lock=my_lock)
    # Output assuming three different threads
    [demo/debug] Hello world from Thread-0!
    [demo/debug] Hello world from Thread-1!
    [demo/debug] Hello world from Thread-2!
    '''
    
    with lock:
        vprint(*args, **kwargs)

# String manipulation stuff

def sanitize_path(filename=str, directory_replace=False):
    replace_win32 = {
        '|': '???',
        '<': '??',
        '>': '??',
        '"': "'",
        '?': '???',
        '*': '???',
        ':': ' ',
        '/': '',
        '\\': '',
    }
    # Windows forbidden characters
    for forbidden, shit_looking_character in replace_win32.items():
        if forbidden == '\\' and directory_replace or forbidden == '/' and directory_replace:
            continue
        filename = filename.replace(forbidden, shit_looking_character)    
    while True:
        if filename[-1] in ('.', ' '):
            filename = filename[:-1]
            continue
        break
    return filename

def sanitized_file_exists(file_path=str):

    file_dir = os.path.dirname(file_path) + '/'
    sanitized_path = sanitize_path(file_dir, directory_replace=True)
    sanitized_filename = sanitize_path(os.path.basename(file_path))
    sanitized = os.path.join(sanitized_path, sanitized_filename)
    if os.path.exists(file_path):
        return True
    if os.path.exists(sanitized):
        return True
    return False

# Adds a '0' behind any number. Example S1 -> S01
def normalize_integer(number):
    try:
        number = float(number)
    except ValueError:
        # Get numbers from string
        number = re.search(r'(\d)+', number)
        number = float(number.group(0))
    if number < 10:
        number = str('0') + str(number)
    else:
        number = str(number)
    if number.endswith('.0'):
        number = re.sub(r'\.\d+', '', number)
    return number

# Returns extension from url
def get_extension(url):
    return re.search(r'(?P<ext>\.\w+)($|[^/.\w\s,-])', url).group('ext')

def to_ascii(value, allow_unicode=True):
    # Taken from https://github.com/django/django/blob/master/django/utils/text.py
    # I literally had to dig throught an old repository to find this fucking function
    # Fuck you Windows and your shitty-ass filesystem
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else: 
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value)
    return re.sub(r'[-]+', '-', value).strip('-_')

def humanbytes(B):
   'Return the given bytes as a human friendly KB, MB, GB, or TB string\nhttps://stackoverflow.com/a/31631711'
   B = float(B)
   KB = float(1024)
   MB = float(KB ** 2) # 1,048,576
   GB = float(KB ** 3) # 1,073,741,824
   TB = float(KB ** 4) # 1,099,511,627,776

   if B < KB:
      return '{0} {1}'.format(B,'Bytes' if 0 == B > 1 else 'Byte')
   if KB <= B < MB:
      return '{0:.2f}KB'.format(B/KB)
   if MB <= B < GB:
      return '{0:.2f}MB'.format(B/MB)
   if GB <= B < TB:
      return '{0:.2f}GB'.format(B/GB)
   if TB <= B:
      return '{0:.2f}TB'.format(B/TB)

split_list = lambda lst, sz: [lst[i:i+sz] for i in range(0, len(lst), sz)]

def recurse_merge_dict(main_dict=dict, secondary_dict=dict):
    for key, val in main_dict.items():
        if isinstance(val, dict):
            secondary_node = secondary_dict.setdefault(key, {})
            recurse_merge_dict(val, secondary_node)
        else:
            if key not in secondary_dict:
                secondary_dict[key] = val
    return secondary_dict

def load_language(lang=None):
    'Returns dict containing selected language strings'
    from singularity.config import config
    from singularity.paths import LANGUAGES
    if lang is None:
        lang = config['language']
    base_language = toml.load(f'{LANGUAGES}enUS.toml')
    if os.path.exists(f'{LANGUAGES}{lang}.toml'):
        loaded_language = toml.load(f'{LANGUAGES}{lang}.toml')
        return recurse_merge_dict(base_language, loaded_language)
    else:
        # This string doesn't need to be translated \/
        # vprint('Specified language "%s" doesn\'t exist. Defaulting to english' % lang)
        return base_language
    
def language_installed(lang: str) -> bool:
    from singularity.paths import LANGUAGES
    return os.path.exists(f'{LANGUAGES}{lang}.toml')

def filename_datetime():
    from datetime import datetime
    return str(datetime.now()).replace(" ", "_").replace(":", ".")

def run_ffprobe(input, show_programs=True, extra_params=''):
    ffprobe_tries = 0
    vprint('getting stream information', 1, 'ffprobe')
    params = ['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams']
    if show_programs:
        params.append('-show_programs')
    # Extra parameters
    for e in re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', extra_params):
        e = e.replace('"', '')
        params.append(e)
    params.append(input)
    while True:
        try:
            _json = json.loads(subprocess.check_output(params))
            break
        except subprocess.CalledProcessError:
            vprint('ffprobe failed, retrying...', 1, 'ffprobe')
            ffprobe_tries += 1
            if ffprobe_tries > 3:
                raise
            continue
    return _json

'Download ID stuff'

class DownloadIdentifier:
    def __init__(self, extractor=str, content_type=str, id=str):
        self.extractor = extractor
        self.content_type = content_type
        self.id = id

download_id_regex = r'(?P<extractor>[\w]+)/(?P<type>[\w]+)-(?P<id>[\S]+)'

def is_download_id(text=str):
    '''
    #### Checks if inputted text is a download id
    >>> is_download_id('crunchyroll/series-000000')
        True
    >>> is_download_id('man')
        False
    '''
    return bool(re.match(download_id_regex, text))

def parse_download_id(id=str):
    '''
    #### Returns a `DownloadIdentifier` object with all attributes
    >>> from singularity.utils import parse_download_id
    >>> a = parse_download_id('crunchyroll/series-320430')
    >>> a.extractor
        'crunchyroll'
    >>> a.content_type
        'series'
    >>> a.id
        '320430'
    '''
    if not is_download_id(id):
        vprint('Failed to parse id', 1, 'utils/parse_download_id', 'error')
        return
    parsed_id = re.match(download_id_regex, id)
    return DownloadIdentifier(*parsed_id.groups())

def order_list(to_order, index=None, order_definer=list):
    if index is None:
        return [y for x in order_definer for y in to_order if x == y]
    else:
        return [y for x in order_definer for y in to_order if x == y[index]]
    
def order_dict(to_order, order_definer):
    return {y: z for x in order_definer for y, z in to_order.items()  if x == y}

def make_thread(*args, **kwargs):
    from singularity.Singularity import _ALL_THREADS
    thread = Thread(*args, **kwargs)
    _ALL_THREADS[thread.name] = {'obj': thread, 'running': False, }
    return thread

def calculate_time_left(processed=int, total=int, time_start=float):
    elapsed = time() - time_start
    try:
        return elapsed / processed * total - elapsed
    except ZeroDivisionError:
        return 0

def send_signal(self, thread=str, signal=str):
    '''
    ### Sends a signal to a Thread
        >>> from singularity.utils import send_signal, make_thread
        >>> from time import sleep
            ...
        # The target Thread must support handling the signals
        >>> a = make_thread(name='Example-0', ...)
        >>> a.start()
        >>> sleep(5)
        >>> send_signal('Example-0', 'PAUSE')
    '''
    from singularity.Singularity import _ALL_THREADS
    valid_signals = ['PAUSE', 'STOP', 'RESUME']
    if thread not in _ALL_THREADS:
        vprint('Failed to send signal, Thread does not exist', 5, 'penguin', 'error')
        return 1
    elif self.segment_downloaders[thread]['signal'] == signal:
        vprint('Signal is already sent!', 5, 'penguin', 'error')
        return 2
    elif signal not in valid_signals:
        vprint('Invalid signal', 5, 'penguin', 'error')
        return 3
    self.segment_downloaders[thread]['signal'] = signal
    vprint('Signal sent!', 3, 'penguin')
    return 0

def handle_signal():
    'Returns True on a stop signal, pauses on a pause signal'
    def clear_signal():
        _ALL_THREADS[thread_name]['signal'] = ''
    from singularity.Singularity import _ALL_THREADS
    thread_name = current_thread().name
    while _ALL_THREADS[thread_name]['signal'] == 'PAUSE':
        sleep(0.5)
    signal = _ALL_THREADS[thread_name]['signal']
    clear_signal()
    return signal == 'STOP'

def mkfile(path=str, contents=str, ):
    if not os.path.exists(path):
        open(path, 'w').write(contents)
        
def request_webpage(url=str, method='get', **kwargs) -> Response:
    '''
    Make a HTTP request using cloudscraper
    `url` url to make the request to
    `method` http request method
    `cloudscraper_kwargs` extra cloudscraper arguments, for more info check the `requests wiki`
    '''
    # Create a cloudscraper session
    # Spoof an Android Firefox browser to bypass Captcha v2
    browser = {
        'browser': 'firefox',
        'platform': 'android',
        'desktop': False,
    } 
    r = cloudscraper.create_scraper(browser=browser)
    response = getattr(r, method.lower())(url, **kwargs)
    return response



def request_json(url=str, method='get', **kwargs):
    'Same as request_webpage, except it returns a tuple with the json as a dict and the response object'
    response = request_webpage(url, method, **kwargs)
    try:
        return (json.loads(response.content.decode()), response)
    except JSONDecodeError:
        return ({}, response)



def request_xml(url=str, method='get', **kwargs):
    'Same as request_webpage, except it returns a tuple with the xml as a dict and the response object'
    response = request_webpage(url, method, **kwargs)
    try:
        return (xmltodict.parse(response.content.decode()), response)
    except ExpatError:
        return ({}, response)
    

def get_country_from_ip() -> str:
    return requests.get('http://ipinfo.io/json').json().get('country')
    
def get_compatible_extractor(url=str) -> tuple:
    'Returns a compatible extractor for the inputted url, if it exists'
    from singularity.extractor import EXTRACTORS
    if not is_download_id(text=url):
        url_host = urlparse(url).netloc
        extractor = [
            extractor
            for extractor in EXTRACTORS.values()
            if re.match(extractor[2], url_host)
            ]
        if not extractor:
            return(None, None)
        # Return (name, object)
        return (extractor[0][0], extractor[0][1])
    else:
        parsed_id = parse_download_id(id=url)
        extractor_name = parsed_id.extractor
        if not extractor_name in EXTRACTORS:
            return (None, None)
        return (EXTRACTORS[extractor_name][0], EXTRACTORS[extractor_name][1])

def format_language_code(code: str) -> str:
    '''
    Returns a correctly formatted language code
    
    Example:
    >>> format_language_code('EnuS')
    'enUS'
    '''
    lang = code[0:2]
    country = code[2:4]
    return f'{lang.lower()}{country.upper()}'