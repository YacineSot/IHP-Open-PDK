########################################################################
#
# Copyright 2024 IHP PDK Authors
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

__version__ = '$Revision: #0 $'

from cni.dlo import *
import cni.text
from .guard_ring_code import GuardRingType, generate_guard_ring
from .geometry import *
from .nmos_code import nmos
from .pmos_code import pmos
from .device_base_code import DeviceBase
from .via_stack_code import via_stack
from .nmosHV_code import nmosHV
from .pmosHV_code import pmosHV
from .t_gate_base import t_gate_base
from .ihp_base_definitions import ihp_base_definitions
import pya


class t_gate(DloGen, t_gate_base, ihp_base_definitions):
    @classmethod
    def defineParamSpecs(cls, specs):
        techparams = specs.tech.getTechParams()
        cls.techparams = techparams

        CDFVersion = techparams['CDFVersion']

        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())
        specs('w' , '5u', 'PMOS Width')
        specs('l' ,   '3u', 'PMOS Length')
        specs('inverter_w' , '5u', 'Inverter PMOS Width')
        specs('inverter_l' ,   '3u', 'Inverter PMOS Length')
        specs('ng', '1', 'Number of fingers')
        specs('pmos_gate_ratio', '0.6', 'PMOS to NMOS T-Gate Width ratio NMOS/PMOS')
        specs('pmos_inv_ratio', '0.6', 'PMOS to NMOS Inverter Width ratio NMOS/PMOS')
        specs('high_voltage', False, 'High Voltage devices ?', BooleanConstraint())
        specs('vertical_spacing', '1u', 'Vertical spacing')
        specs('horizontal_spacing', '0.5u', 'Horizontal spacing')
        specs('tap_spacing', '0.5u', 'Tap spacing')
        specs('tap_width', '0.3u', 'Tap Width')
        specs('connection_metal_width', '0.5u', 'Connection metal width')
        specs('self.inner_connection_width', '0.2u', 'Inner Connections M1 width')
        specs('connection_metal_spacing', '0.5u', 'Connection metal spacing')
        cls.additionnal_specs(cls, specs)
        
        

    def setupParams(self, params):
        # process parameter values entered by user
        self.w  = Numeric(params['w'])
        self.l  = Numeric(params['l'])
        self.inverter_w  = Numeric(params['inverter_w'])
        self.inverter_l  = Numeric(params['inverter_l'])
        self.ng = Numeric(params['ng'])
        self.pmos_gate_ratio = Numeric(params['pmos_gate_ratio'])
        self.pmos_inv_ratio = Numeric(params['pmos_inv_ratio'])
        self.vertical_spacing = Numeric(params['vertical_spacing'])*1e6
        self.horizontal_spacing = Numeric(params['horizontal_spacing'])*1e6
        self.connection_metal_width = Numeric(params['connection_metal_width'])*1e6
        self.connection_metal_spacing = Numeric(params['connection_metal_spacing'])*1e6
        self.inner_connection_width = Numeric(params['self.inner_connection_width'])*1e6
        self.tap_spacing = Numeric(params['tap_spacing'])*1e6
        self.tap_width = Numeric(params['tap_width'])*1e6
        self.Mn_min_distance = self.techparams['Mn_b']
        self.additionnal_params(params)
        self.set_devices('high_voltage' if params['high_voltage'] else 'low_voltage')
    
    def genLayout(self):
        self.gen_t_gate()
