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

__version__ = '$Revision: #3 $'

from cni.dlo import *
import cni.text
from .guard_ring_code import GuardRingType
from .geometry import *
from .nmos_code import nmos
from .pmos_code import pmos
from .device_base_code import DeviceBase
from .via_stack_code import via_stack
from .nmosHV_code import nmosHV
from .pmosHV_code import pmosHV


class diff_pairs(DeviceBase):
    @classmethod
    def defineParamSpecs(cls, specs):
        techparams = specs.tech.getTechParams()

        CDFVersion = techparams['CDFVersion']
        defL       = techparams['nmos_defL']
        defW       = techparams['nmos_defW']
        defNG      = techparams['nmos_defNG']
        minL       = techparams['nmos_minL']
        minW       = techparams['nmos_minW']

        specs('cdf_version', CDFVersion, 'CDF Version')
        #specs('Display', 'Selected', 'Display', ChoiceConstraint(['All', 'Selected']))

        specs('w' , '5u', 'Width')
        #specs('ws',   eng_string(Numeric(defW)/Numeric(defNG)), 'SingleWidth')
        specs('l' ,   '3u', 'Length')
        specs('connect_sources', 'Yes', 'Connect sources?', ChoiceConstraint(['No', 'Yes']))
        specs('connect_gates', 'Yes', 'Connect gates?', ChoiceConstraint(['No', 'Yes']))
        #specs('Wmin', minW, 'Wmin')
        #specs('Lmin', minL, 'Lmin')
        #specs('ng',   defNG, 'Number of Gates')

        #specs('m', '1', 'Multiplier')
        #specs('trise', '', 'Temp rise from ambient')
        specs('pairs_distance', '0.21u', 'Diffrential pairs distance')
        specs('dummies_distance', '0.3u', 'Dummies distance')
        specs('n_dummies', 1, 'Number of dummy fingers on each side')
        specs('n_rows', 2, 'Number of rows')
        specs('n_cells', 2, 'Number of cells')
        specs('model_type', 'nmos', 'Model Type', ChoiceConstraint(['nmos', 'pmos', 'nmosHV', 'pmosHV']))

        super().defineParamSpecs(specs)

    def setupParams(self, params):
        # process parameter values entered by user
        self.w  = Numeric(params['w'])*1e6
        self.l  = Numeric(params['l'])*1e6
        self.ng = 1
        self.nd = int(params['n_dummies'])
        self.model_type = params['model_type']
        nr = int(params['n_rows'])
        nc = int(params['n_cells'])
        self.nr = nr if nr < 2 else 2
        self.nc = nc if nc < 2 else 2
        self.params = params
        self.pd = Numeric(params['pairs_distance']) * 1e6
        self.dd = Numeric(params['dummies_distance']) * 1e6
        self.cg = params['connect_gates'] == 'Yes'
        self.cs = params['connect_sources'] == 'Yes'

        super().setupParams(params)

    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return [GuardRingType.AUTO]

    def getMaxDeviceSize(device):
        ## returns the current device dimensions.
        min_left = INT_MAX
        min_bottom = INT_MAX
        max_right = INT_MIN
        max_top = INT_MIN
        for s in device.getShapes():
            if isinstance(s, cni.text.Text):
                continue

            bbox = s.bbox
            min_left = min(min_left, bbox.left)
            min_bottom = min(min_bottom, bbox.bottom)
            max_right = max(max_right, bbox.right)
            max_top = max(max_top, bbox.top)
        return (min_left, min_bottom, max_right, max_top)

    def genVia(self, vn_columns, vn_rows, offset_x=0, offset_y=0, b_layer = 'GatPoly', t_layer = 'Metal1'):
        # this method used to generate a via stack on a specified position and row/column numbers.
        self.sx = offset_x
        self.sy = offset_y
        self.b_layer = b_layer
        self.t_layer = t_layer
        self.vn_columns = vn_columns
        self.vn_rows = vn_rows
        self.vt1_columns = 0
        self.vt1_rows = 0
        self.vt2_columns = 0
        self.vt2_rows = 0
        return via_stack.genLayout(self)
    
    def genMos(self, x_pos, y_pos):
        # this method used to generate a single mos device on a specified position.
        self.sx = x_pos
        self.sy = y_pos
        if self.model_type == 'nmos' :
            return nmos.genDeviceLayout(self)
        else:
            return pmos.genDeviceLayout(self)


    def genDeviceLayout(self):
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
        cont_Activ_overRec = techparams['Cnt_c']
        gatpoly_Activ_over = techparams['Gat_c']

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
        
        ## determine the main device to use based on the model type
        main_device = None
        if self.model_type == 'nmos' :
            main_device = nmos
        elif self.model_type == 'pmos':
            main_device = pmos
        elif self.model_type == 'nmosHV':
            main_device = nmosHV
        else:
            main_device = pmosHV
        
        device_length = self.l ## saving the device length before the pmos temporary fix.
        
        ## The Pmos devices multiply the l and w by 1e6 on the genLayout method, but the nmos multiply them on the setupParams method.
        ## !! To review !!
        ## Temporary fix
        if self.model_type.__contains__('pmos'):
            self.w = self.w * 1e-6
            self.l = self.l * 1e-6
        
        self.sx = 0 # the current x position for the device layout generation, it will be updated after each device generation based on the max right of the generated device and the defined x offset.
        self.sy = 0 # the current y position for the device layout generation, it will be updated after each row generation based on the max top of the generated device and the defined y offset.
        via_start_offset = 0.34 # the distance from the device origin to the gate edge.
        device_step_x = 0; # will be determined later (step between two cols origins)
        device_step_y = 0; # will be determined later (step between two rows origins)
        y_offset = 1; # the distance between two rows, will be updated later to a user input
        x_offset = self.pd # the distance between the end of the device and the start of the next one. set by the user
        contact_overlap_offset = 0.3 # if the devices distance is 0, this is the required offset to draw the two devices contacts on each other.
        max_right = 0 # current layout max right x coordinate
        origin_bottom_distance = 0; # the distance between the device origin and the lowest point of the device.
        origin_maxleft_distance = 0; # the distance between the device origin and the leftmost point of the device, will be used to determine the x offset for the dummy devices.
        i = 0; 
        device_width = 0; # the device width, will be determined later based on the generated device width and the defined x offset.
        via_step_x_start = via_start_offset # the current via start x position. will be updated for the dummies.
        via_step_x = via_step_x_start # the current via x position.
        via_width = 0; # dynamically determined via width based on the first generated via.
        via_height = 0; # dynamically determined via height based on the first generated via.
        via_shift = 0; # for the devices on the right side of the layout, the vias will be shifted to the right by this value to be aligned with the gate edge.
        via_count = 1 if device_length < 0.7 else math.ceil(device_length/0.45) # the number of vias to connect the gate to the first metal layer, it is determined based on the device length and the maximum via spacing defined in the design rules.
        metal_via_count = math.ceil(via_count/3) # these vias are used to connect the gates with each other.


        ## Generate the main pair devices
        for i in range(self.nr): ## rows loop
            for j in range(self.nc): ## cols loop
                via_step_x = via_step_x_start + device_step_x*j # update the via x position for each device based on the current device step x and the column number.
                self.sy = device_step_y * (i) ## the same value used for the vias, so it must be updated on each loop for the device generation.
                main_device.genDeviceLayout(self) ## generate the main device layout based on the defined main device class (nmos, pmos, nmosHV or pmosHV) and the current sx and sy values.
                (min_left, min_bottom, max_right, max_top) = self.getMaxDeviceSize() ## get the current cell dimentions.
                if i == 0 and j == 0:
                    origin_maxleft_distance = min_left
                if origin_bottom_distance != 0:
                    if device_width == 0:
                        device_width = device_step_x - x_offset
                    via_shift = device_length - via_width if j+1 > self.nc/2 else 0
                    if i % 2 != 0 :
                        via_y_offset = -0.18 + device_step_y*(i-1)
                        via_2_y_offset = - y_offset + 0.41 + origin_bottom_distance + device_step_y*(i-1)
                        via_x_offset = via_step_x + via_shift
                        width, height = self.genVia( via_count ,1,via_x_offset, via_y_offset)
                        if via_width == 0:
                            via_width = width
                            via_height = height
                        gat_box = Box(via_step_x, via_y_offset, via_step_x + device_length, via_y_offset - via_height)
                        dbCreateRect(self, poly_layer, gat_box)
                        self.genVia( via_count ,1,via_x_offset, via_2_y_offset)
                        gat_box = Box(via_step_x, via_2_y_offset, via_step_x + device_length, via_2_y_offset - via_height)
                        dbCreateRect(self, poly_layer, gat_box)
                        # link sources together
                        met1_box = Box(device_step_x - x_offset - cont_Activ_overRec + origin_maxleft_distance,  device_step_y*(i), device_step_x + cont_Activ_overRec, - device_step_y*i - y_offset + origin_bottom_distance)
                        dbCreateRect(self, metall_layer, met1_box)
                        if j == 0 and via_width/3 >= min_metal_width and self.cg:
                            met2_box = Box(via_x_offset + 2*via_width/3, via_y_offset, via_x_offset + via_width, via_2_y_offset - via_height);
                            dbCreateRect(self, metal2_layer, met2_box)
                            via_2_x_position = via_x_offset + 2*via_width/3
                            (m_via_width, m_via_height) = self.genVia(metal_via_count, 1, via_2_x_position, via_y_offset, b_layer = 'Metal1', t_layer = 'Metal2')
                            met3_box = Box(via_x_offset, via_2_y_offset - via_height, via_x_offset + via_width/3, via_y_offset);
                            dbCreateRect(self, metal3_layer, met3_box)
                            via_3_x_distance = via_2_x_position -via_x_offset - m_via_width
                            via_3_margin =   (min_metal_distance - via_3_x_distance) if via_3_x_distance < min_metal_distance else 0
                            self.genVia(metal_via_count, 1, via_x_offset - via_3_margin, via_2_y_offset - 0.02, b_layer = 'Metal1', t_layer = 'Metal3')
                            met2_box = Box(via_x_offset + 2*via_width/3, via_2_y_offset, via_step_x_start + device_step_x*(j+1) + device_length/3, via_2_y_offset - via_height);
                            dbCreateRect(self, metal2_layer, met2_box)
                            met3_box = Box(via_x_offset, via_y_offset, via_step_x_start + device_step_x*(j+1) + device_length/3, via_y_offset - via_height);
                            dbCreateRect(self, metal3_layer, met3_box)
                        if j == 1 and via_width/3 >= min_metal_width and self.cg:
                            self.genVia(metal_via_count, 1, via_x_offset , via_y_offset, b_layer = 'Metal1', t_layer = 'Metal3')
                            self.genVia(metal_via_count, 1, via_x_offset , via_2_y_offset, b_layer = 'Metal1', t_layer = 'Metal2')

                print(min_left,' , ', min_bottom, '  ,  ', max_right,' , ', max_top)
                device_step_x = max_right + x_offset if device_step_x == 0 else device_step_x
                print ("device step x: ", device_step_x)
                self.sx = device_step_x * (j+1)
            (min_left, min_bottom, max_right, max_top) = self.getMaxDeviceSize()
            origin_bottom_distance = min_bottom if i == 0 else origin_bottom_distance;
            device_step_y = -max_top - y_offset if device_step_y == 0 else device_step_y
            print ("device step y: ", device_step_y)
            self.sx = 0
        
        x_offset = -contact_overlap_offset + origin_maxleft_distance;
        ## generate dummies
        self.dd = self.dd
        distance_from_origin = -min_left;
        min_with_dummies =  - ( device_width + x_offset) * self.nd - self.dd + x_offset;
        device_step_x = device_width + x_offset
        self.sx = min_with_dummies
        via_step_x_start = via_start_offset + min_with_dummies
        via_step_x = via_step_x_start
        for i in range(self.nr):
            for j in range(self.nd):
                self.sy = device_step_y * (i)
                via_step_x = via_step_x_start + device_step_x*j
                main_device.genDeviceLayout(self)
                if i % 2 != 0 :
                    via_step_y = -gatpoly_Activ_over + ( device_step_y)*(i-1)
                    self.genVia( via_count ,1,via_step_x, via_step_y)
                    gat_box = Box(via_step_x, via_step_y, via_step_x + device_length, via_step_y - via_height)
                    dbCreateRect(self, poly_layer, gat_box)
                    via_2_step_y = - y_offset + 0.41 + origin_bottom_distance + device_step_y*(i-1)
                    self.genVia( via_count ,1,via_step_x,  via_2_step_y)
                    gat_box = Box(via_step_x, via_2_step_y, via_step_x + device_length, via_2_step_y - via_height)
                    dbCreateRect(self, poly_layer, gat_box)
                print("Generated dummy device at sx=", self.sx, " sy=", self.sy)
                self.sx = min_with_dummies + device_step_x * (j+1)
            self.sx = min_with_dummies
        (min_left_org, min_bottom_org, max_right_org, max_top_org) = self.getMaxDeviceSize()
        guard_ring_offset = self.guardRingDistance
        met_box = Box(min_with_dummies - guard_ring_offset - distance_from_origin, max_top + guard_ring_offset, -self.dd-distance_from_origin, min_bottom - guard_ring_offset)
        dbCreateRect(self, metall_layer,met_box)
        max_width_dummies = max_right_org + self.dd ;
        via_step_x_start = via_start_offset + max_width_dummies
        via_step_x = via_step_x_start
        via_shift = device_length - via_width
        for i in range(self.nr):
            for j in range(self.nd):
                self.sx = max_width_dummies +  device_step_x * j
                self.sy = device_step_y * (i)
                via_step_x = via_step_x_start + device_step_x*j
                main_device.genDeviceLayout(self)
                if i % 2 != 0 :
                    via_step_y = -gatpoly_Activ_over +  device_step_y*(i-1)
                    via_2_step_y = -y_offset + 0.41 + origin_bottom_distance + device_step_y*(i-1)
                    self.genVia( via_count ,1,via_step_x + via_shift, via_step_y)
                    gat_box = Box(via_step_x, via_step_y, via_step_x + device_length, via_step_y - via_height)
                    dbCreateRect(self, poly_layer, gat_box)
                    self.genVia( via_count ,1,via_step_x + via_shift, via_2_step_y)
                    gat_box = Box(via_step_x, via_2_step_y, via_step_x + device_length, via_2_step_y - via_height)
                    dbCreateRect(self, poly_layer, gat_box)
                print("Generated dummy device at sx=", self.sx, " sy=", self.sy)
        
        (min_left, min_bottom, max_right, max_top) = self.getMaxDeviceSize()
        th_box = Box(min_left_org, max_top_org, max_right, min_bottom_org)
        if self.model_type.__contains__('HV'):
            dbCreateRect(self, tgo_layer, th_box)
        if self.model_type.__contains__('pmos'):
            dbCreateRect(self, pdiffx_layer, th_box)
            

        met_box = Box(max_width_dummies, max_top , max_right + guard_ring_offset, min_bottom )
        dbCreateRect(self, metall_layer,met_box)   

        #dbCreateRect(self, poly_layer, Box(device_width/2 - l/2, origin_bottom_distance, max_right - device_width/2 + l/2, -y_offset))
        ### Create vias between gate and poly layer


        ###########################################

            
        print("Device layout generated")
        self.guardRingType = GuardRingType.NWELL if self.model_type.__contains__('pmos') else GuardRingType.PSUB ;
        self.guardRingDistance = 0
        #print(device.shapes[0].bbox.getLeft())

        
