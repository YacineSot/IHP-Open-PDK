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

# FIX: Resolved shape.box returning boolean instead of Box object
# 
# Issue: dbLayerSize() function creates a padded shape around a polygon
# using layer (arg2) and padding value (arg3). The Polygon class inherits
# from Shape but incorrectly passed __polygon.box() (returns DBox object)
# to super().__init__(layer, box) instead of a proper Box object.
#
# Root cause: DBox objects evaluate to False in boolean contexts due to
# library overrides, causing shape.box to return False instead of the
# expected Box object.
#
# Solution: Convert DBox to Box object before passing to parent initializer.
# On the polygon.py file, the def __internalInit(self, layer: Layer) function, 
# Update the super().__init__(layer, self._polygon.bbox()) to a create Box (instead of the passed DBox object)
# for example: conv_box = Box(0,0,0,0)
#        conv_box.box = self._polygon.bbox()
#        super().__init__(layer, conv_box)

########################################################################
__version__ = '$Revision: #3 $'

import pya

import cni.rect
import cni.text
from cni.dlo import *
from .geometry import *
from .guard_ring_code import generate_guard_ring, GuardRingType, GuardRingShape
from .utility_functions import *
from .via_stack_code import *


class DeviceBase(DloGen):
    @classmethod
    def defineParamSpecs(cls, specs):
        cls.techparams = specs.tech.getTechParams()
        def_tap = {'north': True, 'south': True, 'west': True, 'east': True} if not hasattr(cls, 'default_tap') else cls.default_tap
        choices = [c.value for c in cls.validGuardRingTypes()]
        
        cls.default_ring = cls.default_ring if hasattr(cls, 'default_ring') else 'none'
        cls.default_distance = cls.default_distance if hasattr(cls, 'default_distance') else '0.8u'
        
        cls.add_separation(cls, specs, "Guard Ring Settings")
        specs('guardRingType', cls.default_ring, 'Guard Ring Type', ChoiceConstraint(choices))
        specs('guardRingDistance', cls.default_distance, 'Guard Ring Distance')
        specs('guardRingWidth', '0.3u', 'Guard Ring Width')
        specs('distribute_contacts', False, 'Contacts Follows Active', BooleanConstraint())
        cls.add_separation(self=cls, specs=specs, separator="")
        specs('north', def_tap['north'], 'Include North Side', BooleanConstraint())
        specs('south', def_tap['south'], 'Include South Side', BooleanConstraint())
        specs('west', def_tap['west'], 'Include West Side', BooleanConstraint())
        specs('east', def_tap['east'], 'Include East Side', BooleanConstraint())
        #specs('guardRingArray', False, 'Array Ring',ChoiceConstraint([True, False]))
        cls.add_separation(self=cls, specs=specs, separator="")
        if hasattr(cls, 'is_array') and cls.is_array:
            specs('rows', 1, 'Number of rows')
            specs('row_distance', '0u', 'Distance between rows')
            specs('tap_rows', True, 'Tap Between Rows', BooleanConstraint())
            specs('cells', 1, 'Number of cells')
            specs('cell_distance', '0u', 'Distance between cells')
            specs('tap_cells', True, 'Tap Between Cells', BooleanConstraint())

    def setupParams(self, params):
        # process parameter values entered by user
        self.guardRingType = 'none'
        self.rows = 1
        self.cells = 1  
        if 'guardRingType' in params and params['guardRingType'] != 'none':
            self.guardRingType     = GuardRingType(params['guardRingType'])
            self.guardRingDistance = Numeric(params['guardRingDistance'])*1e6
            self.guardRingShape = ''.join(side[0] for side in ['north', 'south', 'west', 'east'] if params.get(side))
            self.guardRingWidth = Numeric(params['guardRingWidth'])*1e6
            self.distribute_contacts = params['distribute_contacts'] if 'distribute_contacts' in params else False
        #self.guardRingArray = params['guardRingArray'] == 'yes'
            if hasattr(self, 'is_array') and self.is_array:
                self.cells = int(params['cells'])
                self.rows = int(params['rows'])
                self.row_distance = Numeric(params['row_distance'])*1e6
                self.cell_distance = Numeric(params['cell_distance'])*1e6
                self.tap_rows = params['tap_rows']
                self.tap_cells= params['tap_cells']
    
    
    def add_separation(self, specs, separator = 'Separator'):
        specs(f'_{separator}', f'----- {separator} -----','='*20, ReadOnlyConstraint())
    
    def instanciate_self(self, params, position):
        """
            Function to recreate the same object with different params
            Reusing the genDeviceLayout function
        """
        
        device = self.__class__()
        device.tech = self.tech
        device._getCurrentCellContext = self._getCurrentCellContext
        device.setupParams(params)
        device.sx = position.x
        device.sy = position.y
        device.genDeviceLayout()
        return device
    
    @staticmethod
    def fix_params_micro_unit(params, keys):
        """
            Function to prevent if the user enter big values (entring 1 instead of 1u)
        """
        for key in keys:
            print(f'checking key: {key}')
            if key in params and not str(params[key]).endswith('u'):
                if float(params[key]) > 0.13:
                    params[key] = params[key].strip()+'u'
    
    @staticmethod
    def get_dimensions(w, l, ng, techparams, gate_connection='T-B'):
        """
        Template method for subclasses to overwrite
        """
        return 0,0
    
    @abstractmethod
    def genDeviceLayout(self):
        """
        Template method for subclasses to overwrite
        """
        raise NotImplementedError()

    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return GuardRingType.cases()

    def genVia(self, vn_columns, vn_rows, offset_x=0, offset_y=0, b_layer = 'GatPoly', t_layer = 'Metal1', use_width = False, origin='centerCenter'):
        back_sx = self.sx if hasattr(self, 'sx') else 0
        back_sy = self.sy if hasattr(self, 'sy') else 0
        self.sx = offset_x
        self.sy = offset_y
        self.b_layer = b_layer
        self.t_layer = t_layer
        self.vn_columns = 0
        self.vn_rows = 0
        if not use_width:
            self.vn_columns = vn_columns
            self.vn_rows = vn_rows
        else :
            self.vn_total_width = vn_columns
            self.vn_total_height = vn_rows
        self.vt1_columns = 0
        self.vt1_rows = 0
        self.vt2_columns = 0
        self.vt2_rows = 0
        self.origin = origin
        vias = via_stack.genLayout(self)
        self.sx = back_sx
        self.sy = back_sy
        return vias
    
    def run_gen_guard_ring(self):
        if self.guardRingType != GuardRingType.NONE and self.guardRingShape:
            self.distribute_contacts = False if not hasattr(self,'distribute_contacts') else self.distribute_contacts
            min_left = INT_MAX
            min_bottom = INT_MAX
            max_right = INT_MIN
            max_top = INT_MIN

            for s in self.getShapes():
                if isinstance(s, cni.text.Text):
                    continue
                bbox = s.bbox
                if isinstance(bbox, bool):
                    print("Warning: encountered shape with boolean bbox, skipping it for guard ring generation")
                    print(f"The layer has noolean bbox {s.layer.name}")
                    print(bbox)
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

            w = max_right - min_left + self.guardRingDistance * 2.0
            h = max_top - min_bottom + self.guardRingDistance * 2.0

            x_center = min_left + (max_right - min_left) / 2.0
            y_center = min_bottom + (max_top - min_bottom) / 2.0

            generate_guard_ring(dlo_gen=self,
                                guard_ring_type=self.guardRingType,
                                guard_ring_shape=self.guardRingShape,
                                w=w,
                                h=h,
                                x_center=x_center,
                                y_center=y_center,
                                t=self.guardRingWidth,
                                distribute_contacts=self.distribute_contacts)
    
    def genArray(self):
        self.genDeviceLayout()
        return
        techparams = self.techparams
        cont_min_act_encl = techparams['Cnt_c']
        cont_size = techparams['Cnt_a']
        pdiffx_over = techparams['pSD_c1']
        tap_width = cont_min_act_encl*2 + pdiffx_over*2 + cont_size
        tap_width = max(self.guardRingWidth, tap_width)
        device_dimentions = (0,0)
        if hasattr(self, 'gate_connection'):
            device_dimentions = self.get_dimensions(self.w, self.l, self.ng, self.techparams, self.gate_connection)
        
        x_inner = self.cell_distance
        x_inner = 2*self.guardRingDistance + tap_width if self.tap_cells else x_inner
        
        y_inner = self.row_distance
        y_inner = 2*self.guardRingDistance + tap_width if self.tap_rows else y_inner
        
        
        
        for i in range(self.rows):
            for j in range(self.cells):
                self.sx =  device_dimentions[0]*i + x_inner*i
                self.sy = device_dimentions[1]*j + y_inner*j
                tap_bbox_width = device_dimentions[0] + 2*self.guardRingDistance - tap_width
                tap_bbox_height = device_dimentions[1] + 2*self.guardRingDistance
                tap_x_center = (i+1)*tap_bbox_width/2 + tap_bbox_width*i + (i+1)*tap_width/2
                tap_y_center = (j+1)*tap_bbox_height/2 + tap_bbox_height*j - (j+1)*tap_width
                self.genDeviceLayout()
                if self.rows - 1 or self.cells -1:
                    shape = ''
                    if i < self.rows - 1:
                        shape += 'e'
                    if j > 0:
                        shape += 's'
                    generate_guard_ring(self, self.guardRingType, shape, tap_bbox_width, tap_bbox_height, tap_x_center, tap_y_center, self.guardRingWidth)
    
    
    def genLayout(self):
        self.genArray()
        if (self.rows - 1 or self.cells -1) and False:  
            pdiffx_over = techparams['pSD_c1']
            self.guardRingDistance = -pdiffx_over
        self.run_gen_guard_ring()
        
