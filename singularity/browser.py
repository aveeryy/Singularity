
from singularity.paths import BINARIES
from singularity.utils import vprint
from seleniumwire.undetected_chromedriver import Chrome, ChromeOptions
from seleniumwire.webdriver import DesiredCapabilities

import re

from time import sleep

from singularity.types.stream import ContentKey

WIDEVINE_REGEX = r'Found key: (?P<key>[a-z0-9]+) \(KID=(?P<kid>[a-z0-9]+)'

class Browser:

    def __init__(self) -> None:
        self.__started = False
        self.reserved_tabs = []
        self.widevine_keys = []
        self.widevine_kids = []

    def start(self):
        if not self.__started:
            # Set logging to ALL
            self.capabilities = DesiredCapabilities.CHROME
            self.capabilities['goog:loggingPrefs'] = {'browser': 'ALL', 'performance': 'ALL'}
            self.chrome_options = ChromeOptions()
            self.chrome_options.add_argument('--mute-audio')
            self.chrome_options.add_argument('--log-level=3')
            # Load widevine L3 decryptor extension
            self.chrome_options.add_extension(BINARIES + 'widevine.crx')

            self.driver = Chrome(desired_capabilities=self.capabilities, chrome_options=self.chrome_options)
            self.driver.implicitly_wait(30)
        self.__started = True

    def get_widevine_keys(self) -> list:
        vprint('Obtaining widevine keys', 3, 'browser', )
        for entry in self.driver.get_log('browser'):
            if entry['level'] != 'INFO':
                continue
            match = re.search(WIDEVINE_REGEX, entry['message'])
            if match is None:
                continue
            #elif match.group('kid') in self.widevine_kids:
            #    continue
            key = ContentKey(None, f"{match.group('kid')}:{match.group('key')}", 'Widevine')
            self.widevine_keys.append(key)
            self.widevine_kids.append(match.group('kid'))
        return self.widevine_keys

    def get_unreserved_tab(self) -> int:
        # TODO
        highest = -1
        for num in self.reserved_tabs:
            highest += 1
            if highest in self.reserved_tabs:
                continue
            break
        return highest

    def reserve_tab(self) -> int:
        # TODO
        # Save widevine keys
        self.get_widevine_keys()
        tabs_opened = len(self.driver.window_handles)
        tab = self.get_unreserved_tab()
        self.reserved_tabs.append(tab)
        return tab

    def release_tab(self, tab: int):
        del self.reserved_tabs[self.reserved_tabs.index(tab)]
        del tab

    def switch_to_tab(self, tab: int):
        self.get_widevine_keys()

    def get_network_requests(self) -> list:
        return self.driver.requests

browser = Browser()

def get_driver() -> Chrome:
    if hasattr(browser, 'driver'):
        return browser.driver