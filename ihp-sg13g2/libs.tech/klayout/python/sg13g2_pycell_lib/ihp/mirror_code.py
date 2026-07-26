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
from .guard_ring_code import GuardRingType
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

        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())
        #specs('Display', 'Selected', 'Display', ChoiceConstraint(['All', 'Selected']))

        specs('w' , '5u', 'Width')
        #specs('ws',   eng_string(Numeric(defW)/Numeric(defNG)), 'SingleWidth')
        specs('l' ,   '3u', 'Length')
        # specs('connect_sources', 'Yes', 'Connect sources?', BooleanConstraint())
        # specs('connect_gates', 'Yes', 'Connect gates?', BooleanConstraint())
        # specs('s_d_mlayer', 'M2', 'S/D Metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        # specs('gate_mlayer', 'M2', 'Gate Metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        #specs('Wmin', minW, 'Wmin')
        #specs('Lmin', minL, 'Lmin')
        #specs('ng',   defNG, 'Number of Gates')

        #specs('m', '1', 'Multiplier')
        #specs('trise', '', 'Temp rise from ambient')
        specs('grid_link', 'T-B', 'Grid Links', ChoiceConstraint(['T-B','T', 'B']))
        specs('horizontal_distance', '0.26u', 'Horizental distance')
        specs('vertical_distance', '0.3u', 'Vertical distance')
        specs('connection_metal_width', '0.5u', 'Connection metal width')
        specs('connection_metal_distance', '0.5u', 'Connection metal distance')
        specs('layout_pattern', 'AB|BA', 'Layout Pattern')
        specs('model_type', 'nmos', 'Model Type', ChoiceConstraint(['nmos', 'pmos', 'nmosHV', 'pmosHV']))

        super().defineParamSpecs(specs)
        specs('guard_ring_ref', 'active', 'Guard ring distance referance', ChoiceConstraint(['active', 'full']))

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
        self.grid_link = params['grid_link']
        self.guard_ring_ref = params['guard_ring_ref']
        # self.gate_metal = params['gate_mlayer']
        self.layout_pattern = params['layout_pattern']
        self.horizontal_distance = Numeric(params['horizontal_distance'])*1e6
        self.vertical_distance = Numeric(params['vertical_distance'])*1e6
        self.connection_width = Numeric(params['connection_metal_width'])*1e6
        self.connections_distance = Numeric(params['connection_metal_distance'])*1e6

        super().setupParams(params)

    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return [GuardRingType.NONE]

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

    
    def genMos(self,main_device, x_pos, y_pos):
        device = main_device()
        guard_ring_type = 'nwell' if 'p' in self.model_type.lower() else 'psub'
        guard_ring_type = 'none' if x_pos != 0 else guard_ring_type
        params = {'w': self.w, 
                    'l': self.l, 
                    'ng': 1, 
                    's_d_mlayer': 'M3', 
                    'gate_connection': 'T-B',
                    'gate_metal': 'M1', 
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

        metall_layer = Layer('Metal1', 'drawing')
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
        (width, height) = main_device.get_dimensions(self.w, self.l, self.ng, self.techparams)
        self.layout_pattern = ''.join([char for char in self.layout_pattern if char.isalpha() or char == '|'])
        cells = self.layout_pattern.upper().split("|")
        cells = cells[::-1] ## because we start drowing from the bottom to the top
        different_devices = set(self.layout_pattern.replace('|', ''))
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
                'gate': Region()
            }
        
        # Calculate widths for the gaps
        # Outer gaps (leftmost and rightmost, bottommost and topmost) only contain 'different_devices_count' lines (e.g. 2 lines)
        N_dev = different_devices_count
        outer_devs_l = set(cell[0] for cell in cells)
        outer_devs_r = set(cell[-1] for cell in cells)
        N_outer_dev_l = len(outer_devs_l)
        N_outer_dev_r = len(outer_devs_r)
        x_outer_l = 2*self.horizontal_distance + N_outer_dev_l*self.connection_width + self.connections_distance * (N_outer_dev_l-1)
        x_outer_r = 2*self.horizontal_distance + N_outer_dev_r*self.connection_width + self.connections_distance * (N_outer_dev_r-1)
        #x_outer = x_outer if len(cells) > 1 else 0
        y_outer = 2*self.vertical_distance + N_dev*self.connection_width + self.connections_distance * (N_dev-1)
        
        # Inner gaps (between devices) contain 2 * 'different_devices_count' lines (e.g. 4 lines: 2 for Drain, 2 for Source)
        num_inner = 2 * N_dev
        x_inner = 2*self.horizontal_distance + num_inner*self.connection_width + self.connections_distance * (num_inner-1)
        y_inner = 2*self.vertical_distance + num_inner*self.connection_width + self.connections_distance * (num_inner-1)
        y_inner = self.vertical_distance ## removing inner connections (useless)
        
        for i in range(len(cells[0])):
            for j,r in enumerate(cells):
                device_char = r[i]
                position = {
                    # X position: Outer gap + width of all previous devices + inner gaps of all previous devices
                    "x": x_outer_l + i*width + i*x_inner, 
                    # Y position: Outer gap + height of all previous devices + inner gaps of all previous devices
                    "y": (y_outer if 'B' in self.grid_link else 0) + j*height + j*y_inner
                    }
                device = self.genMos(main_device, position['x'] , position['y'])
                if device_char not in contact_list:
                    contact_list[device_char] = {
                        'drain': [],
                        'gate' : [],
                        'source': []
                    }
                contact_list[device_char]['drain'].append(device.drain_box)
                contact_list[device_char]['gate'].append(device.gate_box)
                contact_list[device_char]['source'].append(device.source_box)
                dbCreateLabel(self, text_layer, device.gate_box.getCenter(), f"Device {device_char}", 'centerCenter', 'R0', Font.EURO_STYLE, self.l/10)
        
        #############################################
        #           Generate Guard Ring             #
        #############################################
        self.guardRingType = 'psub' if 'n' in self.model_type else 'nwell'
        if self.guard_ring_ref == 'active':
            self.run_gen_guard_ring()
        #############################################
        
             
        # Total array dimensions
        total_width = x_outer_l + len(cells[0])*width + (len(cells[0])-1)*x_inner + x_outer_r - self.horizontal_distance if len(cells[0]) > 0 else width
        total_height = len(cells)*height + (len(cells)-2)*y_inner if len(cells) > 0 else height
        total_height = total_height - 0.48 ## offset of the gat enc + via height
        total_height = total_height + y_outer if 'T' in self.grid_link else total_height
        total_height = total_height + y_outer if 'B' in self.grid_link else total_height
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
                    box = Box(line_x, y_inner - 0.48, line_x + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box)
                    dbCreateLabel(self, metal3_layer, box.getCenter(), f"source {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['source_v'].insert(box.box * (1/epsilon))
                    k += 1
                    
            elif i == len(cells[0]):
                # Gap N (Extreme Right): Only Drain buses (N_dev lines)
                gap_start_x = x_outer_l + i*width + (i-1)*x_inner
                k = 0
                for dev in different_devices:
                    if dev not in outer_devs_r:
                        continue
                    # Drain lines
                    line_x = gap_start_x + self.horizontal_distance + k * (self.connection_width + self.connections_distance)
                    box = Box(line_x, y_inner - 0.48, line_x + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box)
                    dbCreateLabel(self, metal3_layer, box.getCenter(), f"drain {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['drain_v'].insert(box.box * (1/epsilon))
                    k += 1
                    
            else:
                # Inner Gaps (Between devices): Drain buses for left device, THEN Source buses for right device (2 * N_dev lines)
                gap_start_x = x_outer_l + i*width + (i-1)*x_inner
                for k, dev in enumerate(different_devices):
                    # Drain lines (First half of the gap)
                    d_idx = k
                    line_x_d = gap_start_x + self.horizontal_distance + d_idx * (self.connection_width + self.connections_distance)
                    box_d = Box(line_x_d, y_inner - 0.48, line_x_d + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box_d)
                    dbCreateLabel(self, metal3_layer, box_d.getCenter(), f"drain {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['drain_v'].insert(box_d.box * (1/epsilon))
                    
                    # Source lines (Second half of the gap)
                    s_idx = k + N_dev
                    line_x_s = gap_start_x + self.horizontal_distance + s_idx * (self.connection_width + self.connections_distance)
                    box_s = Box(line_x_s, y_inner - 0.48, line_x_s + self.connection_width, total_height)
                    dbCreateRect(self, metal3_layer, box_s)
                    dbCreateLabel(self, metal3_layer, box_s.getCenter(), f"source {dev}", 'centerCenter', 'R90', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['source_v'].insert(box_s.box * (1/epsilon))

        # -------------------------------------------------------------------------
        # Draw horizontal buses (Metal2) in the vertical spaces (gaps between rows)
        # -------------------------------------------------------------------------
        for j in range(len(cells) + 1):
            if j == 0 and 'B' in self.grid_link:
                # Gap 0 (Extreme Bottom): Only Source buses (N_dev lines)
                gap_start_y = 0 - 0.48
                for k, dev in enumerate(different_devices):
                    # Source lines
                    line_y = gap_start_y + self.vertical_distance + k * (self.connection_width + self.connections_distance)
                    box = Box(self.horizontal_distance, line_y, total_width, line_y + self.connection_width)
                    dbCreateRect(self, metal2_layer, box)
                    dbCreateLabel(self, metal2_layer, box.getCenter(), f"source {dev}", 'centerCenter', 'R0', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['source_h'].insert(box.box * (1/epsilon))
                    
            elif j == len(cells) and 'T' in self.grid_link:
                # Gap M (Extreme Top): Only Drain buses (N_dev lines)
                gap_start_y = j*height + (j-1)*y_inner - 0.48
                gap_start_y = gap_start_y + y_outer if 'B' in self.grid_link else gap_start_y
                for k, dev in enumerate(different_devices):
                    # Drain lines
                    line_y = gap_start_y + self.vertical_distance + k * (self.connection_width + self.connections_distance)
                    box = Box(self.horizontal_distance, line_y, total_width, line_y + self.connection_width)
                    dbCreateRect(self, metal2_layer, box)
                    dbCreateLabel(self, metal2_layer, box.getCenter(), f"drain {dev}", 'centerCenter', 'R0', Font.EURO_STYLE, self.connection_width/2)
                    connections_list[dev]['drain_h'].insert(box.box * (1/epsilon))
                    
            else:
                continue;
                # Inner Gaps (Between devices): Drain buses for bottom device, THEN Source buses for top device (2 * N_dev lines)
                gap_start_y = y_outer + j*height + (j-1)*y_inner - 0.48
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
        
        def link_regions(vertical, horizontal):
            drain_intersections = vertical & horizontal
            shapes = drain_intersections.decompose_trapezoids()
            print(shapes.size())
            for shape in shapes:
                box = shape.bbox()
                mbox = Box()
                mbox.box = box
                #dbCreateRect(self, metal4_layer, mbox)
                self.genVia(mbox.getWidth()*epsilon, mbox.getHeight()*epsilon, mbox.getCenter().x*epsilon, mbox.getCenter().y*epsilon, 'Metal2', 'Metal3', True)
        
        def get_nearest_connection(contact, connections):
            return min(connections, key=lambda r: math.hypot(abs(r.bbox().center().x*epsilon - contact.getCenter().x)))
        
        for dev in connections_list:
            current_connection = connections_list[dev];
            drain_v = current_connection['drain_v']
            drain_h = current_connection['drain_h']
            source_v = current_connection['source_v']
            source_h = current_connection['source_h']  
            
            dev_drains = contact_list[dev]['drain']
            dev_sources = contact_list[dev]['source']
            
            link_regions(drain_v, drain_h)
            link_regions(source_v, source_h)
            ## connect drains together
            for dr_contact in dev_drains:
                nearest = get_nearest_connection(dr_contact, drain_v)
                nearest_box = Box(nearest.bbox().left * epsilon, dr_contact.bottom, nearest.bbox().right * epsilon ,dr_contact.top)
                self.genVia(nearest_box.getWidth(), nearest_box.getHeight(), nearest_box.getCenter().x, nearest_box.getCenter().y, 'Metal2', 'Metal3', True)
                connect_box = Box(dr_contact.left, dr_contact.bottom, nearest.bbox().right * epsilon, dr_contact.top)
                dbCreateRect(self, metal2_layer, connect_box)
            
            ## connect sources together
            for sc_contact in dev_sources:
                nearest = get_nearest_connection(sc_contact, source_v)
                nearest_box = Box(nearest.bbox().left * epsilon, sc_contact.bottom, nearest.bbox().right * epsilon ,sc_contact.top)
                self.genVia(nearest_box.getWidth(), nearest_box.getHeight(), nearest_box.getCenter().x, nearest_box.getCenter().y, 'Metal2', 'Metal3', True)
                connect_box = Box(nearest.bbox().left * epsilon, sc_contact.bottom, sc_contact.right, sc_contact.top)
                dbCreateRect(self, metal2_layer, connect_box)
        
        if self.guard_ring_ref == 'full':
            self.run_gen_guard_ring()
