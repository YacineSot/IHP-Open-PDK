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
from .guard_ring_code import GuardRingType, generate_guard_ring
from .geometry import *
from .nmos_code import nmos
from .pmos_code import pmos
from .device_base_code import DeviceBase
from .via_stack_code import via_stack
from .nmosHV_code import nmosHV
from .pmosHV_code import pmosHV
from .t_gate_base import t_gate_base
import pya


class t_gate(DloGen, t_gate_base):
    @classmethod
    def defineParamSpecs(cls, specs):
        techparams = specs.tech.getTechParams()
        cls.techparams = techparams

        CDFVersion = techparams['CDFVersion']

        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())
        specs('w' , '5u', 'PMOS Width')
        specs('l' ,   '3u', 'PMOS Length')
        specs('inverter_w' , '5u', 'Inverter PMOS Width')
        specs('inverter_l' ,   '3u', 'Inverter PMOS Length')
        specs('ng', '1', 'Number of fingers')
        specs('pmos_gate_ratio', '0.6', 'PMOS to NMOS T-Gate Width ratio NMOS/PMOS')
        specs('pmos_inv_ratio', '0.6', 'PMOS to NMOS Inverter Width ratio NMOS/PMOS')
        specs('high_voltage', False, 'High Voltage devices ?', BooleanConstraint())
        specs('vertical_spacing', '1u', 'Vertical spacing')
        specs('horizontal_spacing', '0.5u', 'Horizontal spacing')
        specs('tap_spacing', '0.5u', 'Tap spacing')
        specs('connection_metal_width', '0.5u', 'Connection metal width')
        specs('connection_metal_spacing', '0.5u', 'Connection metal spacing')
        
        

    def setupParams(self, params):
        # process parameter values entered by user
        self.w  = Numeric(params['w'])
        self.l  = Numeric(params['l'])
        self.inverter_w  = Numeric(params['inverter_w'])
        self.inverter_l  = Numeric(params['inverter_l'])
        self.ng = Numeric(params['ng'])
        self.pmos_gate_ratio = Numeric(params['pmos_gate_ratio'])
        self.pmos_inv_ratio = Numeric(params['pmos_inv_ratio'])
        self.set_devices('high_voltage' if params['high_voltage'] else 'low_voltage')
        self.vertical_spacing = Numeric(params['vertical_spacing'])*1e6
        self.horizontal_spacing = Numeric(params['horizontal_spacing'])*1e6
        self.connection_metal_width = Numeric(params['connection_metal_width'])*1e6
        self.connection_metal_spacing = Numeric(params['connection_metal_spacing'])*1e6
        self.tap_spacing = Numeric(params['tap_spacing'])*1e6
        self.tap_width = 0.3

    def set_devices(self, model_type):
        """
        Template method for subclasses to overwrite
        
        You need to set the pmos, nmos classes for the t-gate
        
        self.pmos = my_pmos_class
        self.nmos = my_nmos_class
        
        """
        if model_type == "high_voltage":
            self.pmos = pmosHV
            self.nmos = nmosHV
        else:
            self.pmos = pmos
            self.nmos = nmos
    
    def gen_mos(self, w, l, ng, gate_connection, device_model, x, y, device_name=""):
        """
        Template method for subclasses to overwrite
        
        w: width of the device
        l: length of the device
        ng: number of fingers
        gate_connection: gate connection position (T, B, T-B, none)
        device_model: device_model class
        x: x position of the device
        y: y position of the device
        device_name: name of the device (to display over the gate)
        
        return object: {gate: Box(), source_contact: Box(), drain_contact: Box(), gate_top_contact: Box(), gate_bottom_contact: Box()}
        
        """
        device = device_model()
        params = {'w': w, 
                    'l': l, 
                    'ng': 1, 
                    's_d_mlayer': "M1", 
                    'gate_connection': gate_connection,
                    'gate_metal': "M2", 
                    'cnt_w_ratio': 100,
                    'gate_cnt_ratio': 80,
                    'guardRingType': 'none',
                    'guardRingDistance': 0.5,
                }
        device.tech = self.tech
        device._getCurrentCellContext = self._getCurrentCellContext
        device.sx = x
        device.sy = y
        device.setupParams(params)
        device.genDeviceLayout()
        contacts = {
            'gate': device.gate_box.box,
            'source_contact': device.source_box.box,
            'drain_contact': device.drain_box.box,
            'gate_top_contact': device.gate_box_t.box if hasattr(device, 'gate_box_t') else None,
            'gate_bottom_contact': device.gate_box_b.box if hasattr(device, 'gate_box_b') else None
        }
        if device_name:
            self.draw_label(device.gate_box.box, device_name, "TEXT")
        return contacts

    def get_mos_dimensions(self, w, l, ng, gate_connection, device_model):
        """
        Template method for subclasses to overwrite
        
        w: width of the device
        l: length of the device
        ng: number of fingers
        gate_connection: gate connection position (T, B, T-B, none)
        device_model: device_model class
        
        return (sx, sy) : size of the device (active | gate)
        
        """
        dimensions = device_model.get_dimensions(w, l, ng, self.techparams, gate_connection)
        return {'Width': dimensions[0], 'Height': dimensions[1]}
    
    def gen_tap(self, w, l, x, y, tap_type, tap_name=""):
        """
        Template method for subclasses to overwrite
        
        w: width of the tap
        l: length of the tap
        x: x position of the tap
        y: y position of the tap
        tap_type: type of the tap (nwell, psub)
        tap_name: name of the tap (to display over the gate)
        """
        raise NotImplementedError()
    
    def draw_rect(self, box, layer, net_name=""):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to draw
        layer: layer of the rectangle (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        ihp_box = Box(0,0,0,0)
        ihp_box.box = box
        dbCreateRect(self, Layer(layer.replace("M", "Metal")), ihp_box)
        self.draw_label(box, net_name, layer) if net_name else None
        return box

    def draw_label(self, box, text, layer, size=0):
        """
        Template method for subclasses to overwrite
        
        box: DBox() object to draw the label
        text: text of the label
        layer: layer of the label (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Text()
        
        """
        box_center = box.center()
        point = Point(box_center.x, box_center.y)
        auto_size = min(box.width(), box.height())*0.5 if size == 0 else size
        auto_size = min(auto_size, 0.2)  # Limit the maximum size to 0.1
        rotation = 'R0' if box.width() >= box.height() else 'R90'
        dbCreateLabel(self, Layer(layer.replace("M", "Metal")), point, text, "centerCenter", rotation, Font.EURO_STYLE, auto_size)
    
    def gen_via(self, box, b_layer, t_layer, origin='centerCenter'):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to place the via
        b_layer: bottom layer of the via (e.g. "M1", "M2", "Poly", etc.)
        t_layer: top layer of the via (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        via_device = via_stack()
        b_layer = b_layer.replace("M", "Metal")
        t_layer = t_layer.replace("M", "Metal")
        params = {
            'vn_columns': 0,
            'vn_rows': 0,
            'vt1_columns': 0,
            'vt1_rows': 0,
            'vt2_columns': 0,
            'vt2_rows': 0,
            'b_layer': b_layer,
            't_layer': t_layer,
            'origin': origin,
            'extra_vias': 'no',
            'sx': box.center().x,
            'sy': box.center().y
        }
        via_device.tech = self.tech
        via_device._getCurrentCellContext = self._getCurrentCellContext
        via_device.setupParams(params)
        via_device.vn_total_width = box.width()
        via_device.vn_total_height = box.height()
        via_device.sx = box.center().x
        via_device.sy = box.center().y
        via_device.genLayout()
        return box

    def connect_boxes(self, box1, box2, b_layer, t_layer):
        """
        Template method for subclasses to overwrite
        
        box1: Box() object to connect
        box2: Box() object to connect
        b_layer: bottom layer of the connection (e.g. "M1", "M2", "Poly", etc.)
        t_layer: top layer of the connection (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        intersection_box = box1 & box2
        if intersection_box.area() == 0:
            return None
        
        print(f"Connecting boxes on layers {b_layer} and {t_layer} with intersection box: {intersection_box}")
        
        return self.gen_via(intersection_box, b_layer, t_layer)
        
    def gen_tap(self, box, tap_type, tap_shape, tap_name=""):
        """
        Template method for subclasses to overwrite
        
        box: Box() object representing the tap's bounding box
        tap_type: type of the tap (nwell, psub)
        tap_shape: shape of the tap (here we define the inluding sides nsew (north, south, east, west))
        tap_name: name of the tap (to display over the gate)
        """
        ring_type = 'nwell' if tap_type == 'well' else 'psub'
        generate_guard_ring(self, ring_type, tap_shape, box.width(), box.height(), box.center().x, box.center().y)
    
    
    def genLayout(self):
        self.gen_t_gate()
