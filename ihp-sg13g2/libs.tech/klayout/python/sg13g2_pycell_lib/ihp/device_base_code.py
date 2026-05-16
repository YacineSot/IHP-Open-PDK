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

########################################################################
__version__ = '$Revision: #3 $'

import pya

import cni.rect
import cni.text
from cni.dlo import *
from .geometry import *
from .guard_ring_code import generate_guard_ring, GuardRingType, GuardRingShape
from .utility_functions import *


class DeviceBase(DloGen):
    @classmethod
    def defineParamSpecs(cls, specs):
        choices = [c.value for c in cls.validGuardRingTypes()]
        specs('guardRingType', 'none', 'Guard Ring Type', ChoiceConstraint(choices))
        specs('guardRingDistance', '1u', 'Guard Ring Distance')
        specs('guardRingShape', 'o', 'Guard Ring Shape', ChoiceConstraint(GuardRingShape.case_values()))

    def setupParams(self, params):
        # process parameter values entered by user
        self.guardRingType     = GuardRingType(params['guardRingType'])
        self.guardRingDistance = Numeric(params['guardRingDistance'])*1e6
        self.guardRingShape = GuardRingShape(params['guardRingShape'])

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

    def genLayout(self):
        self.genDeviceLayout()
        if self.guardRingType != GuardRingType.NONE:
            min_left = INT_MAX
            min_bottom = INT_MAX
            max_right = INT_MIN
            max_top = INT_MIN

            for s in self.getShapes():
                if isinstance(s, cni.text.Text):
                    continue
                bbox = s.bbox
                
                print(f"The box object is: {s.box}")
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
                                y_center=y_center)
