from pya import DBox


class t_gate_base():
    
    def set_devices(self, model_type):
        """
        Template method for subclasses to overwrite
        
        You need to set the pmos, nmos classes for the t-gate
        
        self.pmos = my_pmos_class
        self.nmos = my_nmos_class
        
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
        
        return object: {gate: Box(), source_contact: Box(), drain_contact: Box(), gate_top_contact: Box(), gate_bottom_contact: Box()}
        
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
    
    def gen_tap(self, box, tap_type, tap_shape, tap_name=""):
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
    
    
    def gen_t_gate(self):
        
        ## TODO: implementation
        
        # intitalize the variables
        t_gate_nmos_w = self.w*self.pmos_gate_ratio
        t_gate_nmos_l = self.l
        inv_nmos_w = self.inverter_w*self.pmos_inv_ratio
        inv_nmos_l = self.inverter_l
        
        t_gate_pmos_size = self.get_mos_dimensions(self.w, self.l, self.ng, 'T', self.pmos)
        t_gate_nmos_size = self.get_mos_dimensions(t_gate_nmos_w, t_gate_nmos_l, self.ng, 'B', self.nmos)
        inv_pmos_size = self.get_mos_dimensions(self.inverter_w, self.inverter_l, self.ng, 'none', self.pmos)
        inv_nmos_size = self.get_mos_dimensions(inv_nmos_w, inv_nmos_l, self.ng, 'none', self.nmos)

        x_outer_l = self.connection_metal_width + self.connection_metal_spacing
        x_outer_r = 2*self.connection_metal_width + self.connection_metal_spacing + self.horizontal_spacing
        x_inner = self.horizontal_spacing
        y_outer_b = self.tap_spacing + self.tap_width
        y_outer_t = self.tap_spacing + self.tap_width
        y_inner = self.vertical_spacing*2 + self.connection_metal_width
        additionnal_size = t_gate_pmos_size['Height'] - inv_pmos_size['Height']
        y_inner += additionnal_size if additionnal_size > 0 else 0
        
        total_width = x_outer_l + inv_pmos_size['Width'] + x_inner + t_gate_pmos_size['Width'] + x_outer_r
        total_height = y_outer_b + max(t_gate_nmos_size['Height'], inv_nmos_size['Height']) + y_inner + max(t_gate_pmos_size['Height'], inv_pmos_size['Height']) + y_outer_t
        
        # Starts with pmoses    
        inv_pmos_x_position = x_outer_l
        inv_pmos_y_position = y_outer_b + max(t_gate_nmos_size['Height'], inv_nmos_size['Height']) + y_inner
        t_gate_pmos_x_position = x_outer_l + max(inv_pmos_size['Width'], t_gate_pmos_size['Width']) + x_inner
        t_gate_pmos_y_position = inv_pmos_y_position + (self.inverter_w - self.w)*1e6 ## The inverter and tgate pmoses are vertically aligned        
        # Place Inverter PMOS
        inv_pmos = self.gen_mos(self.inverter_w, self.inverter_l, self.ng, 'none', self.pmos, inv_pmos_x_position, inv_pmos_y_position, "Inverter PMOS")
        # Place T-Gate PMOS
        t_gate_pmos = self.gen_mos(self.w, self.l, self.ng, 'B', self.pmos, t_gate_pmos_x_position, t_gate_pmos_y_position, "T-Gate PMOS")
        
        
        # Since the gate of the t-gate pmos is connected to the output of the inverter
        # The pmoses will be bottom aligned (but placed on the top of the layout)
        # And the gate contacts will be placed on the top only for the t-gate pmos
        
        ## Connect the output of the inverter to the gate of the t-gate pmos
                
        t_gate_pmos_gt_connection = t_gate_pmos['gate_bottom_contact']
        inv_pmos_drain_connection = inv_pmos['drain_contact']
        
        ## Connection Box:
        inv_gate_connection_box = DBox(t_gate_pmos_gt_connection.left, t_gate_pmos_gt_connection.bottom, inv_pmos_drain_connection.left, t_gate_pmos_gt_connection.top)
        self.draw_rect(inv_gate_connection_box, "M2", "EN_N")
        
        
        # Nmoses 
        inv_nmos_x_position = inv_pmos_x_position
        inv_nmos_y_position = y_outer_b
        t_gate_nmos_x_position = t_gate_pmos_x_position
        t_gate_nmos_y_position = inv_nmos_y_position ## The inverter and tgate nmoses are vertically aligned    
        
        # Place Inverter NMOS
        inv_nmos = self.gen_mos(inv_nmos_w, inv_nmos_l, self.ng, 'none', self.nmos, inv_nmos_x_position, inv_nmos_y_position, "Inverter NMOS")
        
        # Place T-Gate NMOS
        t_gate_nmos = self.gen_mos(t_gate_nmos_w, t_gate_nmos_l, self.ng, 'T', self.nmos, t_gate_nmos_x_position, t_gate_nmos_y_position, "T-Gate NMOS")
        
        # Place Vertical Connections
        en_connection_box = DBox (0, 0, self.connection_metal_width, total_height)
        self.draw_rect(en_connection_box, "M3", "EN")
        in_connection_box = DBox (total_width - self.connection_metal_width - self.connection_metal_spacing, 0, total_width - self.connection_metal_width - self.connection_metal_spacing - self.connection_metal_width, total_height)
        self.draw_rect(in_connection_box, "M3", "IN")
        out_connection_box = DBox (total_width - self.connection_metal_width, 0, total_width , total_height)
        self.draw_rect(out_connection_box, "M3", "OUT")

        # Connect the inverter fet gates and drains:
        gate_connection_box = DBox(inv_pmos['gate'].left, inv_nmos['gate'].bottom, inv_nmos['gate'].right, inv_pmos['gate'].top)
        self.draw_rect(gate_connection_box, "GatPoly", "EN")
        drain_connection_box = DBox(inv_pmos['drain_contact'].left, inv_nmos['drain_contact'].bottom, inv_nmos['drain_contact'].right, inv_pmos['drain_contact'].top)
        self.draw_rect(drain_connection_box, "M1", "EN_N")
        self.connect_boxes(inv_gate_connection_box, drain_connection_box, 'M1', 'M2')
        # Connect the t-gate with enable signal
        en_connection_t_gate_box = DBox(en_connection_box.left, gate_connection_box.center().y - self.connection_metal_width/2, t_gate_nmos['gate_top_contact'].right, gate_connection_box.center().y + self.connection_metal_width/2)
        self.draw_rect(en_connection_t_gate_box, "M2", "EN")
        
        self.connect_boxes(en_connection_t_gate_box, gate_connection_box, "GatPoly", "M2")
        
        t_gate_nmos_gt_connection_box = DBox(t_gate_nmos['gate_top_contact'].left, t_gate_nmos['gate_top_contact'].bottom, t_gate_nmos['gate_top_contact'].right, en_connection_t_gate_box.top)
        self.draw_rect(t_gate_nmos_gt_connection_box, "M1", "EN")
        
        self.connect_boxes(t_gate_nmos_gt_connection_box, en_connection_t_gate_box, "M1", "M2")
        self.connect_boxes(en_connection_t_gate_box, en_connection_box, "M2", "M3")
        
        # Connect the t-gate drains and sources
        in_drain_connection_box = DBox(t_gate_nmos['drain_contact'].left, t_gate_nmos['drain_contact'].bottom, t_gate_pmos['drain_contact'].right, t_gate_pmos['drain_contact'].top)
        self.draw_rect(in_drain_connection_box, "M1", "IN")
        out_source_connection_box = DBox(t_gate_nmos['source_contact'].left, t_gate_pmos['source_contact'].bottom, t_gate_pmos['source_contact'].right, t_gate_nmos['source_contact'].top)
        self.draw_rect(out_source_connection_box, "M1", "OUT")
        
        # Connect the IN OUT signals
        connection_drain_in_box = DBox(in_drain_connection_box.left, en_connection_t_gate_box.bottom - self.connection_metal_spacing - self.connection_metal_width, in_connection_box.right, en_connection_t_gate_box.bottom - self.connection_metal_spacing)
        self.draw_rect(connection_drain_in_box, "M2", "IN")
        connection_source_out_box = DBox(out_connection_box.right, en_connection_t_gate_box.top + self.connection_metal_spacing, out_source_connection_box.left, en_connection_t_gate_box.top + self.connection_metal_spacing + self.connection_metal_width)
        self.draw_rect(connection_source_out_box, "M2", "OUT")
        
        self.connect_boxes(in_drain_connection_box, connection_drain_in_box, "M1", "M2")
        self.connect_boxes(connection_drain_in_box, in_connection_box, "M2", "M3")
        self.connect_boxes(out_connection_box, connection_source_out_box, "M3", "M2")
        self.connect_boxes(connection_source_out_box, out_source_connection_box, "M2", "M1")
        
        # Draw taps
        # Draw nwell tap
        well_tap_bounding_box = DBox(0, min(inv_pmos['gate'].bottom, t_gate_pmos['gate'].bottom) - y_inner/2, total_width, inv_pmos['gate'].top + y_outer_b)
        self.gen_tap(well_tap_bounding_box, 'well', 'n')
        sub_tap_bounding_box = DBox(0, 0, total_width, max(inv_nmos['gate'].top, t_gate_pmos['gate'].top)+y_inner/2)
        self.gen_tap(sub_tap_bounding_box, 'sub', 's')


        pass