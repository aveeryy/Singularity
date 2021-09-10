from .Singularity import Singularity
from singularity.update import selfupdate
from .version import __version__

update = selfupdate

_version = __version__