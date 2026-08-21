

class base_definitions():
    def set_devices(self, model_type):
        """
        Template method for subclasses to overwrite
        
        You need to set the pmos, nmos classes
        
        self.pmos = my_pmos_class
        self.nmos = my_nmos_class
        
        And set the self.vertical_metals, self.horizontal_metals here
        """
        raise NotImplementedError()
    
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
        
        return object: {gate: Box(), source_contact: Box(), drain_contact: Box(), gate_bottom_contact: Box(), gate_bottom_contact: Box()}
        
        """
        raise NotImplementedError()

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
        raise NotImplementedError()
    
    def gen_tap(self, box, tap_type, tap_shape, tap_width ,tap_name=""):
        """
        Template method for subclasses to overwrite
        
        box: Box() object representing the tap's bounding box
        tap_type: type of the tap (nwell, psub)
        tap_shape: shape of the tap (here we define the inluding sides nsew (north, south, east, west))
        tap_name: name of the tap (to display over the gate)
        """
        raise NotImplementedError()
    
    def draw_rect(self, box, layer, net_name=""):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to draw
        layer: layer of the rectangle (e.g. "M1", "M2", "Poly", etc.)
        net_name: name of the net (to display over the rectangle)
        
        return object: Box()
        
        """
        raise NotImplementedError()
    
    def draw_label(self, box, text, layer, size=0):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to draw the label
        text: text of the label
        layer: layer of the label (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Text()
        
        """
        raise NotImplementedError()
    
    def connect_boxes(self, box1, box2, b_layer, t_layer):
        """
        Template method for subclasses to overwrite
        
        box1: Box() object to connect
        box2: Box() object to connect
        b_layer: bottom layer of the connection (e.g. "M1", "M2", "Poly", etc.)
        t_layer: top layer of the connection (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        raise NotImplementedError()
    
    def gen_via(self, box, b_layer, t_layer):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to place the via
        b_layer: bottom layer of the via (e.g. "M1", "M2", "Poly", etc.)
        t_layer: top layer of the via (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        raise NotImplementedError()