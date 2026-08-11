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


class mirror(DeviceBase):
    @classmethod
    def defineParamSpecs(cls, specs):
        techparams = specs.tech.getTechParams()

        CDFVersion = techparams['CDFVersion']
        defL       = techparams['nmos_defL']
        defW       = techparams['nmos_defW']
        defNG      = techparams['nmos_defNG']
        minL       = techparams['nmos_minL']
        minW       = techparams['nmos_minW']

        cls.add_separation(cls, specs, 'Version readonly')
        
        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())

        cls.add_separation(cls, specs, 'Devices Sizing')
        specs('w' , '5u', 'Width')
        specs('l' ,   '3u', 'Length')
       
        cls.add_separation(cls, specs, 'Model Type')
        specs('model_type', 'nmos', 'Model Type', ChoiceConstraint(['nmos', 'pmos', 'nmosHV', 'pmosHV']))
        
        cls.add_separation(cls, specs, 'Internal connections & patterns settings')
        specs('horizontal_distance', '0.26u', 'Horizental distance')
        specs('vertical_distance', '0.3u', 'Vertical distance')
        specs('connection_metal_width', '0.5u', 'Connection metal width')
        specs('connection_metal_distance', '0.5u', 'Connection metal distance')
        specs('layout_pattern', 'AB BA', 'Layout Pattern')
        specs('gate_linked_to_source_devs', '', 'Devices which gate linked to source/drain')
        specs('connect_gate_to', 'drain', 'Connect gate to: ', ChoiceConstraint(['source', 'drain']))
        specs('connected_gate_devs', '', 'Devices which gates connected together')
        specs('connected_source_devs', '', 'Devices which sources connected together')
        
        cls.add_separation(cls, specs, 'Dummies settings')
        specs('dummies_count', 2, 'Number of dummies')
        specs('inner_dummies_count',0,'Number of dummies between devices')
        specs('dummy_l', '0.5u', 'Dummy length')
        specs('dummies_offset', '0.2u', 'Distance between core and dummy')
        specs('dummies_distance', '0.2u', 'Distance between dummies')
        specs('place_taps', False, 'Place taps between devices', BooleanConstraint())
        
        cls.default_ring = 'auto'
        super().defineParamSpecs(specs)

    def setupParams(self, params):
        # process parameter values entered by user
        self.w  = Numeric(params['w'])
        self.l  = Numeric(params['l'])
        self.ng = 1
        self.model_type = params['model_type']
        self.params = params
        # self.connect_gates = params['connect_gates']
        # self.connect_sources = params['connect_sources']
        # self.s_d_mlayer = params['s_d_mlayer']
        # self.grid_link = params['grid_link']
        self.grid_link = 'T-B'
        self.guard_ring_ref = 'full'
        self.separation = ' '
        # self.gate_metal = params['gate_mlayer']
        self.layout_pattern = self.fix_string(params['layout_pattern'], self.separation)
        self.gate_linked_to_source_devs = params['gate_linked_to_source_devs']
        self.connect_gate_to = params['connect_gate_to']
        self.connected_gate_devs = set(self.fix_string(params['connected_gate_devs']))
        self.connected_source_devs = set(self.fix_string(params['connected_source_devs']))
        self.horizontal_distance = Numeric(params['horizontal_distance'])*1e6
        self.vertical_distance = Numeric(params['vertical_distance'])*1e6
        self.bottom_top_distance = 0.2
        self.connection_width = Numeric(params['connection_metal_width'])*1e6
        self.connections_distance = Numeric(params['connection_metal_distance'])*1e6
        self.dummies_count = int(params['dummies_count'])
        self.inner_dummies_count = int(params['inner_dummies_count'])
        self.dummy_l = Numeric(params['dummy_l'])
        self.dummies_offset = Numeric(params['dummies_offset'])*1e6
        self.dummies_distance = Numeric(params['dummies_distance'])*1e6
        self.place_taps = params['place_taps']

        super().setupParams(params)

    @staticmethod
    def fix_string(str, separation = ""):
        return ''.join([char for char in str if char.isalpha() or char == separation])
    
    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return [GuardRingType.AUTO]

    def getMaxDeviceSize(device):
        min_left = INT_MAX
        min_bottom = INT_MAX
        max_right = INT_MIN
        max_top = INT_MIN
        for s in device.getShapes():
            if isinstance(s, cni.text.Text):
                continue

            bbox = s.bbox
            if isinstance(bbox, bool):
                # FIXME: in dpantenna/inductor2/inductor3 cells,
                #        strangely Polygon shapes
                #        had s.bbox being a boolean!
                #        skip those for now
                #
                # remove this as soon as this PR is merged:
                # https://github.com/IHP-GmbH/pycell4klayout-api/pull/3
                continue

            min_left = min(min_left, bbox.left)
            min_bottom = min(min_bottom, bbox.bottom)
            max_right = max(max_right, bbox.right)
            max_top = max(max_top, bbox.top)
        return (min_left, min_bottom, max_right, max_top)

    
    def genMos(self,main_device, x_pos, y_pos, connection_metal = 'M2', l=None):
        device = main_device()
        guard_ring_type = 'nwell' if 'p' in self.model_type.lower() else 'psub'
        guard_ring_type = 'none' if x_pos != 0 else guard_ring_type
        params = {'w': self.w, 
                    'l': self.l if not l else l, 
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
        if self.dummies_params['count'] > 0:
            params = params | {
                'dummies_count': self.dummies_params['count'],
                'dummies_l': self.dummies_params['l'],
                'dummy_core_spacing': self.dummies_params['core_spacing'],
                'dummies_inner_spacing': self.dummies_params['inner_spacing'],
                'dummies_left':self.dummies_params['left'],
                'dummies_right': self.dummies_params['right']
            }
        device.tech = self.tech
        device._getCurrentCellContext = self._getCurrentCellContext
        device.sx = x_pos
        device.sy = y_pos
        device.setupParams(params)
        device.genDeviceLayout()
        return device
    


    def genLayout(self):
        #self.genDeviceLayout()
        w  = self.w
        ng = self.ng
        l  = self.l

        techparams      = self.tech.getTechParams()
        self.techparams = techparams
        self.epsilon    = techparams['epsilon1']

        Cell = self.__class__.__name__

        #*************************************************************************
        #*
        #* Cell Properties
        #*
        #************************************************************************
        dbReplaceProp(self, 'ivCellType', 'graphic')
        dbReplaceProp(self, 'viewSubType', 'maskLayoutParamCell')
        dbReplaceProp(self, 'instNamePrefix', 'M')
        dbReplaceProp(self, 'function', 'transistor')
        dbReplaceProp(self, 'pcellVersion', '$Revision: 1.0 $')
        dbReplaceProp(self, 'pin#', 5)

        #*************************************************************************
        #*
        #* Layer Definitions
        #*
        #************************************************************************

        metal1_layer = Layer('Metal1', 'drawing')
        metal2_layer = Layer('Metal2', 'drawing')
        metal3_layer = Layer('Metal3', 'drawing')
        metal4_layer = Layer('Metal4', 'drawing')
        tgo_layer = Layer('ThickGateOx', 'drawing') # 44
        pdiffx_layer = Layer('pSD', 'drawing')      # 14
        metall_layer_pin = Layer('Metal1', 'pin')
        ndiff_layer = Layer('Activ')
        poly_layer = Layer('GatPoly')
        poly_layer_pin = Layer('GatPoly', 'pin')
        locint_layer = Layer('Cont')
        text_layer = Layer('TEXT', 'drawing')

        #*************************************************************************
        #*
        #* Generic Design Rule Definitions
        #*
        #************************************************************************
        epsilon = techparams['epsilon1']
        min_metal1_distance = techparams['M1_a']
        min_metal_width = techparams['Mn_a']
        min_metal_distance = techparams['Mn_b']
        endcap = techparams['M1_c1']
        cont_size = techparams['Cnt_a']
        cont_dist = techparams['Cnt_b']
        cont_Activ_overRec = techparams['Cnt_c']
        cont_metall_over = techparams['M1_c']
        gatpoly_Activ_over = techparams['Gat_c']
        gatpoly_cont_dist = techparams['Cnt_f']
        smallw_gatpoly_cont_dist = cont_Activ_overRec+techparams['Gat_d']
        contActMin = 2*cont_Activ_overRec+cont_size

        dbReplaceProp(self, 'pin#', 5)

        ng = fix(ng+epsilon)

        w = w/ng
        w = GridFix(w)
        l = GridFix(l)

        #*************************************************************************
        #*
        #* Main body of code
        #*
        #************************************************************************
        gard_ring_type = self.params['guardRingType']
        self.params['guardRingType'] = GuardRingType.NONE
        main_device = None
        if self.model_type == 'nmos' :
            main_device = nmos
        elif self.model_type == 'pmos':
            main_device = pmos
        elif self.model_type == 'nmosHV':
            main_device = nmosHV
        else:
            main_device = pmosHV
        
        l_com = self.l;
        # if self.model_type.__contains__('pmos'):
        #     self.w = self.w * 1e-6
        #     self.l = self.l * 1e-6
        self.dummies_params = {
            'count': self.inner_dummies_count,
            'left': True,
            'right': True,
            'l': self.dummy_l,
            'core_spacing': self.dummies_offset*1e-6,
            'inner_spacing': 0
        }
        (width, height) = main_device.get_dimensions(
                self.w*1e6, 
                self.l*1e6, 
                self.ng, 
                self.techparams,
                dummies_params=self.dummies_params
            )
        (dummy_width,  _) = main_device.get_dimensions(
            self.w*1e6,
            self.dummy_l*1e6,
            1,
            self.techparams
        )
        self.dummies_params['left'] = False
        (dummy_onside_width, _) = main_device.get_dimensions(
                    self.w*1e6, 
                    self.l*1e6, 
                    self.ng, 
                    self.techparams,
                    dummies_params=self.dummies_params
                )
        cells = self.layout_pattern.upper().split(self.separation)
        cells = cells[::-1] ## because we start drowing from the bottom to the top
        cells = [self.fix_string(cell) for cell in cells]
        different_devices = set(self.layout_pattern.replace(self.separation, ''))
        print(f"devices are: {different_devices}")
        different_devices_count = len(different_devices)
        contact_list = {}
        
        connections_list = {}
        for unique_dev in different_devices:
            connections_list[unique_dev] = {
                'drain_h': Region(),
                'drain_v': Region(),
                'source_h': Region(),
                'source_v': Region(),
                'gate_v': Region(),
                'gate_h': Region()
            }
        
        # Calculate widths for the gaps
        # Outer gaps (leftmost and rightmost, bottommost and topmost) only contain 'different_devices_count' lines (e.g. 2 lines)
        self.vertical_distance = max(self.vertical_distance, min_metal1_distance)
        self.horizontal_distance = max(self.horizontal_distance, min_metal1_distance)
        N_dev = different_devices_count
        outer_devs_l = set(cell[0] for cell in cells)
        outer_devs_r = set(cell[-1] for cell in cells)
        linked_gate_to_source_devs = different_devices & set(self.gate_linked_to_source_devs)
        common_source_devs = different_devices & self.connected_source_devs
        common_gate_devs = self.connected_gate_devs
        N_unique_gate_connection = N_dev if len(common_gate_devs) < 2 else N_dev - len(common_gate_devs) + 1
        N_unique_source_connection = N_dev if len(common_source_devs) < 2 else N_dev - len(common_source_devs) + 1
        N_linked_gate_to_source_devs = len(linked_gate_to_source_devs)
        N_unique_gate_connection -= N_linked_gate_to_source_devs
        N_outer_dev_l = len(outer_devs_l)
        N_outer_dev_r = len(outer_devs_r)
        x_outer_l = 2*self.horizontal_distance + N_outer_dev_l*self.connection_width + self.connections_distance * (N_outer_dev_l-1)
        x_outer_r = 2*self.horizontal_distance + N_outer_dev_r*self.connection_width + self.connections_distance * (N_outer_dev_r-1)
        #x_outer = x_outer if len(cells) > 1 else 0
        y_outer_b = 2*self.bottom_top_distance + (N_unique_source_connection + N_unique_gate_connection)*self.connection_width + self.connections_distance * (N_unique_source_connection + N_unique_gate_connection -1)
        y_outer_t = 2*self.bottom_top_distance + N_dev*self.connection_width + self.connections_distance * (N_dev-1)
        
        # Inner gaps (between devices) contain 2 * 'different_devices_count' lines (e.g. 4 lines: 2 for Drain, 2 for Source)
        num_inner = 2 * N_dev
        x_inner = 2*self.horizontal_distance + num_inner*self.connection_width + self.connections_distance * (num_inner-1)
        y_inner = 2*self.vertical_distance + num_inner*self.connection_width + self.connections_distance * (num_inner-1)
        y_inner = self.vertical_distance ## removing inner connections (useless)
        
        for i in range(len(cells[0])):
            for j,r in enumerate(cells):
                self.dummies_params['left'] = i > 0
                self.dummies_params['right'] = i < len(cells[0])-1
                device_char = r[i]
                position = {
                    # X position: Outer gap + width of all previous devices + inner gaps of all previous devices
                    "x": x_outer_l + i*(width + x_inner), 
                    # Y position: Outer gap + height of all previous devices + inner gaps of all previous devices
                    "y": (y_outer_b if 'B' in self.grid_link else 0) + j*height + j*y_inner
                    }
                device = self.genMos(main_device, position['x'] , position['y'])
                if device_char not in contact_list:
                    contact_list[device_char] = {
                        'drain': [],
                        'gate_t' : [],
                        'gate_b' : [],
                        'source': []
                    }
                contact_list[device_char]['drain'].append(device.drain_box)
                contact_list[device_char]['gate_t'].append(device.gate_box_t)
                contact_list[device_char]['gate_b'].append(device.gate_box_b)
                contact_list[device_char]['source'].append(device.source_box)
                dbCreateLabel(self, text_layer, device.gate_box.getCenter(), f"Device {device_char}", 'centerCenter', 'R0', Font.EURO_STYLE, self.l*1e5)
                
        #############################################
        #             Generate DUMMIES              #
        #############################################
        dummy_connection1 = {'top': None, 'bottom': None, 'left': None, 'right': None}     
        dummy_connection2 = {'top': None, 'bottom': None, 'left': None, 'right': None}
        self.dummies_params['count'] = 0
        for i in range(self.dummies_count):
            for j in range(len(cells)):
               position = {
                # X position: Outer gap + width of all previous devices + inner gaps of all previous devices
                "x": x_outer_l - self.dummies_offset - (i+1)*(dummy_width + self.dummies_distance ), 
                # Y position: Outer gap + height of all previous devices + inner gaps of all previous devices
                "y": (y_outer_b if 'B' in self.grid_link else 0) + j*height + j*y_inner}
               device = self.genMos(main_device, position['x'] , position['y'], 'M1', self.dummy_l)
               if j == 0 and i == 0:
                   dummy_connection1['bottom'] = device.gate_box_b.bottom
               if j == (len(cells)-1) and i == 0:   
                   dummy_connection1['top'] = device.gate_box_t.top
               if i == 0 and j == 0:
                   dummy_connection1['left'] = device.drain_box.right 
               if i == (self.dummies_count - 1) and (len(cells)-1):
                   dummy_connection1['right'] = device.source_box.left - self.guardRingDistance - self.guardRingWidth
               dbCreateLabel(self, text_layer, device.gate_box.getCenter(), f"Dummy", 'centerCenter', 'R0', Font.EURO_STYLE, self.l*1e5)
               position['x'] = x_outer_l + self.dummies_offset + (i)*(dummy_width + self.dummies_distance ) + (width + x_inner)*(len(cells[0])-1) - width + self.dummies_distance + 2*dummy_onside_width
               device = self.genMos(main_device, position['x'] , position['y'], 'M1', self.dummy_l)
               dbCreateLabel(self, text_layer, device.gate_box.getCenter(), f"Dummy", 'centerCenter', 'R0', Font.EURO_STYLE, self.l*1e5)
               if j == 0:
                   dummy_connection2['bottom'] = device.gate_box_b.bottom
               if j == (len(cells)-1):
                   dummy_connection2['top'] = device.gate_box_t.top
               if i == 0:
                   dummy_connection2['right'] = device.source_box.left
               if i == (self.dummies_count - 1):
                   dummy_connection2['left'] = device.drain_box.right + self.guardRingDistance + self.guardRingWidth
                 
        
        #############################################
        #           Generate Guard Ring             #
        #############################################
        #self.guardRingDistance = 0.3
        self.guardRingType = 'psub' if 'n' in self.model_type else 'nwell'
        if self.guard_ring_ref == 'active':
            self.run_gen_guard_ring()
        #############################################
        
             
        # Total array dimensions
        height_offset = self.vertical_distance - self.bottom_top_distance
        total_width = x_outer_l + (len(cells[0]) - 2)*width + 2*dummy_onside_width + (len(cells[0])-1)*x_inner + x_outer_r - self.horizontal_distance if len(cells[0]) > 0 else width
        total_height = y_outer_b + len(cells)*height + (len(cells)-2)*y_inner +  y_outer_t if len(cells) > 0 else height
        total_height = total_height + height_offset -0.32 + self.bottom_top_distance ## offset of the gat enc + via height
        
        self.gate_connection_horizontal_shift = 0
        
        if self.place_taps:
            self.gate_connection_horizontal_shift = 0.3
            if abs(self.horizontal_distance - self.gate_connection_horizontal_shift) < min_metal1_distance:
                self.gate_connection_horizontal_shift = 0
        ### Place Taps between devices
        for j in range(len(cells) -1):
            if not self.place_taps or self.gate_connection_horizontal_shift == 0: break;
            x_center = x_outer_l + width + x_inner/2 + 0.15 + ( (width + x_inner)*j + (width + x_inner)*(j-1) ) /2
            generate_guard_ring(self, self.guardRingType, 'e', width + x_inner, total_height, x_center , total_height/2)
        ###############################
        # -------------------------------------------------------------------------
        # Draw vertical buses (Metal3) in the horizontal spaces (gaps between columns)
        # -------------------------------------------------------------------------
        for i in range(len(cells[0]) + 1):
            if i == 0:
                # Gap 0 (Extreme Left): Only Source buses (N_dev lines)
                gap_start_x = 0
                k = 0
                for dev in different_devices:
                    if dev not in outer_devs_l:
                        continue
                    # Source lines
                    line_x = gap_start_x + self.horizontal_distance + k * (self.connection_width + self.connections_distance)
                    box = Box(line_x, y_inner - 0.48 - height_offset, line_x + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box)
                    dbCreateLabel(self, metal3_layer, box.getCenter(), f"source {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['source_v'].insert(box.box * (1/epsilon))
                    k += 1
                    
            elif i == len(cells[0]):
                # Gap N (Extreme Right): Only Drain buses (N_dev lines)
                gap_start_x = x_outer_l + (i-2)*width + (i-1)*x_inner + 2*dummy_onside_width
                k = 0
                for dev in different_devices:
                    if dev not in outer_devs_r:
                        continue
                    # Drain lines
                    line_x = gap_start_x + self.horizontal_distance + k * (self.connection_width + self.connections_distance)
                    box = Box(line_x, y_inner - 0.48 - height_offset, line_x + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box)
                    dbCreateLabel(self, metal3_layer, box.getCenter(), f"drain {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['drain_v'].insert(box.box * (1/epsilon))
                    k += 1
                    
            else:
                # Inner Gaps (Between devices): Drain buses for left device, THEN Source buses for right device (2 * N_dev lines)
                gap_start_x = x_outer_l + (i - 1)*width + (i-1)*x_inner + (dummy_onside_width)
                for k, dev in enumerate(different_devices):
                    # Drain lines (First half of the gap)
                    d_idx = k
                    line_x_d = gap_start_x + self.horizontal_distance + d_idx * (self.connection_width + self.connections_distance)
                    box_d = Box(line_x_d, y_inner - 0.48 - height_offset, line_x_d + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box_d)
                    dbCreateLabel(self, metal3_layer, box_d.getCenter(), f"drain {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['drain_v'].insert(box_d.box * (1/epsilon))
                    dbCreateRect(self, metal1_layer, box_d)
                    box_d.moveBy(-self.gate_connection_horizontal_shift,0)
                    dbCreateLabel(self, metal1_layer, box_d.getCenter(), f"gate {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['gate_v'].insert(box_d.box * (1/epsilon))
                    
                    # Source lines (Second half of the gap)
                    s_idx = k + N_dev
                    line_x_s = gap_start_x + self.horizontal_distance + s_idx * (self.connection_width + self.connections_distance)
                    box_s = Box(line_x_s, y_inner - 0.48 - height_offset, line_x_s + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box_s)
                    dbCreateLabel(self, metal3_layer, box_s.getCenter(), f"source {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['source_v'].insert(box_s.box * (1/epsilon))
                    dbCreateRect(self, metal1_layer, box_s)
                    box_s.moveBy(self.gate_connection_horizontal_shift,0)
                    dbCreateLabel(self, metal1_layer, box_s.getCenter(), f"gate {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['gate_v'].insert(box_s.box * (1/epsilon))

        # -------------------------------------------------------------------------
        # Draw horizontal buses (Metal2) in the vertical spaces (gaps between rows)
        # -------------------------------------------------------------------------
        for j in range(len(cells) + 1):
            if j == 0 and 'B' in self.grid_link:
                # Gap 0 (Extreme Bottom): Only Source buses (N_dev lines)
                gap_start_y = 0 - 0.48
                k = 0
                for dev in different_devices:
                    dev_name = dev
                    if dev in self.connected_source_devs:
                        dev_name = self.connected_source_devs
                        for tdev in self.connected_source_devs:
                            if tdev == dev: continue
                            if connections_list[tdev]['source_h'].count() > 0:
                                connections_list[dev]['source_h'] = connections_list[tdev]['source_h']
                                break;
                        if connections_list[dev]['source_h'].count() > 0: continue;
                    # Source lines
                    current_source = (N_unique_gate_connection) + k
                    line_y = gap_start_y + self.bottom_top_distance + current_source * (self.connection_width + self.connections_distance)
                    box = Box(self.horizontal_distance, line_y, total_width, line_y + self.connection_width)
                    dbCreateRect(self, metal2_layer, box)
                    dbCreateLabel(self, metal2_layer, box.getCenter(), f"source {dev_name}", 'centerCenter', 'R0', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['source_h'].insert(box.box * (1/epsilon))
                    k += 1
                k = 0
                for dev in different_devices:
                    dev_name = dev
                    if dev in self.connected_gate_devs:
                        dev_name = self.connected_gate_devs
                        for tdev in self.connected_gate_devs:
                            if tdev == dev: continue;
                            if connections_list[tdev]['gate_h'].count() > 0:
                                connections_list[dev]['gate_h'] = connections_list[tdev]['gate_h']
                                break;
                        if connections_list[dev]['gate_h'].count() > 0: continue;
                    if dev in linked_gate_to_source_devs:
                        continue
                    # Gate lines
                    line_y = gap_start_y + self.bottom_top_distance + k * (self.connection_width + self.connections_distance)
                    box = Box(self.horizontal_distance, line_y, total_width, line_y + self.connection_width)
                    dbCreateRect(self, metal2_layer, box)
                    dbCreateLabel(self, metal2_layer, box.getCenter(), f"gate {dev_name}", 'centerCenter', 'R0', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['gate_h'].insert(box.box * (1/epsilon))
                    k += 1
                    
            elif j == len(cells) and 'T' in self.grid_link:
                # Gap M (Extreme Top): Only Drain buses (N_dev lines)
                gap_start_y = j*height + (j-1)*y_inner - 0.32 + self.bottom_top_distance
                gap_start_y = gap_start_y + y_outer_b if 'B' in self.grid_link else gap_start_y
                for k, dev in enumerate(different_devices):
                    # Drain lines
                    line_y = gap_start_y + self.bottom_top_distance + k * (self.connection_width + self.connections_distance)
                    box = Box(self.horizontal_distance, line_y, total_width, line_y + self.connection_width)
                    dbCreateRect(self, metal2_layer, box)
                    dbCreateLabel(self, metal2_layer, box.getCenter(), f"drain {dev}", 'centerCenter', 'R0', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['drain_h'].insert(box.box * (1/epsilon))
                    
            else:
                continue; ## Skip inner connections 
                # Inner Gaps (Between devices): Drain buses for bottom device, THEN Source buses for top device (2 * N_dev lines)
                gap_start_y = y_outer_b + j*height + (j-1)*y_inner - 0.48
                for k, dev in enumerate(different_devices):
                    # Drain lines (First half of the gap)
                    d_idx = k
                    line_y_d = gap_start_y + self.vertical_distance + d_idx * (self.connection_width + self.connections_distance)
                    box_d = Box(0, line_y_d, total_width, line_y_d + self.connection_width)
                    dbCreateRect(self, metal2_layer, box_d)
                    dbCreateLabel(self, metal2_layer, box_d.getCenter(), f"drain {dev}", 'centerCenter', 'R0', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['drain_h'].insert(box_d.box * (1/epsilon))
                    
                    # Source lines (Second half of the gap)
                    s_idx = k + N_dev
                    line_y_s = gap_start_y + self.vertical_distance + s_idx * (self.connection_width + self.connections_distance)
                    box_s = Box(0, line_y_s, total_width, line_y_s + self.connection_width)
                    dbCreateRect(self, metal2_layer, box_s)
                    dbCreateLabel(self, metal2_layer, box_s.getCenter(), f"source {dev}", 'centerCenter', 'R0', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['source_h'].insert(box_s.box * (1/epsilon))
        
        def link_regions(vertical, horizontal, metal_b = 'Metal2', metal_t = 'Metal3'):
            drain_intersections = vertical & horizontal
            shapes = drain_intersections.decompose_trapezoids()
            #print(shapes.size())
            for shape in shapes:
                box = shape.bbox()
                mbox = Box()
                mbox.box = box
                #dbCreateRect(self, metal4_layer, mbox)
                self.genVia(mbox.getWidth()*epsilon, mbox.getHeight()*epsilon, mbox.getCenter().x*epsilon, mbox.getCenter().y*epsilon, metal_b, metal_t, True)
        
        def get_nearest_connection(contact, connections):
            return min(connections, key=lambda r: math.hypot(abs(r.bbox().center().x*epsilon - contact.getCenter().x)))
        
        def connect_terminal(terminal_contact, connections, metal_b = 'Metal2', metal_t = 'Metal3'):
            nearest = get_nearest_connection(terminal_contact, connections)
            nearest_box = Box(nearest.bbox().left * epsilon, terminal_contact.bottom, nearest.bbox().right * epsilon ,terminal_contact.top)
            self.genVia(nearest_box.getWidth(), nearest_box.getHeight(), nearest_box.getCenter().x, nearest_box.getCenter().y, metal_b, metal_t, True)
            connection_in_right = (nearest_box.getCenter().x - terminal_contact.getCenter().x) > 0
            left = terminal_contact.left if connection_in_right else nearest_box.left
            right = terminal_contact.right if not connection_in_right else nearest_box.right
            connect_box = Box(left, terminal_contact.bottom, right, terminal_contact.top)
            dbCreateRect(self, metal2_layer, connect_box)
        
        for dev in connections_list:
            current_connection = connections_list[dev];
            drain_v = current_connection['drain_v']
            drain_h = current_connection['drain_h']
            source_v = current_connection['source_v']
            source_h = current_connection['source_h']
            gate_v = current_connection['gate_v'] 
            gate_h = current_connection['gate_h'] 
            
            dev_drains = contact_list[dev]['drain']
            dev_sources = contact_list[dev]['source']
            dev_gates = contact_list[dev]['gate_t'] + contact_list[dev]['gate_b']
            
            link_regions(drain_v, drain_h)
            link_regions(source_v, source_h)
            link_regions(gate_v, gate_h, 'Metal1', 'Metal2')
            ## connect drains together
            for dr_contact in dev_drains:
                connect_terminal(dr_contact, drain_v)
            
            ## connect sources together
            for sc_contact in dev_sources:
                connect_terminal(sc_contact, source_v)
            
            for gt_contact in dev_gates:
                connect_terminal(gt_contact, gate_v, 'Metal1', 'Metal2')
            
            if dev in self.gate_linked_to_source_devs:
                for gt_contact in dev_gates:
                    vertical_connection = source_v if self.connect_gate_to == 'source' else drain_v
                    connect_terminal(gt_contact, vertical_connection)
        
        if self.guard_ring_ref == 'full':
            self.run_gen_guard_ring()
        if self.dummies_count > 0:  
            dummy_con_box = Box(dummy_connection1['left'], dummy_connection1['bottom'], dummy_connection1['right'], dummy_connection1['top'])
            dbCreateRect(self, metal1_layer, dummy_con_box)
            dummy_con_box = Box(dummy_connection2['left'], dummy_connection2['bottom'], dummy_connection2['right'], dummy_connection2['top'])
            dbCreateRect(self, metal1_layer, dummy_con_box)
