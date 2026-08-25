
from .base_definitions import base_definitions
from .pmos_code import pmos
from .pmosHV_code import pmosHV
from .nmos_code import nmos
from .nmosHV_code import nmosHV
from .geometry import *
from .guard_ring_code import generate_guard_ring
from .via_stack_code import via_stack
from .utility_functions import GridFix


class ihp_base_definitions(base_definitions):
    def additionnal_specs(self, specs):
        specs("start_level", 1, "First connection metal", ChoiceConstraint([1,2]))
        specs("odd_vertical", True, "Vertical Metal ODD")
    
    def additionnal_params(self, params):
        self.start_level = int(params["start_level"])
        self.odd_vertical = params['odd_vertical']
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
        
        self.poly_layer = Layer("GatPoly")
        self.horizontal_layers = []
        self.vertical_layers = []
        for i in range(1,5):
            if i < self.start_level: continue;
            layer = Layer(f"Metal{i}")
            if self.odd_vertical:
                if i%2 == 0:
                    self.horizontal_layers.append(layer)
                else:
                    self.vertical_layers.append(layer)
            else:
                if i%2 != 0:
                    self.horizontal_layers.append(layer)
                else:
                    self.vertical_layers.append(layer)
    
    def gen_mos(self, w, l, ng, gate_connection, device_model, x, y, device_name="", connection_params={
        's_d_mlayer': "M1", 
        'gate_metal': "M2"
    }, start_diffusion="Source"):
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
                    'ng': ng, 
                    'gate_connection': gate_connection,
                    'cnt_w_ratio': 80,
                    'gate_cnt_ratio': 100,
                    'guardRingType': 'none',
                    'guardRingDistance': 0.5,
                } | connection_params
        device.tech = self.tech
        device._getCurrentCellContext = self._getCurrentCellContext
        if device_name:
            device.label = device_name
        device.sx = x
        device.sy = y
        device.setupParams(params)
        device.start_diffusion = start_diffusion
        device.genDeviceLayout()
        contacts = {
            'gate': device.gate_box.box,
            'source_contact': device.source_box.box,
            'drain_contact': device.drain_box.box,
            'gate_top_contact': device.gate_box_t.box if hasattr(device, 'gate_box_t') else None,
            'gate_bottom_contact': device.gate_box_b.box if hasattr(device, 'gate_box_b') else None,
            'active_box': device.active_box.box
        }
        # if device_name:
        #     self.draw_label(device.gate_box.box, device_name, Layer("TEXT"))
        return contacts

    def get_mos_dimensions(self, w, l, ng, gate_connection, device_model, connection_params={}):
        """
        Template method for subclasses to overwrite
        
        w: width of the device
        l: length of the device
        ng: number of fingers
        gate_connection: gate connection position (T, B, T-B, none)
        device_model: device_model class
        
        return (sx, sy) : size of the device (active | gate)
        
        """
        dimensions = device_model.get_dimensions(w*1e6, l*1e6, ng, self.techparams, gate_connection, connection_params = connection_params)
        return {'Width': dimensions[0], 'Height': dimensions[1]}
    
    def fix_grid(self, size):
        """
        Fix Snap to grid
        """
        return GridFix(size)
    
    def draw_rect(self, box, layer, net_name=""):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to draw
        layer: layer of the rectangle (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        ihp_box = Box(0,0,0,0)
        ihp_box.box = box
        dbCreateRect(self, layer, ihp_box)
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
        dbCreateLabel(self, layer, point, text, "centerCenter", rotation, Font.EURO_STYLE, auto_size)
    
    def gen_via(self, box, b_layer, t_layer, origin='centerCenter'):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to place the via
        b_layer: bottom layer of the via (e.g. "M1", "M2", "Poly", etc.)
        t_layer: top layer of the via (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        via_device = via_stack()
        params = {
            'vn_columns': 0,
            'vn_rows': 0,
            'vt1_columns': 0,
            'vt1_rows': 0,
            'vt2_columns': 0,
            'vt2_rows': 0,
            'b_layer': b_layer._name,
            't_layer': t_layer._name,
            'origin': origin,
            'extra_vias': False,
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
        
    def gen_tap(self, box, tap_type, tap_shape,tap_width,  tap_name=""):
        """
        Template method for subclasses to overwrite
        
        box: Box() object representing the tap's bounding box
        tap_type: type of the tap (nwell, psub)
        tap_shape: shape of the tap (here we define the inluding sides nsew (north, south, east, west))
        tap_name: name of the tap (to display over the gate)
        """
        ring_type = 'nwell' if tap_type == 'well' else 'psub'
        generate_guard_ring(self, ring_type, tap_shape, box.width(), box.height(), box.center().x, box.center().y, tap_width)
    