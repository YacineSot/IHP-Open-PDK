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

from cni.dlo import *
from .geometry import *
from .thermal import *
from .utility_functions import *

import math

class via_stack(DloGen):

    @classmethod
    def defineParamSpecs(self, specs):
        # define parameters and default values
        techparams = specs.tech.getTechParams()
        
#ifdef KLAYOUT
#else
        CDFVersion = techparams['CDFVersion']
        specs('cdf_version', CDFVersion, 'CDF Version')
#endif

        # SG13CMOS5L: M1-M4-TM1 stack (Metal5 removed, TopMetal1 as top layer)
        specs('b_layer', 'Metal1', 'Bottom layer', ChoiceConstraint(['Activ','GatPoly','Metal1', 'Metal2', 'Metal3', 'Metal4', 'Metal5', 'TopMetal1']))
        specs('t_layer', 'Metal2', 'Top layer', ChoiceConstraint(['Metal1', 'Metal2', 'Metal3', 'Metal4', 'Metal5', 'TopMetal1', 'TopMetal2']))
        specs('vn_columns', 2, 'Via_n Columns')
        specs('vn_rows', 2, 'Via_n Rows')
        specs('extra_vias', 'no', 'Add extra vias', ChoiceConstraint(['yes', 'no']))

    def setupParams(self, params):
        # process parameter values entered by user
        self.params = params
        self.extra_vias = params['extra_vias'] == 'yes'
        self.b_layer = params['b_layer']
        self.t_layer = params['t_layer']
        self.vn_columns = params['vn_columns']
        self.vn_rows = params['vn_rows']
    
    
    def genLayout(self):

        b_layer = self.b_layer
        t_layer = self.t_layer

        self.techparams = self.tech.getTechParams()
        self.epsilon = self.techparams['epsilon1']
        self.grid = self.tech.getGridResolution()         # needed for Dogbone
        
        offset_x = self.sx if hasattr(self, 'sx') and self.sx is not None else 0
        offset_y = self.sy if hasattr(self, 'sy') and self.sy is not None else 0


        Cell = self.__class__.__name__

        textlayer = 'TEXT'

        #*************************************************************************
        #*
        #* Generic Design Rule Definitions
        #*
        #************************************************************************

        epsilon = techparams['epsilon1']
        cont_size = self.techparams['Cnt_a']
        cont_enc1 = self.techparams['Cnt_c']
        cont_enc2 = self.techparams['M1_c1']
        cont_enc3 = self.techparams['M1_c']
        cont_sep1 = self.techparams['Cnt_b']
        cont_sep2 = self.techparams['Cnt_b1']

        v1_size = techparams['V1_a']
        v1_sep1 = techparams['V1_b']
        v1_sep2 = techparams['V1_b1']
        v1_enc = techparams['V1_c1']
        v1_enc1 = techparams['V1_c']

        vn_size = techparams['Vn_a']
        vn_sep1 = techparams['Vn_b']
        vn_sep2 = techparams['Vn_b1']
        vn_enc = techparams['Vn_c1']
        vn_enc1 = techparams['Vn_c']

        # TopVia1 parameters for M5-TM1 connection
        # TopVia1 is larger than regular vias (0.42um vs 0.19um)
        tv1_size = techparams.get('TV1_a', 0.42)  # TopVia1 size
        tv1_sep = techparams.get('TV1_b', 0.42)   # TopVia1 spacing
        tv1_enc = techparams.get('TV1_c', 0.10)   # Metal4 enclosure of TopVia1
        tm1_enc = techparams.get('TV1_d', 0.42)   # TopMetal1 enclosure of TopVia1
        # TopVia2
        tv2_size = techparams.get('TV2_a', 0.42)  # TopVia1 size
        tv2_sep = techparams.get('TV2_b', 0.42)   # TopVia1 spacing
        tv2_enc = techparams.get('TV2_c', 0.10)   # Metal4 enclosure of TopVia1
        tm2_enc = techparams.get('TV2_d', 0.42)   # TopMetal1 enclosure of TopVia1
        #*************************************************************************
        #*
        #* Device Specific Design Rule Definitions
        #*
        #************************************************************************

        vn_columns = self.vn_columns if self.vn_columns > 0 else 1
        vn_rows = self.vn_rows if self.vn_rows > 0 else 1
        vn_total_width = self.vn_total_width if hasattr(self, 'vn_total_width') else 0
        vn_total_height = self.vn_total_height if hasattr(self, 'vn_total_height') else 0

        # SG13CMOS5L: M1-M4-TM1 metal stack (TopVia1 connects M4 to TopMetal1)
        metal_layers = ['Metal1', 'Metal2', 'Metal3', 'Metal4', 'Metal5', 'TopMetal1', 'TopMetal2']
        via_layers = ['Via1', 'Via2', 'Via3', 'Via4', 'TopVia1', 'TopVia2']
        
        #*************************************************************************
        #*
        #* Main body of code
        #*
        #************************************************************************
        if self.b_layer in ['GatPoly', 'Activ']:
            metal_layers.insert(0,self.b_layer)
            via_layers.insert(0, 'Cont')
        idx_b = metal_layers.index(b_layer)
        idx_t = metal_layers.index(t_layer)
        if idx_b > idx_t:
            idx_b, idx_t = idx_t, idx_b
            b_layer, t_layer = t_layer, b_layer  # Also swap layer names
        stack_layers = metal_layers[idx_b:idx_t+1]
        def via_count_from_size(via_size, via_sep, via_total_size, via_num):
            ret = max(math.floor((via_total_size + via_sep)/(via_size + via_sep)), 1) if via_total_size > 0 else via_num
            return ret -1 if via_num == 0 else ret

        if vn_total_width == 0 and self.extra_vias:
            via_size = vn_size
            via_sep = vn_sep2
            via_enc = vn_enc1
            if t_layer == 'TopMetal2':
                via_size = tv2_size
                via_sep = tv2_sep
                via_enc = tm2_enc
            elif t_layer == 'TopMetal1':
                via_size = tv1_size
                via_sep = tv1_sep
                via_enc = tm1_enc
            elif t_layer == 'Metal1':
                via_size = cont_size
                via_sep = cont_sep2
                via_enc = cont_enc2
            vn_total_width = (vn_columns * via_size + (vn_columns - 1) * via_sep) + 2*via_enc
            vn_total_height = (vn_rows * via_size + (vn_rows - 1) * via_sep) + 2*via_enc
                
                
        
        cont_cols_from_size = via_count_from_size(cont_size, cont_sep2, vn_total_width - cont_enc1*2, vn_columns)
        cont_rows_from_size = via_count_from_size(cont_size, cont_sep2, vn_total_height, vn_rows)
        v1_cols_from_size = via_count_from_size(v1_size, v1_sep2, vn_total_width, vn_columns)
        v1_rows_from_size = via_count_from_size(v1_size, v1_sep2, vn_total_height, vn_rows)
        vn_cols_from_size = via_count_from_size(vn_size, vn_sep2, vn_total_width, vn_columns)
        vn_rows_from_size = via_count_from_size(vn_size, vn_sep2, vn_total_height, vn_rows)
        tv1_cols_from_size = via_count_from_size(tv1_size, tv1_sep, vn_total_width, vn_columns)
        tv1_rows_from_size = via_count_from_size(tv1_size, tv1_sep, vn_total_height, vn_rows)
        tv2_cols_from_size = via_count_from_size(tv2_size, tv2_sep, vn_total_width, vn_columns)
        tv2_rows_from_size = via_count_from_size(tv2_size, tv2_sep, vn_total_height, vn_rows)

        for layer in stack_layers:
            via_enc1 = None
            #pre-procesing
            if layer in ['Activ', 'GatPoly']:
                columns = cont_cols_from_size
                rows = cont_rows_from_size
                via_size = cont_size
                via_enc = cont_enc1
                via_sep = cont_sep1 if (columns<4 and rows<4) else cont_sep2
                w_x = (columns * via_size + (columns - 1) * via_sep)
                w_y = (rows * via_size + (rows - 1) * via_sep)
                via_array_w_x = w_x
                via_array_w_y = w_y
            elif t_layer == 'Metal1':
                columns = cont_cols_from_size
                rows = cont_rows_from_size
                via_size = cont_size
                via_sep = cont_sep1 if (columns<4 and rows<4) else cont_sep2
                via_enc = cont_enc2
                via_enc1 = cont_enc3
                w_x = (columns * via_size + (columns - 1) * via_sep)
                w_y = (rows * via_size + (rows - 1) * via_sep)
                via_array_w_x = w_x
                via_array_w_y = w_y
            elif layer == 'Metal1':
                columns = v1_cols_from_size
                rows = v1_rows_from_size
                via_size = v1_size
                via_sep = v1_sep1 if (columns<4 and rows<4) else v1_sep2
                via_enc = v1_enc
                via_enc1 = v1_enc1
                w_x = (columns * via_size + (columns - 1) * via_sep)
                w_y = (rows * via_size + (rows - 1) * via_sep)
                via_array_w_x = w_x
                via_array_w_y = w_y

            elif layer == 'TopMetal1':  # TopMetal1 uses TopVia1 (larger vias)
                columns = tv1_cols_from_size
                rows = tv1_rows_from_size
                via_size = tv1_size
                via_sep = tv1_sep
                via_enc = tm1_enc  # TopMetal1 enclosure of TopVia1
                w_x = (columns * via_size + (columns - 1) * via_sep)
                w_y = (rows * via_size + (rows - 1) * via_sep)
                via_array_w_x = w_x
                via_array_w_y = w_y
            elif layer == 'TopMetal2':  # TopMetal1 uses TopVia1 (larger vias)
                columns = tv2_cols_from_size
                rows = tv2_rows_from_size
                via_size = tv2_size
                via_sep = tv2_sep
                via_enc = tm2_enc  # TopMetal1 enclosure of TopVia1
                w_x = (columns * via_size + (columns - 1) * via_sep)
                w_y = (rows * via_size + (rows - 1) * via_sep)
                via_array_w_x = w_x
                via_array_w_y = w_y

            elif layer == 'Metal5' and 'TopMetal1' in stack_layers:
                # Metal4 connected to TopMetal1: M4 area must match TM1 area
                columns = vn_cols_from_size
                rows = vn_rows_from_size
                # Via3 parameters (for drawing Via3 - keep original size)
                via_size = vn_size
                via_sep = vn_sep1 if (columns<4 and rows<4) else vn_sep2
                via_enc = tm1_enc  # Use TM1 enclosure so M4 rect = TM1 rect
                # Via3 array size (for positioning Via3)
                via_array_w_x = (columns * via_size + (columns - 1) * via_sep)
                via_array_w_y = (rows * via_size + (rows - 1) * via_sep)
                # Metal4 rectangle uses TopVia1 params (matches TM1 area)
                w_x = (tv1_cols_from_size * tv1_size + (tv1_cols_from_size - 1) * tv1_sep)
                w_y = (tv1_rows_from_size * tv1_size + (tv1_rows_from_size - 1) * tv1_sep)

            else:  # Metal2, Metal3, or Metal4 without TopMetal1
                columns = vn_cols_from_size
                rows = vn_rows_from_size
                via_size = vn_size
                via_sep = vn_sep1 if (columns<4 and rows<4) else vn_sep2
                via_enc = vn_enc
                via_enc1 = vn_enc1
                w_x = (columns * via_size + (columns - 1) * via_sep)
                w_y = (rows * via_size + (rows - 1) * via_sep)
                via_array_w_x = w_x
                via_array_w_y = w_y
            via_enc1 = via_enc if via_enc1 == None else via_enc1
            
            box_w = w_x/2 + via_enc 
            box_h = w_y/2 + via_enc1 
            if layer in ['Activ', 'GatPoly'] :
                if vn_total_width != 0:
                    box_w = max(box_w, vn_total_width/2)
                if vn_total_height != 0:
                    box_h = max(vn_total_height/2, box_h)
    
            metal_box = Box(-box_w + offset_x, -box_h + offset_y, box_w + offset_x, box_h + offset_y)
            
            #metal draw
            dbCreateRect(self, layer, metal_box)

            if layer == 'Metal1':
                columns = cont_cols_from_size
                rows = cont_rows_from_size
                via_size = cont_size
                via_sep = cont_sep1 if (columns<4 and rows<4) else cont_sep2
                via_enc = cont_enc2
                via_enc1 = cont_enc3
                w_x = (columns * via_size + (columns - 1) * via_sep)
                w_y = (rows * via_size + (rows - 1) * via_sep)
                via_array_w_x = w_x
                via_array_w_y = w_y
            
            #via draw
            if layer != b_layer:
                via_layer = via_layers[metal_layers.index(layer)-1]
                for i in range(columns):
                    x0 = i * via_sep + i * via_size - via_array_w_x/2 + offset_x
                    for j in range(rows):
                        y0 = j * via_sep + j * via_size - via_array_w_y/2 + offset_y
                        dbCreateRect(self, via_layer, Box(x0, y0, x0 + via_size, y0 + via_size))
