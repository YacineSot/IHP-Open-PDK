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
from .via_stack2_code import via_stack
from .nmosHV_code import nmosHV
from .pmosHV_code import pmosHV
import pya
from pya import Region

# Import the PDK-agnostic MirrorBase
from .mirror_base import MirrorBase

class mirror_ihp(DeviceBase, MirrorBase):
    @classmethod
    def defineParamSpecs(cls, specs):
        techparams = specs.tech.getTechParams()

        CDFVersion = techparams['CDFVersion']
        defL       = techparams['nmos_defL']
        defW       = techparams['nmos_defW']
        defNG      = techparams['nmos_defNG']
        minL       = techparams['nmos_minL']
        minW       = techparams['nmos_minW']

        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())

        specs('w' , '5u', 'Width')
        specs('l' ,   '3u', 'Length')
        specs('model_type', 'nmos', 'Model Type', ChoiceConstraint(['nmos', 'pmos', 'nmosHV', 'pmosHV']))
        specs('horizontal_distance', '0.26u', 'Horizental distance')
        specs('vertical_distance', '0.3u', 'Vertical distance')
        specs('connection_metal_width', '0.5u', 'Connection metal width')
        specs('connection_metal_distance', '0.5u', 'Connection metal distance')
        specs('layout_pattern', 'AB BA', 'Layout Pattern')
        specs('gate_linked_to_source_devs', '', 'Devices which gate linked to source/drain')
        specs('connect_gate_to', 'drain', 'Connect gate to: ', ChoiceConstraint(['source', 'drain']))
        specs('connected_gate_devs', '', 'Devices which gates connected together')
        specs('connected_source_devs', '', 'Devices which sources connected together')
        specs('dummies_count', 2, 'Number of dummies')
        specs('dummies_offset', '0.2u', 'Distance between core and dummy')
        specs('dummies_distance', '0.2u', 'Distance between dummies')
        specs('place_taps', True, 'Place taps between devices', BooleanConstraint())
        super().defineParamSpecs(specs)
        specs('guard_ring_ref', 'active', 'Guard ring distance referance', ChoiceConstraint(['active', 'full']))

    def setupParams(self, params):
        self.w  = Numeric(params['w'])
        self.l  = Numeric(params['l'])
        self.ng = 1
        self.model_type = params['model_type']
        self.params = params
        self.grid_link = 'T-B'
        self.guard_ring_ref = params['guard_ring_ref']
        self.separation = ' '
        self.layout_pattern = self.fix_string(params['layout_pattern'], self.separation)
        self.gate_linked_to_source_devs = params['gate_linked_to_source_devs']
        self.connect_gate_to = params['connect_gate_to']
        self.connected_gate_devs = set(self.fix_string(params['connected_gate_devs']))
        self.connected_source_devs = set(self.fix_string(params['connected_source_devs']))
        self.horizontal_distance = Numeric(params['horizontal_distance'])*1e6
        self.vertical_distance = Numeric(params['vertical_distance'])*1e6
        self.bottom_top_distance = 0.2
        self.connection_metal_width = Numeric(params['connection_metal_width'])*1e6
        self.connection_metal_distance = Numeric(params['connection_metal_distance'])*1e6
        self.dummies_count = int(params['dummies_count'])
        self.dummies_offset = Numeric(params['dummies_offset'])*1e6
        self.dummies_distance = Numeric(params['dummies_distance'])*1e6
        self.place_taps = params['place_taps']

        super().setupParams(params)
        
        # Enforce minimums using tech params
        techparams = self.tech.getTechParams()
        min_metal1_distance = techparams['M1_a']
        self.min_metal1_distance = min_metal1_distance
        self.vertical_distance = max(self.vertical_distance, min_metal1_distance)
        self.horizontal_distance = max(self.horizontal_distance, min_metal1_distance)
        self.inner_vertical_distance = self.vertical_distance

    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        return [GuardRingType.AUTO]
        
    def _get_main_device(self):
        if self.model_type == 'nmos':
            return nmos
        elif self.model_type == 'pmos':
            return pmos
        elif self.model_type == 'nmosHV':
            return nmosHV
        else:
            return pmosHV

    def genMos(self, main_device, x_pos, y_pos, connection_metal='M2', is_dummy=False):
        device = main_device()
        guard_ring_type = 'nwell' if 'p' in self.model_type.lower() else 'psub'
        guard_ring_type = 'none' if x_pos != 0 and not is_dummy else guard_ring_type
        params = {'w': self.w, 
                    'l': self.l, 
                    'ng': 1, 
                    's_d_mlayer': connection_metal, 
                    'gate_connection': 'T-B',
                    'gate_metal': connection_metal, 
                    'cnt_w_ratio': 90,
                    'gate_cnt_ratio': 100,
                    'guardRingType' : guard_ring_type,
                    'guardRingDistance': '0.6u',
                    'north': False,
                    'south': False,
                    'west': True,
                    'east': True
                }
        device.tech = self.tech
        device._getCurrentCellContext = self._getCurrentCellContext
        device.sx = x_pos
        device.sy = y_pos
        device.setupParams(params)
        device.genDeviceLayout()
        return device

    # -------------------------------------------------------------------------
    # MirrorBase Abstract Method Implementations
    # -------------------------------------------------------------------------
    
    def get_device_dimensions(self):
        main_device = self._get_main_device()
        width, height = main_device.get_dimensions(self.w, self.l, self.ng, self.techparams)
        return (width, height, 0.0) # IHP draws sub-devices from origin 0
        
    def _box_to_list(self, box):
        # Convert cni.dlo Box to [left, bottom, right, top] in microns
        if not box: return None
        return [box.left, box.bottom, box.right, box.top]
        
    def place_device(self, char, x, y):
        main_device = self._get_main_device()
        device = self.genMos(main_device, x, y)
        dbCreateLabel(self, Layer('TEXT', 'drawing'), device.gate_box.getCenter(), f"Device {char}", 'centerCenter', 'R0', Font.EURO_STYLE, self.l*1e5)
        
        return {
            'source': self._box_to_list(device.source_box),
            'drain': self._box_to_list(device.drain_box),
            'gate_t': self._box_to_list(device.gate_box_t),
            'gate_b': self._box_to_list(device.gate_box_b)
        }
        
    def place_dummy(self, x, y):
        main_device = self._get_main_device()
        device = self.genMos(main_device, x, y, 'M1', is_dummy=True)
        dbCreateLabel(self, Layer('TEXT', 'drawing'), device.gate_box.getCenter(), f"Dummy", 'centerCenter', 'R0', Font.EURO_STYLE, self.l*1e5)
        return {
            'source': self._box_to_list(device.source_box),
            'drain': self._box_to_list(device.drain_box),
            'gate_t': self._box_to_list(device.gate_box_t),
            'gate_b': self._box_to_list(device.gate_box_b)
        }
        
    def draw_rect(self, layer_name, box, label = ""):
        layer_map = {
            'M1': Layer('Metal1', 'drawing'),
            'M2': Layer('Metal2', 'drawing'),
            'M3': Layer('Metal3', 'drawing'),
        }
        cni_box = Box(box[0], box[1], box[2], box[3])
        dbCreateRect(self, layer_map.get(layer_name, layer_map['M1']), cni_box)
        if label:
            self.draw_label(layer_name, label, box, "R0" if cni_box.getWidth() > cni_box.getHeight() else "R90")
        
    def draw_label(self, layer_name, text, box, rotation="R0"):
        layer_map = {
            'M1': Layer('Metal1', 'drawing'),
            'M2': Layer('Metal2', 'drawing'),
            'M3': Layer('Metal3', 'drawing'),
        }
        cni_box = Box(box[0], box[1], box[2], box[3])
        rot_str = 'R90' if rotation == "R90" else 'R0'
        # Size based on connection width (box width for V, height for H)
        size = min(cni_box.getWidth(), cni_box.getHeight()) / 2.0
        dbCreateLabel(self, layer_map.get(layer_name, layer_map['M1']), cni_box.getCenter(), text, 'centerCenter', rot_str, Font.EURO_STYLE, size)
        
    def draw_via(self, box, metal_b, metal_t, direction="V"):
        cni_box = Box(box[0], box[1], box[2], box[3])
        # Convert to tech units (microns) as IHP's genVia takes sizes
        width = cni_box.getWidth()
        height = cni_box.getHeight()
        center_x = cni_box.getCenter().x
        center_y = cni_box.getCenter().y
        
        metal_map = {'M1': 'Metal1', 'M2': 'Metal2', 'M3': 'Metal3'}
        mb = metal_map.get(metal_b, metal_b)
        mt = metal_map.get(metal_t, metal_t)
        
        self.genVia(width, height, center_x, center_y, mb, mt, True)
        
    def generate_tap(self, box):
        width = box[2] - box[0]
        height = box[3] - box[1]
        x_center = box[0] + width / 2.0
        y_center = box[1] + height / 2.0
        generate_guard_ring(self, self.guardRingType, 'e', width, height, x_center, y_center)
        
    def generate_outer_guard_ring(self, box):
        self.run_gen_guard_ring()


    # -------------------------------------------------------------------------
    # Entry Point
    # -------------------------------------------------------------------------
    def genLayout(self):
        w  = self.w
        ng = self.ng
        l  = self.l

        techparams      = self.tech.getTechParams()
        self.techparams = techparams
        self.epsilon    = techparams['epsilon1']

        dbReplaceProp(self, 'ivCellType', 'graphic')
        dbReplaceProp(self, 'viewSubType', 'maskLayoutParamCell')
        dbReplaceProp(self, 'instNamePrefix', 'M')
        dbReplaceProp(self, 'function', 'transistor')
        dbReplaceProp(self, 'pcellVersion', '$Revision: 1.0 $')
        dbReplaceProp(self, 'pin#', 5)

        self.w = GridFix(self.w / fix(ng+self.epsilon))
        self.l = GridFix(l)

        # Handle guard ring params internally for IHP logic
        self.guardRingType = 'psub' if 'n' in self.model_type else 'nwell'
        self.params['guardRingType'] = GuardRingType.NONE
        
        if self.guard_ring_ref == 'active':
            self.run_gen_guard_ring()

        # Call the core layout generation
        self.generate_mirror_layout()
