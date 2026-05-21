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
        self.nr = nr if nr > 2 else 2
        self.nc = nc if nc > 2 else 2
        self.params = params
        self.pd = Numeric(params['pairs_distance']) * 1e6
        self.dd = Numeric(params['dummies_distance']) * 1e6
        self.cg = params['connect_gates'] == 'Yes'
        self.cs = params['connect_sources'] == 'Yes'
        self.s_d_mlayer = 'M1'
        self.gate_connection = 'none'
        self.gate_metal = 'M1'

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

    def genVia(self, vn_columns, vn_rows, offset_x=0, offset_y=0, b_layer = 'GatPoly', t_layer = 'Metal1'):
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
        self.sx = x_pos
        self.sy = y_pos
        if self.model_type == 'nmos' :
            return nmos.genDeviceLayout(self)
        else:
            return pmos.genDeviceLayout(self)


    def genDeviceLayout(self):
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
        if self.model_type.__contains__('pmos'):
            self.w = self.w * 1e-6
            self.l = self.l * 1e-6
        self.sx = 0
        via_start_offset = 0.34
        self.sy = 0
        device_step_x = 0;
        device_step_y = 0;
        y_offset = 1
        x_offset = self.pd
        contact_distance = 0.3
        max_right = 0
        min_bottom_step = 0;
        i = 0
        device_width = 0
        device_height = 0
        via_step_x_start = via_start_offset
        via_step_x = via_step_x_start
        via_width = 0;
        met_via_width = 0;
        met_via_height = 0;
        via_height = 0;
        via_shift = 0;
        left_origin_distance = 0;
        via_count = 1 if l_com < 0.7 else math.ceil(l_com/0.45)
        metal_via_count = math.ceil(2*via_count/3)



        for i in range(self.nr):
            for j in range(self.nc):
                via_step_x = via_step_x_start + device_step_x*j
                self.sy = device_step_y * (i)
                device = main_device.genDeviceLayout(self)
                (min_left, min_bottom, max_right, max_top) = self.getMaxDeviceSize()
                if i == 0 and j == 0:
                    left_origin_distance = min_left
                if min_bottom_step != 0:
                    if device_width == 0:
                        device_width = device_step_x - x_offset
                        device_height = max_top - min_bottom
                    via_shift = l_com - via_width if j+1 > self.nc/2 else 0
                    if i > 0 and self.cg:
                        device_y_offset = - gatpoly_Activ_over + device_step_y*(i-1)
                        via_y_offset = device_y_offset - gatpoly_Activ_over/2
                        #via_2_y_offset = - y_offset + 0.41 + min_bottom_step + device_step_y*(i-1)
                        via_x_offset = via_step_x + via_shift
                        width, height = self.genVia( via_count ,2,via_x_offset, via_y_offset)
                        shift_value = via_width - met_via_width;
                        via_shift = 0 if j < self.nc/2 else shift_value ;
                        (met_via_width, met_via_height) = self.genVia(metal_via_count, 2, via_x_offset + via_shift, via_y_offset, 'Metal1', 'Metal2')
                        via_next_step_x = via_step_x_start + device_step_x*(j+1)
                        if via_width == 0:
                            via_width = width
                            via_height = height
                        if j%2 == 0:
                            # connect met vias
                            met2_box = Box(via_x_offset, via_y_offset,via_next_step_x + l_com, via_y_offset - via_height )
                            dbCreateRect(self, metal2_layer, met2_box)
                            # connect gat poly
                            gat_box = Box(via_step_x, device_y_offset, via_step_x + l_com + device_step_x*(j+1), device_y_offset - y_offset + gatpoly_Activ_over)
                            dbCreateRect(self, poly_layer, gat_box)
                    # link sources together
                    if self.cs and i == self.nr -1:
                        met1_box = Box(device_step_x - x_offset - cont_Activ_overRec + left_origin_distance,  device_step_y*i - self.guardRingDistance - gatpoly_Activ_over, device_step_x + cont_Activ_overRec, - device_step_y - y_offset + self.guardRingDistance)
                        dbCreateRect(self, metall_layer, met1_box)

                print(min_left,' , ', min_bottom, '  ,  ', max_right,' , ', max_top)
                device_step_x = max_right + x_offset if device_step_x == 0 else device_step_x
                print ("device step x: ", device_step_x)
                self.sx = device_step_x * (j+1)
            (min_left, min_bottom, max_right, max_top) = self.getMaxDeviceSize()
            min_bottom_step = min_bottom if i == 0 else min_bottom_step;
            device_step_y = -max_top - y_offset + (-min_bottom_step - gatpoly_Activ_over) if device_step_y == 0 else device_step_y
            print ("device step y: ", device_step_y)
            self.sx = 0
        
        x_offset = -contact_distance + left_origin_distance;
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
                device = main_device.genDeviceLayout(self)
                if i > 0 :
                    via_2_step_y = - y_offset + 0.41 + min_bottom_step + device_step_y*(i-1)
                    device_y_offset = - gatpoly_Activ_over + device_step_y*(i-1)
                    via_step_y = device_y_offset - gatpoly_Activ_over/2
                    via_y_offset = device_y_offset - gatpoly_Activ_over/2
                    (width, height) = self.genVia( via_count ,2,via_step_x, via_y_offset)
                    if via_width == 0:
                        via_width = width
                        via_height = height
                    gat_box = Box(via_step_x, device_y_offset, via_step_x + l_com, via_2_step_y - via_height)
                    dbCreateRect(self, poly_layer, gat_box)
                self.sx = min_with_dummies + device_step_x * (j+1)
            self.sx = min_with_dummies
        (min_left_org, min_bottom_org, max_right_org, max_top_org) = self.getMaxDeviceSize()
        guard_ring_offset = self.guardRingDistance
        met_box = Box(min_with_dummies - guard_ring_offset - distance_from_origin, max_top if self.cs else max_top + guard_ring_offset , -self.dd-distance_from_origin, min_bottom if self.cs else min_bottom - guard_ring_offset)
        dbCreateRect(self, metall_layer,met_box)
        max_width_dummies = max_right_org + self.dd ;
        via_step_x_start = via_start_offset + max_width_dummies
        via_step_x = via_step_x_start
        via_shift = l_com - via_width
        for i in range(self.nr):
            for j in range(self.nd):
                self.sx = max_width_dummies +  device_step_x * j
                self.sy = device_step_y * (i)
                via_step_x = via_step_x_start + device_step_x*j
                device = main_device.genDeviceLayout(self)
                if i > 0 :
                    via_2_step_y = - y_offset + 0.41 + min_bottom_step + device_step_y*(i-1)
                    device_y_offset = - gatpoly_Activ_over + device_step_y*(i-1)
                    via_y_offset = device_y_offset - gatpoly_Activ_over/2
                    self.genVia( via_count ,2,via_step_x + via_shift, via_y_offset)
                    gat_box = Box(via_step_x, device_y_offset, via_step_x + l_com, via_2_step_y - via_height)
                    dbCreateRect(self, poly_layer, gat_box)
        
        (min_left, min_bottom, max_right, max_top) = self.getMaxDeviceSize()
        th_offset = guard_ring_offset if self.cs else 0
        th_box = Box(min_left_org, max_top_org - th_offset, max_right, min_bottom_org + th_offset)
        if self.model_type.__contains__('HV'):
            dbCreateRect(self, tgo_layer, th_box)
        if self.model_type.__contains__('pmos'):
            dbCreateRect(self, pdiffx_layer, th_box)
            

        met_box = Box(max_width_dummies, max_top , max_right + guard_ring_offset, min_bottom )
        dbCreateRect(self, metall_layer,met_box)   

        #dbCreateRect(self, poly_layer, Box(device_width/2 - l/2, min_bottom_step, max_right - device_width/2 + l/2, -y_offset))
        ### Create vias between gate and poly layer


        ###########################################

            
        print("Device layout generated")
        self.guardRingType = GuardRingType.NWELL if self.model_type.__contains__('pmos') else GuardRingType.PSUB ;
        self.guardRingDistance = 0
        #print(device.shapes[0].bbox.getLeft())

        
