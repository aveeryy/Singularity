import os

HOME = os.path.expanduser('~')

# Set common directories
BASEDIR = HOME + '/.Singularity/'
ACCOUNTS = BASEDIR + 'Accounts/'
BINARIES = BASEDIR + 'Binaries/'
LANGUAGES = BASEDIR + 'Languages/' if not os.path.exists(HOME + '/.Polarity/Languages/') else HOME + '/.Polarity/Languages/'
LOGS = BASEDIR + 'Logs/'
# TEMP = BASEDIR + 'Temp/'
TEMP = r'Z:\TEMP\\'

# DOWNLOADS = HOME + '/Singularity Downloads/'
DOWNLOADS = r'Z:\DOWNLOADS\\'

# Set common file paths
CONFIGURATION_FILE = BASEDIR + 'Singularity.toml'
DOWNLOAD_LOG = BASEDIR + 'AlreadyDownloaded.log'
SYNC_LIST = BASEDIR + 'SyncList.json'

# Ability to use Polarity binaries path
ALT_BINARIES = HOME + '/.Polarity/Binaries/'


# Add the binaries directory to PATH
os.environ['PATH'] += ';' + BINARIES
os.environ['PATH'] += ';' + ALT_BINARIES