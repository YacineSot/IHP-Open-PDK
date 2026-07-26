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
from .device_base_code import DeviceBase
from .geometry import *
from .guard_ring_code import GuardRingType
from .thermal import *
from .utility_functions import *

import math

class mos_base(DeviceBase):
    """
    Base class for MOS devices (nmos, pmos, nmosHV, pmosHV).
    Inherit this class and set the class attributes to configure the specific device.
    """

    # Class attributes to be overridden by subclasses
    model_name = ''
    model_type = ''
    
    default_ring = 'none'
    default_distance = '0.57u'
    allowed_guard_ring_types = [GuardRingType.NONE]
    
    typ = 'N'  # 'N' or 'P'
    hv = False # True or False

    @classmethod
    def defineParamSpecs(cls, specs):
        techparams = specs.tech.getTechParams()

        CDFVersion = techparams['CDFVersion']
        model      = cls.model_name
        defL       = techparams[cls.model_type+'_defL']
        defW       = techparams[cls.model_type+'_defW']
        defNG      = techparams[cls.model_type+'_defNG']
        minL       = techparams[cls.model_type+ '_minL']
        minW       = techparams[cls.model_type+ '_minW']

        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())
        #specs('Display', 'Selected', 'Display', ChoiceConstraint(['All', 'Selected']))
        specs('model', model, 'Model name', ReadOnlyConstraint())

        specs('w' ,   defW, 'Width')
        specs('cnt_w_ratio', 100, 'Contact width ratio %', RangeConstraint(1, 100))
        specs('l' ,   defL, 'Length')
        specs('gate_cnt_ratio', 100, 'Gate Length contact ratio %', RangeConstraint(1, 100))
        specs('ng',   defNG, 'Number of Gates')

        specs('s_d_mlayer', 'M2', 'S/D Metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        specs('gate_connection', 'T-B', 'Gate contact position', ChoiceConstraint(['T-B', 'T', 'B', 'none']))
        specs('gate_metal', 'M2', 'Gate contact metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        
        super().defineParamSpecs(specs)
        
        specs('minW', minW, 'Minimum Width', ReadOnlyConstraint())
        specs('minL', minL, 'Minimum Length', ReadOnlyConstraint())

    def setupParams(self, params):
        self.params = params
        self.s_d_mlayer = params['s_d_mlayer']
        self.gate_connection = params['gate_connection']
        self.gate_metal = params['gate_metal']
        
        self.w = Numeric(params['w'])
        self.l = Numeric(params['l'])
        self.ng = Numeric(params['ng'])
        
        self.cnt_w_ratio = Numeric(params['cnt_w_ratio'])
        self.gate_cnt_ratio = Numeric(params['gate_cnt_ratio'])
        self.cnt_w_ratio = max(1, min(100, self.cnt_w_ratio))/100
        self.gate_cnt_ratio = max(1, min(100, self.gate_cnt_ratio))/100

        super().setupParams(params)

    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return cls.allowed_guard_ring_types

    @staticmethod
    def get_dimensions(w, l, ng, techparams, gate_connection='T-B'):
        """
        Returns the (width, height) of the device.
        width: from the beginning to the end of the Activ (diffusion) horizontally.
        height: from the beginning to the end of the GatPoly vertically.
        """
        w_val = Numeric(w)
        l_val = Numeric(l)
        if w_val < 1:
            w_val = w_val * 1e6
        if l_val < 1:
            l_val = l_val * 1e6
            
        epsilon = techparams['epsilon1']
        ng_int = math.floor(Numeric(ng) + epsilon)
        
        w_finger = GridFix(w_val / ng_int)
        l_fixed = GridFix(l_val)
        
        cont_size = techparams['Cnt_a']
        cont_Activ_overRec = techparams['Cnt_c']
        gatpoly_cont_dist = techparams['Cnt_f']
        smallw_gatpoly_cont_dist = cont_Activ_overRec + techparams['Gat_d']
        contActMin = 2 * cont_Activ_overRec + cont_size

        if w_finger < contActMin - epsilon:
            gatpoly_cont_dist = smallw_gatpoly_cont_dist
            
        # Horizontal width
        width = (ng_int * l_fixed) + ((ng_int + 1) * cont_size) + (2 * ng_int * gatpoly_cont_dist) + (2 * cont_Activ_overRec)
        
        # Vertical height
        gatpoly_Activ_over = techparams['Gat_c']
        gatpoly_Min_Width = techparams['Gat_a']
        
        gate_offset = 0
        if gate_connection != 'none':
            additional_offset = 0.065 if l_fixed < 0.5 else 0
            gate_offset = additional_offset - 0.035 if additional_offset > 0 else 0
        via_height = 0
        if 'T' in gate_connection:
            via_height += gatpoly_Min_Width + 2*gatpoly_Activ_over
        if 'B' in gate_connection:
            via_height += gatpoly_Min_Width + 2*gatpoly_Activ_over
            
        height = w_finger + (2 * gate_offset) + via_height
        
        return width, height

    def genDeviceLayout(self):
        self.grid = self.tech.getGridResolution()
        self.techparams = self.tech.getTechParams()
        self.epsilon = self.techparams['epsilon1']

        # Ensure w and l are in um (pmos approach)
        w = self.w
        l = self.l
        if w < 1:
            w = w * 1e6
        if l < 1:
            l = l * 1e6
            
        ng = self.ng
        
        start_x = self.sx if hasattr(self, 'sx') and self.sx is not None else 0
        start_y = self.sy if hasattr(self, 'sy') and self.sy is not None else 0

        typ = self.typ
        hv = self.hv
        Cell = self.__class__.__name__

        # *************************************************************************
        # *
        # * Cell Properties
        # *
        # ************************************************************************
        dbReplaceProp(self, 'ivCellType', 'graphic')
        dbReplaceProp(self, 'viewSubType', 'maskLayoutParamCell')
        dbReplaceProp(self, 'instNamePrefix', 'M')
        dbReplaceProp(self, 'function', 'transistor')
        dbReplaceProp(self, 'pcellVersion', '$Revision: 1.0 $')
        dbReplaceProp(self, 'pin#', 5)

        # *************************************************************************
        # *
        # * Layer Definitions
        # *
        # ************************************************************************
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
        text_layer = Layer('TEXT', 'drawing')       # 63

        # *************************************************************************
        # *
        # * Generic Design Rule Definitions
        # *
        # ************************************************************************
        endcap = self.techparams['M1_c1']
        cont_size = self.techparams['Cnt_a']
        cont_dist = self.techparams['Cnt_b']
        cont_dist_act = self.techparams['Cnt_e']
        cont_Activ_overRec = self.techparams['Cnt_c']
        cont_metall_over = self.techparams['M1_c']
        
        if typ == 'P':
            psd_pActiv_over = self.techparams['pSD_c']    # pSD enc. of p+-Activ in nwell
            nwell_pActiv_over = self.techparams['NW_c1'] if hv else self.techparams['NW_c']  # NWell enc. of pActiv
            psd_PFET_over = self.techparams['pSD_i1'] if hv else self.techparams['pSD_i']    # pSD enc. of Gate
            
        gatpoly_Activ_over = self.techparams['Gat_c']
        gatpoly_cont_dist = self.techparams['Cnt_f']
        smallw_gatpoly_cont_dist = cont_Activ_overRec+self.techparams['Gat_d']
        
        wmin = Numeric(self.techparams[self.model_type+'_minW'])
        lmin = Numeric(self.techparams[self.model_type+'_minL'])
        contActMin = 2*cont_Activ_overRec+cont_size
        thGateOxGat = self.techparams['TGO_c']
        thGateOxAct = self.techparams['TGO_a']

        ng = math.floor(Numeric(ng)+self.epsilon)
        w = w/ng
        w = GridFix(w)
        l = GridFix(l)
        cnt_ratio = self.cnt_w_ratio
        gate_cnt_ratio = self.gate_cnt_ratio

        # *************************************************************************
        # *
        # * Main body of code
        # *
        # ************************************************************************

        if endcap < cont_metall_over :
            endcap = cont_metall_over
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

        # draw Metal rect
        # calculate bot and top cont position
        yMet1 = ycont_cnt-endcap
        yMet2 = ycont_cnt+cont_size+(ncont-1)*distc +endcap
        # is metal1 overlapping Activ?
        yMet1 = min(yMet1, ydiff_beg+diffoffset)
        yMet2 = max(yMet2, ydiff_end+diffoffset)

        min_height = cont_size + 2 * endcap
        max_offset = ((yMet2 - yMet1) - min_height - cont_Activ_overRec) / 2
        ratio_offset = min((w - w * cnt_ratio) / 2, max_offset)
        ratio_offset = GridFix(max(0, ratio_offset))
        
        cnt_box = Box(xcont_beg-cont_metall_over, yMet1 + ratio_offset, xcont_end+cont_metall_over, yMet2 - ratio_offset)
        dbCreateRect(self, metall_layer, cnt_box)
        self.source_box = cnt_box
        
        # draw contacts
        contactArray(self, 0, locint_layer, xcont_beg, ydiff_beg + ratio_offset, xcont_end, ydiff_end+diffoffset*2 - ratio_offset, 0, cont_Activ_overRec, cont_size, cont_dist)
        if self.s_d_mlayer != 'M1':
            metal = self.s_d_mlayer.replace('M', 'Metal')
            metal = metal.replace('T', 'Top')
            self.genVia(0, w*cnt_ratio, GridFix (cnt_box.getCenter().x), GridFix (cnt_box.getCenter().y),'Metal1', metal, True)
            
        pinname = 'S'
        try:
            if typ == 'P':
                MkPin(self, pinname, 3, cnt_box, metall_layer)
            else:
                MkPin(self, pinname, 3, cnt_box, metall_layer_pin)
        except: print(f"Pin {pinname} already exist")

        if typ == 'N' :
            dbCreateRect(self, ndiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))
        else :  # typ == 'P'
            dbCreateRect(self, pdiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))

        for i in range(1, int(ng)+1) :
            # draw the poly line
            xpoly_beg = xcont_end+gatpoly_cont_dist
            ypoly_beg = ydiff_beg-gatpoly_Activ_over
            xpoly_end = xpoly_beg+l
            ypoly_end = ydiff_end+gatpoly_Activ_over
            
            gate_offset = 0.065 if l < 0.5 and self.gate_connection != 'none' else 0
            
            ## Drow gate poly        
            gate_box = Box(xpoly_beg, ypoly_beg+diffoffset-gate_offset, xpoly_end, ypoly_end+diffoffset+gate_offset)
            dbCreateRect(self, poly_layer, gate_box)
            self.gate_box = gate_box
            ## Drow gate contacts
            if self.gate_connection != 'none':
                metal_layer = self.gate_metal.replace('M', 'Metal').replace('T','Top')
                # additional_offset = 0.065 if l < 0.5 else 0
                # gate_offset = additional_offset - 0.035 if additional_offset > 0 else 0
                gate_cnt_width = GridFix(l*gate_cnt_ratio)
                ### Bottom contacts
                if 'B' in self.gate_connection:
                    # self.genVia(gate_cnt_width, 0, GridFix(l/2+xpoly_beg), GridFix(-cont_dist_act - cont_size/2 - additional_offset), 'GatPoly', metal_layer, True)
                    self.genVia(gate_cnt_width, 0, GridFix(gate_box.box.center().x), GridFix(gate_box.box.bottom), 'GatPoly', metal_layer, True, 'centerTop')
                ### Top contacts
                if 'T' in self.gate_connection:
                    # top_distace  = max(ycont_beg+cont_size+cont_Activ_overRec, ydiff_end)
                    # self.genVia(gate_cnt_width, 0, GridFix(l/2+xpoly_beg), GridFix(top_distace + cont_dist_act + cont_size/2  + additional_offset), 'GatPoly', metal_layer, True)
                    self.genVia(gate_cnt_width, 0, GridFix(gate_box.box.center().x), GridFix(gate_box.box.top), 'GatPoly', metal_layer, True, 'centerBottom')
            
            if typ == 'P' and not hv:
                ihpAddThermalMosLayer(self, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end + cont_size /2 , ypoly_end+diffoffset), True, 'pmos')
            elif typ == 'P' and hv:
                ihpAddThermalMosLayer(self, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end, ypoly_end+diffoffset), True, 'pmos')
            else:
                ihpAddThermalMosLayer(self, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end, ypoly_end+diffoffset), True, Cell)

            if i == 1 :
                label_text = self.model_type
                dbCreateLabel(self, text_layer, Point((xpoly_beg+xpoly_end)/2, (ypoly_beg+ypoly_end)/2+diffoffset), label_text, 'centerCenter', 'R90', Font.EURO_STYLE, 0.1)

            if onep(i) :
                pinname = 'G'
                try:
                    if typ == 'P':
                        # pmos uses poly_layer for pin
                        # pmosHV uses poly_layer_pin for pin
                        p_layer_pin = poly_layer_pin if hv else poly_layer
                        MkPin(self, pinname, 2, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end, ypoly_end+diffoffset), p_layer_pin)
                    else:
                        MkPin(self, pinname, 2, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end, ypoly_end+diffoffset), poly_layer_pin)
                except: print(f'Pinname {pinname} already exists')

            # draw the second cont row
            xcont_beg = xpoly_end+gatpoly_cont_dist
            ycont_beg = ydiff_beg+cont_Activ_overRec
            ycont_cnt = ycont_beg+diffoffset+diff_cont_offset
            xcont_end = xcont_beg+cont_size

            cnt_box = Box(xcont_beg-cont_metall_over, yMet1 + ratio_offset, xcont_end+cont_metall_over, yMet2 - ratio_offset)
            dbCreateRect(self, metall_layer, cnt_box)
            self.drain_box = cnt_box
            
            contactArray(self, 0, locint_layer, xcont_beg, ydiff_beg + ratio_offset, xcont_end, ydiff_end+diffoffset*2 - ratio_offset, 0, cont_Activ_overRec, cont_size, cont_dist)
            if self.s_d_mlayer != 'M1':
                metal = self.s_d_mlayer.replace('M', 'Metal').replace('T', 'Top')
                self.genVia(0, w*cnt_ratio, GridFix (cnt_box.getCenter().x), GridFix (cnt_box.getCenter().y),'Metal1',  metal, True)
            
            if onep(i) :
                pinname = 'D'
                try:
                    if typ == 'P':
                        MkPin(self, pinname, 1, cnt_box, metall_layer if not hv else metall_layer_pin)
                    else:
                        MkPin(self, pinname, 1, cnt_box, metall_layer_pin)
                except: print(f"Pinname {pinname} already exists")

            if typ == 'N' :
                dbCreateRect(self, ndiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))
            else :
                dbCreateRect(self, pdiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))

        # now finish drawing the diffusion
        xdiff_end = xcont_end+cont_Activ_overRec
        if typ == 'N' :
            dbCreateRect(self, ndiff_layer, Box(xdiff_beg, ydiff_beg+diffoffset, xdiff_end, ydiff_end+diffoffset))
        else :
            dbCreateRect(self, pdiff_layer,  Box(xdiff_beg, ydiff_beg+diffoffset, xdiff_end, ydiff_end+diffoffset))
            dbCreateRect(self, pdiffx_layer, Box(xdiff_beg-psd_pActiv_over, ypoly_beg-psd_PFET_over+gatpoly_Activ_over+diffoffset, xdiff_end+psd_pActiv_over, ypoly_end+psd_PFET_over-gatpoly_Activ_over+diffoffset))
            # draw minimum nWell
            nwell_offset = max(0, GridFix((contActMin-w)/2+0.5*self.grid))
            dbCreateRect(self, well_layer, Box(xdiff_beg-nwell_pActiv_over, ydiff_beg-nwell_pActiv_over+diffoffset-nwell_offset, xdiff_end+nwell_pActiv_over, ydiff_end+nwell_pActiv_over+diffoffset+nwell_offset))

        # B-Pin
        pinname = 'B'
        try:
            MkPin(self, pinname, 4, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec), Layer('Substrate', 'drawing'))
        except: print(f'Pinname {pinname} already exists')

        # draw Thick Gate Oxide
        if hv :
            if typ == 'P':
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
            else:
                dbCreateRect(self, tgo_layer,
                             Box(xdiff_beg - thGateOxAct, ydiff_beg - gatpoly_Activ_over - thGateOxGat,
                                 xdiff_end + thGateOxAct, ydiff_end + gatpoly_Activ_over + thGateOxGat))

        return self._getCurrentCellContext()
