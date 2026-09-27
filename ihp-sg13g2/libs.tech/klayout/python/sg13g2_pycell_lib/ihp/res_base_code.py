########################################################################
#
# Copyright 2025 IHP PDK Authors
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
from .utility_functions import *
from .device_base_code import *

from dataclasses import dataclass


@dataclass
class ResistorInfo:
    plus_pin_box: Box
    minus_pin_box: Box


class ResistorBase(DeviceBase):        
    @classmethod
    def defineParamSpecs(cls, specs):
        # define parameters and default values
        techparams = specs.tech.getTechParams()
        
        SG13_TECHNOLOGY = techparams["techName"]
        suffix = ""
        if 'SG13G2' in SG13_TECHNOLOGY :
            suffix = 'G2' 
        if 'SG13G3' in SG13_TECHNOLOGY :
            suffix = 'G3'
        
        CDFVersion = techparams['CDFVersion']
        model      = techparams[cls.res_type + '_model']
        rspec      = techparams[cls.res_type + suffix + '_rspec']
        rkspec     = techparams[cls.res_type + '_rkspec']
        rzspec     = techparams[cls.res_type + '_rzspec']
        defL       = techparams[cls.res_type + '_defL']
        defW       = techparams[cls.res_type + '_defW']
        defB       = techparams[cls.res_type + '_defB']
        defPS      = techparams[cls.res_type + '_defPS']
        minL       = techparams[cls.res_type + '_minL']
        minW       = techparams[cls.res_type + '_minW']
        minPS      = techparams[cls.res_type + '_minPS']
        eps        = techparams['epsilon2']
        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())
        #specs('Display', 'Selected', 'Display', ChoiceConstraint(['All', 'Selected']))
        #specs('Calculate', 'l', 'Calculate', ChoiceConstraint(['R', 'w', 'l']))
        #specs('Recommendation', 'No', 'Recommendation', ChoiceConstraint(['Yes', 'No']))
        specs('model', model, 'Model name', ReadOnlyConstraint())
        resistance = CbResCalc('R', 0, defL, defW, defB, defPS, cls.res_type)
        
        
        specs('w',  defW, 'Width')
        specs('l',  defL, 'Length')
        specs('b',  defB, 'Bends')
        specs('ps', defPS, 'Poly Space')
        specs('PWB', 'No', 'PWell Blockage', ChoiceConstraint(['Yes', 'No']))
        
        ## ----------------------------
        
        specs('UseContBar', True, 'Use Contact Bar')
        specs("ConnectionsMetal", 'M2', 'Connections metal' ,ChoiceConstraint(['M1', 'M2', 'M3', 'M4', 'TM1']))
        specs('NumberOfSegments', 1, 'Number of Segments')
        specs('SegmentConnection', 'Serial', 'Segment Connection', ChoiceConstraint(['None', 'Serial', 'Parallel']))
        specs('SegmentSpacing', '2u', 'Segment Spacing')
        
        ## -----------------------------
        super().defineParamSpecs(specs)
        imax = CbResCurrent(Numeric(defW), eps, cls.res_type+suffix)
        specs('R', eng_string(resistance), 'R', ReadOnlyConstraint())
        specs('Imax', imax, 'Imax', ReadOnlyConstraint())
        specs('bn', 'sub!', 'Bulk node connection', ReadOnlyConstraint())
        specs('Wmin', minW, 'Wmin', ReadOnlyConstraint())
        specs('Lmin', minL, 'Lmin', ReadOnlyConstraint())
        specs('PSmin', minPS, 'PSmin', ReadOnlyConstraint())
        specs('Rspec', rspec, 'Rspec [Ohm/sq]', ReadOnlyConstraint())
        specs('Rkspec', rkspec, 'Rkspec [Ohm/cont]', ReadOnlyConstraint())
        specs('Rzspec', rzspec, 'Rzspec [Ohm*m]', ReadOnlyConstraint())
        specs('tc1', '170e-6', 'Temperature coefficient 1', ReadOnlyConstraint())
        specs('tc2', '0.4e-6', 'Temperature coefficient 2', ReadOnlyConstraint())
        specs('m', '1', 'Multiplier', ReadOnlyConstraint())
        specs('trise', '0.0', 'Temp rise from ambient', ReadOnlyConstraint())

    def setupParams(self, params):
        # process parameter values entered by user
        self.params = params
        self.number_of_segments = int(params['NumberOfSegments'])
        self.segment_connection = params['SegmentConnection']
        self.segment_spacing = Numeric(params['SegmentSpacing'])*1e6
        self.connections_metal = params['ConnectionsMetal']
        self.use_cont_bar = params['UseContBar']
        self.connections_metal = params['ConnectionsMetal']
        super().setupParams(params)

    @abstractmethod
    def genSingleResistorLayout(self, index: int, x_offset: float) -> ResistorInfo:
        raise NotImplementedError('subclasses must overwrite the method genSingleResistorLayout()')

    def genDeviceLayout(self):
        met1_drw = Layer('Metal1', 'drawing')

        x_offset = 0.0
        previous_res_info = None
        for i in range(0, self.number_of_segments):
            res_info = self.genSingleResistorLayout(index=i, x_offset=x_offset)

            if previous_res_info is not None:
                match self.segment_connection:
                    case 'Serial':
                        box1: Box
                        box2: Box
                        if i % 2 == 0:
                            # horizontal connection near top, PLUS
                            box1 = previous_res_info.plus_pin_box
                            box2 = res_info.plus_pin_box
                        else:
                            # horizontal connection near bottom, MINUS
                            box1 = previous_res_info.minus_pin_box
                            box2 = res_info.minus_pin_box
                        dbCreateRect(self, met1_drw, Box(box1.left, box1.bottom, box2.right, box2.top))
                    case 'Parallel':
                        box1 = previous_res_info.plus_pin_box
                        box2 = res_info.plus_pin_box
                        dbCreateRect(self, met1_drw, Box(box1.left, box1.bottom, box2.right, box2.top))
                        box1 = previous_res_info.minus_pin_box
                        box2 = res_info.minus_pin_box
                        dbCreateRect(self, met1_drw, Box(box1.left, box1.bottom, box2.right, box2.top))
            x_offset += self.segment_spacing
            previous_res_info = res_info

