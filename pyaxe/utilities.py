from __future__ import (absolute_import, unicode_literals, division,
                        print_function)

import os
from stsci.tools import fileutil  # replaces axe.findFile

# these are the C executables, verify they exist (from axeverify)
_execfiles = ['aXe_AF2PET', 'aXe_BE', 'aXe_GOL2AF', 'aXe_PET2SPC',
              'aXe_PETCONT', 'aXe_PETFF', 'aXe_STAMPS',
              'aXe_DRZPREP', 'aXe_DRZ2PET', 'aXe_GPS', 'aXe_FILET',
              'aXe_NICBACK', 'aXe_DIRIMAGE', 'aXe_SCALEBCK']

_bin_dir = os.environ("AXEBIN")
