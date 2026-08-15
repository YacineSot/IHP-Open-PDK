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
import pya

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
        Mn_size    = techparams['Mn_a']
        Mn_space   = techparams['Mn_b']

        cls.add_separation(cls,specs, 'Version & model name readonly')
        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())
        #specs('Display', 'Selected', 'Display', ChoiceConstraint(['All', 'Selected']))
        specs('model', model, 'Model name', ReadOnlyConstraint())

        cls.add_separation(cls, specs, 'Device Sizing')
        specs('w' ,   defW, 'Width')
        specs('cnt_w_ratio', 100, 'Contact width ratio %', RangeConstraint(1, 100))
        specs('l' ,   defL, 'Length')
        specs('gate_cnt_ratio', 100, 'Gate Length contact ratio %', RangeConstraint(1, 100))
        specs('ng',   defNG, 'Number of Gates')
        specs('split_width', True, 'Split the width over the number of gate', BooleanConstraint())
        specs('connect_diffusions', True, 'Auto connect S/D diffusions', BooleanConstraint())
        specs('connect_gates', True, 'Auto connect gates', BooleanConstraint())
        specs('connect_gates_use_poly', True, 'Connect gates using poly', BooleanConstraint())
        specs('connection_width', f'{Mn_size}u', 'Connection Width')
        specs('connection_spacing', f'{Mn_space}u', 'Connection Spacing')
        specs('odd_vertical', True, 'Vertical metals odd', BooleanConstraint())

        cls.add_separation(cls, specs, 'Contacts settings')
        specs('s_d_mlayer', 'M2', 'S/D Metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        specs('gate_connection', 'T-B', 'Gate contact position', ChoiceConstraint(['T-B', 'T', 'B', 'none']))
        specs('gate_metal', 'M2', 'Gate contact metal layer', ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        specs('use_poly_pin', False, 'Create poly pin', BooleanConstraint())
        
        cls.add_separation(cls, specs, 'Dummies settings')
        specs('dummies_count', '0', 'Dummies Count')
        specs('dummies_l', defL, 'Dummies Length')
        specs('dummy_core_spacing', '0.3u', 'Dummy-Core Spacing')
        specs('dummies_inner_spacing', '-0.3u', 'Dummies Inner Spacing')
        specs('dummies_left', True, 'Place Dummies on the left', BooleanConstraint())
        specs('overlap_left', True, 'Overlap left dummiy with diffusion', BooleanConstraint())
        specs('dummies_right', True, 'Place Dummies on the right', BooleanConstraint())
        specs('overlap_right', True, 'Overlap right dummiy with diffusion', BooleanConstraint())
        
        super().defineParamSpecs(specs)
        
        specs('minW', minW, 'Minimum Width', ReadOnlyConstraint())
        specs('minL', minL, 'Minimum Length', ReadOnlyConstraint())

    def setupParams(self, params):
        # params = self.fix_params_micro_unit(
        #     params=params,
        #     keys=[
        #         'w',
        #         'l',
        #         'dummies_l',
        #         'dummy_core_spacing',
        #         'dummies_inner_spacing'
        #     ]
        # )
        self.params = params
        self.s_d_mlayer = params['s_d_mlayer']
        self.gate_connection = params['gate_connection']
        self.gate_metal = params['gate_metal']
        
        self.w = Numeric(params['w'])*1e6
        self.l = Numeric(params['l'])*1e6
        self.ng = int(params['ng'])
        self.split_width = params['split_width'] if 'split_width' in params else False
        self.connect_diffusions = params['connect_diffusions'] if 'connect_diffusions' in params else False
        self.connection_width = Numeric(params['connection_width'])*1e6 if 'connection_width' in params else 0.21
        self.connection_spacing = Numeric(params['connection_spacing'])*1e6 if 'connection_spacing' in params else 0.24
        self.connect_gates = params['connect_gates'] if 'connect_gates' in params else False
        self.connect_gates_use_poly = params['connect_gates_use_poly'] if 'connect_gates_use_poly' in params else False
        
        self.cnt_w_ratio = int(params['cnt_w_ratio'])
        self.gate_cnt_ratio = int(params['gate_cnt_ratio'])
        self.cnt_w_ratio = max(1, min(100, self.cnt_w_ratio))/100
        self.gate_cnt_ratio = max(1, min(100, self.gate_cnt_ratio))/100
        self.use_poly_pin = params['use_poly_pin'] if hasattr(params, 'use_poly_pin') else False
        
        if 'dummies_count' in params:
            self.dummies_count = int(params['dummies_count'])
            self.dummies_l = Numeric(params['dummies_l'])
            self.dummy_core_spacing = Numeric(params['dummy_core_spacing'])*1e6
            self.dummies_inner_spacing = Numeric(params['dummies_inner_spacing'])*1e6
            self.dummies_left = params['dummies_left']
            self.dummies_right = params['dummies_right']
            self.overlap_left = params['overlap_left']
            self.overlap_right = params['overlap_right']
        else:
            self.dummies_count = 0

        super().setupParams(params)
        self.vertical_layers = self.odd_layers if 'odd_vertical' in params and params['odd_vertical'] else self.even_layers
        self.horizontal_layers = self.even_layers if 'odd_vertical' in params and params['odd_vertical'] else self.odd_layers

    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return cls.allowed_guard_ring_types

    @staticmethod
    def get_dimensions(w, l, ng, techparams, gate_connection='T-B', dummies_params={'count': 0}):
        """
        Returns the (width, height) of the device.
        width: from the beginning to the end of the Activ (diffusion) horizontally.
        height: from the beginning to the end of the GatPoly vertically.
        """
        w_val = Numeric(w)
        l_val = Numeric(l)
            
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
        gatpoly_cont_enc = techparams['Cnt_d']
        
        gate_offset = 0
        if gate_connection != 'none':
            additional_offset = 0.065 if l_fixed < 0.5 else 0
            gate_offset = additional_offset - 0.035 if additional_offset > 0 else 0
        poly_height = cont_size + 2*gatpoly_cont_enc
        via_height = 0
        if 'T' in gate_connection:
            via_height += poly_height
        if 'B' in gate_connection:
            via_height += poly_height
            
        height = w_finger + (2 * gate_offset) + via_height
        
        dummies_count = dummies_params['count']
        if dummies_count > 0:
            (dummy_width, _ ) = mos_base.get_dimensions(
                w,
                dummies_params['l']*1e6,
                1,
                techparams,
                'T-B'
            )
            additional_width = dummy_width*dummies_count + dummies_params['core_spacing']*1e6 + dummies_params['inner_spacing']*1e6*(dummies_count - 1)
            if dummies_params['left']:
                width += additional_width
            if dummies_params['right']:
                width += additional_width
        print(f'device dimensions: (width, height): ({width}, {height})')
        return width, height

    def get_self_dimensions(self):
        return self.get_dimensions(
            w=self.w,
            l=self.l,
            ng=self.ng,
            techparams=self.tech.getTechParams(),
            gate_connection=self.gate_connection
        )

    def genDeviceLayout(self):
        self.grid = self.tech.getGridResolution()
        self.techparams = self.tech.getTechParams()
        self.epsilon = self.techparams['epsilon1']

        # Ensure w and l are in um (pmos approach)
        # Protection from huge size
        if self.w > 200:
            print('Warning: detecting big device, dividing it by 1e6')
            self.w *= 1e-6
            self.l *= 1e-6
        w = self.w
        l = self.l
        
            
        ng = self.ng
        
        start_x = self.sx if hasattr(self, 'sx') and self.sx is not None else 0
        start_y = self.sy if hasattr(self, 'sy') and self.sy is not None else 0
        self.use_poly_pin = False if not hasattr(self, 'use_poly_pin') else self.use_poly_pin

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
        metal2_layer = Layer('Metal2', 'drawing')   # 8
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
        w = w/ng if self.split_width else w
        w = GridFix(w)
        l = GridFix(l)
        cnt_ratio = self.cnt_w_ratio
        gate_cnt_ratio = self.gate_cnt_ratio
        sources = [] # to save the different source contacts for a multi-finger device
        drains = [] # to save the different drain contacts for a multi-finger device
        gates = [] # to save the different gate boxes for a multi-finger device
        gates_t = [] #to save the different top gate_contacts
        gates_b = [] # to save the different bottom gate_contacts

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
        sources.append(cnt_box)
        
        # draw contacts
        contactArray(self, 0, locint_layer, xcont_beg, ydiff_beg + ratio_offset, xcont_end, ydiff_end+diffoffset*2 - ratio_offset, 0, cont_Activ_overRec, cont_size, cont_dist)
        if self.s_d_mlayer != 'M1':
            metal = self.s_d_mlayer.replace('M', 'Metal')
            metal = metal.replace('T', 'Top')
            self.genVia(0, w*cnt_ratio, GridFix (cnt_box.getCenter().x), GridFix (cnt_box.getCenter().y),'Metal1', metal, True)
            
        pinname = 'S'
        try:
            if self.use_poly_pin:
                MkPin(self, pinname, 3, cnt_box, metall_layer_pin)
        except: pass ##print(f"Pin {pinname} already exist")
        s_diff_box = Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec)
        if typ == 'N' :
            dbCreateRect(self, ndiff_layer, s_diff_box)
        else :  # typ == 'P'
            dbCreateRect(self, pdiff_layer, s_diff_box)

        for i in range(1, int(ng)+1) :
            # draw the poly line
            xpoly_beg = xcont_end+gatpoly_cont_dist
            ypoly_beg = ydiff_beg-gatpoly_Activ_over
            xpoly_end = xpoly_beg+l
            ypoly_end = ydiff_end+gatpoly_Activ_over
            
            gate_offset = 0.065 if l < 0.5 and self.gate_connection != 'none' else 0
            
            ## Drow gate poly        
            gate_box = Box(xpoly_beg, ypoly_beg+diffoffset-gate_offset, xpoly_end, ypoly_end+diffoffset+gate_offset)
            self.gate_box = gate_box
            gates.append(gate_box)
            dbCreateRect(self, poly_layer, gate_box)
            ## Drow gate contacts
            if self.gate_connection != 'none':
                metal_layer = self.gate_metal.replace('M', 'Metal').replace('T','Top')
                # additional_offset = 0.065 if l < 0.5 else 0
                # gate_offset = additional_offset - 0.035 if additional_offset > 0 else 0
                gate_cnt_width = GridFix(l*gate_cnt_ratio)
                ### Bottom contacts
                if 'B' in self.gate_connection:
                    # self.genVia(gate_cnt_width, 0, GridFix(l/2+xpoly_beg), GridFix(-cont_dist_act - cont_size/2 - additional_offset), 'GatPoly', metal_layer, True)
                    gate_cnt_box = self.genVia(gate_cnt_width, 0, GridFix(gate_box.box.center().x), GridFix(gate_box.box.bottom), 'GatPoly', metal_layer, True, 'centerTop')
                    self.gate_box_b = gate_cnt_box
                    gates_b.append(gate_cnt_box)
                    
                ### Top contacts
                if 'T' in self.gate_connection:
                    # top_distace  = max(ycont_beg+cont_size+cont_Activ_overRec, ydiff_end)
                    # self.genVia(gate_cnt_width, 0, GridFix(l/2+xpoly_beg), GridFix(top_distace + cont_dist_act + cont_size/2  + additional_offset), 'GatPoly', metal_layer, True)
                    gate_cnt_box = self.genVia(gate_cnt_width, 0, GridFix(gate_box.box.center().x), GridFix(gate_box.box.top), 'GatPoly', metal_layer, True, 'centerBottom')
                    self.gate_box_t = gate_cnt_box
                    gates_t.append(gate_cnt_box)
            
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
                    if self.use_poly_pin:
                        # pmos uses poly_layer for pin
                        # pmosHV uses poly_layer_pin for pin
                        MkPin(self, pinname, 2, Box(xpoly_beg, ypoly_beg+diffoffset, xpoly_end, ypoly_end+diffoffset), poly_layer_pin)
                except: pass ##print(f'Pinname {pinname} already exists')

            # draw the second cont row
            xcont_beg = xpoly_end+gatpoly_cont_dist
            ycont_beg = ydiff_beg+cont_Activ_overRec
            ycont_cnt = ycont_beg+diffoffset+diff_cont_offset
            xcont_end = xcont_beg+cont_size

            cnt_box = Box(xcont_beg-cont_metall_over, yMet1 + ratio_offset, xcont_end+cont_metall_over, yMet2 - ratio_offset)
            dbCreateRect(self, metall_layer, cnt_box)
            self.drain_box = cnt_box
            if i%2 != 0:
                drains.append(cnt_box)
            else: sources.append(cnt_box)
            
            contactArray(self, 0, locint_layer, xcont_beg, ydiff_beg + ratio_offset, xcont_end, ydiff_end+diffoffset*2 - ratio_offset, 0, cont_Activ_overRec, cont_size, cont_dist)
            if self.s_d_mlayer != 'M1':
                metal = self.s_d_mlayer.replace('M', 'Metal').replace('T', 'Top')
                self.genVia(0, w*cnt_ratio, GridFix (cnt_box.getCenter().x), GridFix (cnt_box.getCenter().y),'Metal1',  metal, True)
            
            if onep(i) :
                pinname = 'D'
                try:
                    if self.use_poly_pin:
                        MkPin(self, pinname, 1, cnt_box, metall_layer_pin)
                except: pass ## print(f"Pinname {pinname} already exists")

            if typ == 'N' :
                dbCreateRect(self, ndiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))
            else :
                dbCreateRect(self, pdiff_layer, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec))

        # now finish drawing the diffusion
        xdiff_end = xcont_end+cont_Activ_overRec
        diff_box = Box(xdiff_beg, ydiff_beg+diffoffset, xdiff_end, ydiff_end+diffoffset)
        if typ == 'N' :
            dbCreateRect(self, ndiff_layer, diff_box)
        else :
            dbCreateRect(self, pdiff_layer,  diff_box)
            dbCreateRect(self, pdiffx_layer, Box(xdiff_beg-psd_pActiv_over, ypoly_beg-psd_PFET_over+gatpoly_Activ_over+diffoffset, xdiff_end+psd_pActiv_over, ypoly_end+psd_PFET_over-gatpoly_Activ_over+diffoffset))
            # draw minimum nWell
            nwell_offset = max(0, GridFix((contActMin-w)/2+0.5*self.grid))
            dbCreateRect(self, well_layer, Box(xdiff_beg-nwell_pActiv_over, ydiff_beg-nwell_pActiv_over+diffoffset-nwell_offset, xdiff_end+nwell_pActiv_over, ydiff_end+nwell_pActiv_over+diffoffset+nwell_offset))

        # B-Pin
        pinname = 'B'
        try:
            MkPin(self, pinname, 4, Box(xcont_beg-cont_Activ_overRec, ycont_beg-cont_Activ_overRec, xcont_end+cont_Activ_overRec, ycont_beg+cont_size+cont_Activ_overRec), Layer('Substrate', 'drawing'))
        except: pass #print(f'Pinname {pinname} already exists')

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
        
        ## Connecting Sources/Drains
        if ng > 1:
            if self.connect_diffusions:
                top = self.gate_box_t.top if self.gate_box_t else self.gate_box.top
                top += self.connection_spacing
                s_left = sources[0].left
                s_right = sources[-1].right
                d_left = drains[0].left
                d_right = drains[-1].right
                sources_connection_box = Box(s_left, top, s_right, top+self.connection_width)
                drains_connection_box = Box(d_left, top+self.connection_width+self.connection_spacing, d_right,top+2*self.connection_width+self.connection_spacing )
                self.draw_rect(self.horizontal_layers[0], sources_connection_box, "Source")
                self.draw_rect(self.horizontal_layers[0], drains_connection_box, "Drain")
                for drain in drains:
                    con_box = Box(drain.left, drain.bottom, drain.right, drains_connection_box.top)
                    self.draw_rect(self.vertical_layers[0], con_box, "Drain")
                    self.connectBoxes(con_box, drains_connection_box, self.horizontal_layers[0]._name, self.vertical_layers[0]._name)
                for source in sources:
                    con_box = Box(source.left, source.bottom, source.right, sources_connection_box.top)
                    self.draw_rect(self.vertical_layers[0], con_box, "Source")
                    self.connectBoxes(con_box, sources_connection_box, self.horizontal_layers[0]._name, self.vertical_layers[0]._name)
            
            if self.connect_gates:
                con_layer = poly_layer if self.connect_gates_use_poly else self.horizontal_layers[0]
                if gates_t:
                    gate_con_box = Box(gates_t[0].left, gates_t[0].bottom, gates_t[-1].right, gates_t[-1].top)
                    self.draw_rect(con_layer, gate_con_box, "Gate")
                if gates_b:
                    gate_con_box = Box(gates_b[0].left, gates_b[0].bottom, gates_b[-1].right, gates_b[-1].top)
                    self.draw_rect(con_layer, gate_con_box, "Gate")
        
        ## Placing dummies beside the generated device
        if self.dummies_count > 0:
            params = {
                'l': self.dummies_l, #Updating the new device lenght into the dummy length
                'w': w*1e-6,
                'ng': 1,
                'gate_connection': 'T-B',
                's_d_mlayer': 'M1',
                'gate_metal': 'M1',
                'cnt_w_ratio': self.cnt_w_ratio*100,
                'gate_cnt_ratio': 100,
                'use_poly_pin': False
            }
            (width, _) = mos_base.get_dimensions(
                    w=params['w']*1e6, 
                    l=params['l']*1e6, 
                    ng=params['ng'],
                    techparams= self.techparams,
                    gate_connection = params['gate_connection']
                )
            if self.dummies_left:
                left_spacing = self.dummy_core_spacing if not self.overlap_left else -0.3
                for i in range(self.dummies_count):
                    x_pos = diff_box.left - left_spacing - i*(self.dummies_inner_spacing) - (i+1)*width
                    self.instanciate_self(params, pya.DPoint(x_pos, self.sy))
            if self.dummies_right:
                right_spacing = self.dummy_core_spacing if not self.overlap_right else -0.3
                for i in range(self.dummies_count):
                    x_pos = diff_box.right + i*(self.dummies_inner_spacing) + (i)*width  + right_spacing
                    self.instanciate_self(params, pya.DPoint(x_pos, self.sy))
                        
        
        return self._getCurrentCellContext()
