import logging
import os
import sys
import traceback
import pretty_errors

from platform import system, version, python_version

from singularity.arguments import argument_parser
from singularity.config import lang
from singularity.Singularity import Singularity
from singularity.paths import LOGS
from singularity.utils import vprint, filename_datetime
from singularity.version import __version__


def main():
    urls, opts = argument_parser()
    # Launches Singularity
    Singularity(urls=urls, options=opts).start()

if __name__ == '__main__':
    if '--update-git' in sys.argv:
        from singularity.update import selfupdate
        selfupdate(mode='git')
    # Launch main function and handle 
    try:
        main()
    except KeyboardInterrupt:
        vprint(lang['main']['exit_msg'], 1)
        os._exit(0)
    except Exception:
        exception_filename = LOGS + f'exception_{filename_datetime()}.log'
        with open(exception_filename, 'w', encoding='utf-8') as log:
            log.write('Singularity version: %s\nOS: %s %s\nPython %s\n%s' %(
                __version__,
                system(),
                version(),
                python_version(),
                traceback.format_exc()
                )
            )
        # Re-raise exception
        raise