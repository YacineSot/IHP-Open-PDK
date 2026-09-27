########################################################################
#
# Copyright 2023 IHP PDK Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
########################################################################
__version__ = '$Revision: #3 $'

from .mos_code import mos_base
from .guard_ring_code import GuardRingType
from typing import List

class pmosHV(mos_base):
    model_name = 'sg13_hv_pmos'
    model_type = 'pmosHV'
    
    default_ring = 'nwell'
    default_distance = '0.57u'
    allowed_guard_ring_types = [GuardRingType.NONE, GuardRingType.NWELL]
    
    typ = 'P'
    hv = True
