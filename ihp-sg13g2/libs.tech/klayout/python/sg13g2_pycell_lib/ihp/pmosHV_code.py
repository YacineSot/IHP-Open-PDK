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
from .device_base_code import DeviceBase
from .geometry import *
from .guard_ring_code import GuardRingType
from .thermal import *
from .utility_functions import *
from .via_stack_code import *

import math

class pmosHV(DeviceBase):

    @classmethod
    def defineParamSpecs(self, specs):
        techparams = specs.tech.getTechParams()

        CDFVersion = techparams['CDFVersion']
        model      = 'sg13_hv_pmos'
        defL       = techparams['pmosHV_defL']
        defW       = techparams['pmosHV_defW']
        defNG      = techparams['pmosHV_defNG']
        minL       = techparams['pmosHV_minL']
        minW       = techparams['pmosHV_minW']

        specs('cdf_version', CDFVersion, 'CDF Version')
        specs('Display', 'Selected', 'Display', ChoiceConstraint(['All', 'Selected']))
        specs('model', model, 'Model name')

        specs('w' ,   defW, 'Width')

        test = Numeric(defW)
        # specs('ws',   eng_string(Numeric(defW)/Numeric(defNG)), 'SingleWidth')
        specs('l' ,   defL, 'Length')
        # specs('Wmin', minW, 'Wmin')
        # specs('Lmin', minL, 'Lmin')
        specs('ng',   defNG, 'Number of Gates')

        # specs('m', '1', 'Multiplier')
        # specs('trise', '', 'Temp rise from ambient')
        specs('s_d_mlayer', 'M2', 'S/D Metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        specs('gate_connection', 'T-B', 'Gate contact position', ChoiceConstraint(['T-B', 'T', 'B', 'none']))
        specs('gate_metal', 'M2', 'Gate contact metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        self.default_ring =  'nwell'
        self.default_distance = '0.57u'
        super().defineParamSpecs(specs)

    def setupParams(self, params):
        # process parameter values entered by user
        self.params = params
        self.s_d_mlayer = params['s_d_mlayer']
        self.gate_connection = params['gate_connection']
        self.gate_metal = params['gate_metal']
        self.w = Numeric(params['w'])
        self.l = Numeric(params['l'])
        self.ng = Numeric(params['ng'])

        super().setupParams(params)

    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return [GuardRingType.NONE, GuardRingType.NWELL]

    def genVia(self, vn_columns, vn_rows, offset_x=0, offset_y=0, b_layer = 'GatPoly', t_layer = 'Metal1', use_width = False):
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
        vias = via_stack.genLayout(self)
        self.sx = back_sx
        self.sy = back_sy
        return vias
    
    def genDeviceLayout(self):
        self.grid = self.tech.getGridResolution()
        self.techparams = self.tech.getTechParams()
        self.epsilon = self.techparams['epsilon1']

        w = self.w
        ng = self.ng
        l = self.l
        start_x = self.sx if hasattr(self, 'sx') and self.sx is not None else 0
        start_y = self.sy if hasattr(self, 'sy') and self.sy is not None else 0


        ndiff_layer = Layer('Activ', 'drawing')     # 1
        pdiff_layer = Layer('Activ', 'drawing')     # 1
        poly_layer = Layer('GatPoly', 'drawing')    # 5
        poly_layer_pin = Layer('GatPoly', 'pin')
        locint_layer = Layer('Cont', 'drawing')     # 6
        metall_layer = Layer('Metal1', 'drawing')   # 8
        metall_layer_pin = Layer('Metal1', 'pin')
        pdiffx_layer = Layer('pSD', 'drawing')      # 14
        well_layer = Layer('NWell', 'drawing')      # 31
        tgo_layer = Layer('ThickGateOx', 'drawing') # 44
        text_layer = Layer('TEXT', 'drawing')        # 63

        endcap = self.techparams['M1_c1']
        cont_size = self.techparams['Cnt_a']
        cont_dist = self.techparams['Cnt_b']
        cont_dist_act = self.techparams['Cnt_e']
        cont_Activ_overRec = self.techparams['Cnt_c']
        cont_metall_over = self.techparams['M1_c']
        psd_pActiv_over = self.techparams['pSD_c']    # pSD enc. of p+-Activ in nwell
        nwell_pActiv_over = self.techparams['NW_c1']  # NWell enc. of pActiv
        gatpoly_Activ_over = self.techparams['Gat_c'] # poly overlap of Activ (endcap)
        gatpoly_cont_dist = self.techparams['Cnt_f']
        smallw_gatpoly_cont_dist = cont_Activ_overRec+self.techparams['Gat_d'] # for w < contActMin -> poly dogbone sep. to gate
        psd_PFET_over = self.techparams['pSD_i1']     # pSD enc. of Gate
        
        wmin = Numeric(self.techparams['pmosHV_minW'])
        lmin = Numeric(self.techparams['pmosHV_minL'])
        contActMin = 2*cont_Activ_overRec+cont_size
        thGateOxGat = self.techparams['TGO_c'] # Overlay over GatPoly
        thGateOxAct = self.techparams['TGO_a'] # Overlay over Active

        dbReplaceProp(self, 'pin#', 5)

        w = w*1e6;
        l = l*1e6;
        ng = math.floor(Numeric(ng)+self.epsilon)
        w = w/ng
        w = GridFix(w)
        l = GridFix(l)

        if w < contActMin-self.epsilon :
            gatpoly_cont_dist = smallw_gatpoly_cont_dist

        xdiff_beg = start_x
        ydiff_beg = start_y
        ydiff_end = start_y + w

        if w < wmin-self.epsilon :
            hiGetAttention()
            print('Width < '+str(wmin))
            w = wmin

        if l < lmin-self.epsilon :
            hiGetAttention()
            print('Length < '+str(lmin))
            l = lmin

        if ng < 1 :
            hiGetAttention()
            print('Minimum one finger')
            ng = 1

        xanz = math.floor((w-2*cont_Activ_overRec+cont_dist)/(cont_size+cont_dist)+self.epsilon)
        w1 = xanz*(cont_size+cont_dist)-cont_dist+cont_Activ_overRec+cont_Activ_overRec
        xoffset = (w-w1)/2
        xoffset = GridFix(xoffset)
        diffoffset = 0
        if w < contActMin :
            xoffset = start_x
            diffoffset = (contActMin-w)/2
            diffoffset = Snap(diffoffset)

        # get the number of contacts
        lcon = w-2*cont_Activ_overRec
        distc = cont_size+cont_dist
        ncont = math.floor((lcon+cont_dist-2*endcap)/distc + self.epsilon)
        if zerop(ncont) :
            ncont = 1

        diff_cont_offset = GridFix((w-2*cont_Activ_overRec-ncont*cont_size-(ncont-1)*cont_dist)/2)

        # draw the cont row
        xcont_beg = xdiff_beg+cont_Activ_overRec
        ycont_beg = ydiff_beg+cont_Activ_overRec
        ycont_cnt = ycont_beg+diffoffset+diff_cont_offset
        xcont_end = xcont_beg+cont_size

        # draw contacts
        # LI and Metall
        diff_width = - (xcont_beg-cont_Activ_overRec) + xcont_end+cont_Activ_overRec
        diff_height = - ydiff_beg + ydiff_end+diffoffset*2
        contactArray(self, 0, locint_layer, xcont_beg, ydiff_beg, xcont_end, ydiff_end+diffoffset*2, 0, cont_Activ_overRec, cont_size, cont_dist)
        if self.s_d_mlayer != 'M1':
            metal = self.s_d_mlayer.replace('M', 'Metal')
            metal = metal.replace('T', 'Top')
            via_offset = GridFix(diff_height/2)
            self.genVia(0, self.w*1e6/self.ng, diff_width / 2,via_offset,'Metal1', metal, True)
        # 30.01.08 GGa added block
        # draw Metal rect
        # calculate bot and top cont position
        yMet1 = ycont_cnt-endcap
        yMet2 = ycont_cnt+cont_size+(ncont-1)*distc +endcap
        # is metal1 overlapping Activ?
        yMet1 = min(yMet1, ydiff_beg+diffoffset)
        yMet2 = max(yMet2, ydiff_end+diffoffset)

        dbCreateRect(self, metall_layer, Box(xcont_beg-cont_metall_over, yMet1, xcont_end+cont_metall_over, yMet2))
        pinname = 'Sx'+ start_x.__str__() if start_x != 0 else 'S'
        pinname = pinname + start_y.__str__() if start_y != 0 else pinname
        if w > contActMin :
            MkPin(self, pinname, 3, Box(xcont_beg-cont_metall_over, yMet1, xcont_end+cont_metall_over, yMet2), metall_layer_pin)
        else :
            MkPin(self, pinname, 3, Box(xcont_beg-cont_metall_over, yMet1, xcont_end+cont_metall_over, yMet2), metall_layer_pin)

        dbCreateRect(self, pdiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))

        for i in range(1, int(ng)+1) :
            # draw the poly line
            xpoly_beg = xcont_end+gatpoly_cont_dist
            ypoly_beg = ydiff_beg-gatpoly_Activ_over
            xpoly_end = xpoly_beg+l
            ypoly_end = ydiff_end+gatpoly_Activ_over
             
            gate_offset = 0
            ## Drow gate contacts
            if self.gate_connection != 'none':
                metal_layer = self.gate_metal.replace('M', 'Metal')
                metal_layer = metal_layer.replace('T','Top')
                additional_offset = 0.065 if self.l < 0.5e-6 else 0
                gate_offset = additional_offset - 0.035 if additional_offset > 0 else 0
                ### Bottom contacts
                if 'B' in self.gate_connection:
                    self.genVia(self.l*1e6, 0, GridFix(l/2+xpoly_beg), GridFix(-cont_dist_act - cont_size/2 - additional_offset), 'GatPoly', metal_layer, True)
                ### Top contacts
                if 'T' in self.gate_connection:
                    top_distace  = max(ycont_beg+cont_size+cont_Activ_overRec, ydiff_end)
                    self.genVia(self.l*1e6, 0, GridFix(l/2+xpoly_beg), GridFix(top_distace + cont_dist_act + cont_size/2  + additional_offset), 'GatPoly', metal_layer, True)
                    
            ## Drow gate poly
            dbCreateRect(self, poly_layer, Box(xpoly_beg, ypoly_beg+diffoffset - gate_offset, xpoly_end, ypoly_end+diffoffset + gate_offset))

            ihpAddThermalMosLayer(self, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end, ypoly_end+diffoffset), True, 'pmos')

            if i == 1 :
                dbCreateLabel(self, text_layer, Point((xpoly_beg+xpoly_end)/2, (ypoly_beg+ypoly_end)/2+diffoffset), 'pmosHV', 'centerCenter', 'R90', Font.EURO_STYLE, 0.1)

            if onep(i) :
                pinname = 'Gx'+ start_x.__str__() if start_x != 0 else 'G'
                pinname = pinname + start_y.__str__() if start_y != 0 else pinname
                MkPin(self, pinname, 2, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end, ypoly_end+diffoffset), poly_layer_pin)

            # draw the second cont row
            xcont_beg = xpoly_end+gatpoly_cont_dist
            ycont_beg = ydiff_beg+cont_Activ_overRec
            ycont_cnt = ycont_beg+diffoffset+diff_cont_offset
            xcont_end = xcont_beg+cont_size

            dbCreateRect(self, metall_layer, Box(xcont_beg-cont_metall_over, yMet1, xcont_end+cont_metall_over, yMet2))
            # draw contacts
            # LI and Metall
            diff_width =  (xcont_beg-cont_Activ_overRec) + xcont_end+cont_Activ_overRec
            diff_height = - ydiff_beg + ydiff_end+diffoffset*2
            contactArray(self, 0, locint_layer, xcont_beg, ydiff_beg, xcont_end, ydiff_end+diffoffset*2, 0, cont_Activ_overRec, cont_size, cont_dist)
            if self.s_d_mlayer != 'M1':
                metal = self.s_d_mlayer.replace('M', 'Metal')
                metal = metal.replace('T', 'Top')
                via_offset = GridFix(diff_height/2)
                self.genVia(0, self.w*1e6/self.ng, diff_width / 2,via_offset,'Metal1',  metal, True)
            
            if onep(i) :
                pinname = 'Dx'+ start_x.__str__() if start_x != 0 else 'D'
                pinname = pinname + start_y.__str__() if start_y != 0 else pinname
                if w > contActMin :
                    MkPin(self, pinname, 1, Box(xcont_beg-cont_metall_over, yMet1, xcont_end+cont_metall_over, yMet2), metall_layer_pin)
                else :
                    MkPin(self, pinname, 1, Box(xcont_beg-cont_metall_over, yMet1, xcont_end+cont_metall_over, yMet2), metall_layer_pin)


            dbCreateRect(self, pdiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))
        # for i 1 ng

        # now finish drawing the diffusion
        xdiff_end = xcont_end+cont_Activ_overRec
        
        dbCreateRect(self, pdiff_layer,  Box(xdiff_beg, ydiff_beg+diffoffset, xdiff_end, ydiff_end+diffoffset))
        dbCreateRect(self, pdiffx_layer, Box(xdiff_beg-psd_pActiv_over, ypoly_beg-psd_PFET_over+gatpoly_Activ_over+diffoffset, xdiff_end+psd_pActiv_over, ypoly_end+psd_PFET_over-gatpoly_Activ_over+diffoffset))
        
        # draw minimum nWell
        nwell_offset = max(0, GridFix((contActMin-w)/2+0.5*self.grid))
        dbCreateRect(self, well_layer, Box(xdiff_beg-nwell_pActiv_over, ydiff_beg-nwell_pActiv_over+diffoffset-nwell_offset,
                                           xdiff_end+nwell_pActiv_over, ydiff_end+nwell_pActiv_over+diffoffset+nwell_offset))

        # B-Pin
        pinname = 'Bx'+ start_x.__str__() if start_x != 0 else 'B'
        pinname = pinname + start_y.__str__() if start_y != 0 else pinname
        #MkPin(self, pinname, 4, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec), Layer('Substrate', 'drawing'))

        # draw Thick Gate Oxide
        
        # first get standard values
        x1 = xdiff_beg-thGateOxAct
        x2 = xdiff_end+thGateOxAct
        y1 = ydiff_beg-gatpoly_Activ_over-thGateOxGat
        y2 = ydiff_end+gatpoly_Activ_over+thGateOxGat
        # now check, if NWell is drawn bigger
        if nwell_pActiv_over > thGateOxAct :
            x1 = xdiff_beg-nwell_pActiv_over
            x2 = xdiff_end+nwell_pActiv_over
        if (nwell_pActiv_over+diffoffset-nwell_offset) > (gatpoly_Activ_over-thGateOxGat) :
            y1 = ydiff_beg-nwell_pActiv_over+diffoffset-nwell_offset
            y2 = ydiff_end+nwell_pActiv_over+diffoffset+nwell_offset
        
        dbCreateRect(self, tgo_layer, Box(x1, y1, x2, y2))