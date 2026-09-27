from pya import DBox
from .base_definitions import base_definitions

class t_gate_base(base_definitions):
    
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
        x_inner = self.horizontal_spacing + 2*self.inner_connection_width
        y_outer_b = self.tap_spacing
        y_outer_t = self.tap_spacing
        y_inner = self.vertical_spacing*2 + self.connection_metal_width
        additionnal_size = t_gate_pmos_size['Height'] - inv_pmos_size['Height']
        y_inner += additionnal_size if additionnal_size > 0 else 0
        
        total_width = x_outer_l + inv_pmos_size['Width'] + x_inner + t_gate_pmos_size['Width'] + x_outer_r
        total_height = y_outer_b + max(inv_nmos_size['Height'], t_gate_nmos_size['Height'])+ y_inner + inv_pmos_size['Height'] + y_outer_t + self.tap_width
        
        # Starts with pmoses    
        inv_pmos_x_position = x_outer_l
        inv_pmos_y_position = y_outer_b + max(t_gate_nmos_size['Height'], inv_nmos_size['Height']) + y_inner
        t_gate_pmos_x_position = x_outer_l + inv_pmos_size['Width']+ x_inner
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
        
        
        
        
        # Nmoses 
        inv_nmos_x_position = inv_pmos_x_position
        inv_nmos_y_position = y_outer_b
        t_gate_nmos_x_position = t_gate_pmos_x_position
        t_gate_nmos_y_position = inv_nmos_y_position ## The inverter and tgate nmoses are vertically aligned    
        
        # Place Inverter NMOS
        inv_nmos = self.gen_mos(inv_nmos_w, inv_nmos_l, self.ng, 'none', self.nmos, inv_nmos_x_position, inv_nmos_y_position, "Inverter NMOS")
        
        # Place T-Gate NMOS
        t_gate_nmos = self.gen_mos(t_gate_nmos_w, t_gate_nmos_l, self.ng, 'B', self.nmos, t_gate_nmos_x_position, t_gate_nmos_y_position, "T-Gate NMOS")
        
        # Place Vertical Connections
        en_connection_box = DBox (0, -self.tap_width, self.connection_metal_width, total_height)
        self.draw_rect(en_connection_box, self.vertical_layers[1], "EN")
        in_connection_box = DBox (total_width - self.connection_metal_width - self.connection_metal_spacing, -self.tap_width, total_width - self.connection_metal_width - self.connection_metal_spacing - self.connection_metal_width, total_height)
        self.draw_rect(in_connection_box, self.vertical_layers[1], "IN")
        out_connection_box = DBox (total_width - self.connection_metal_width, -self.tap_width, total_width , total_height)
        self.draw_rect(out_connection_box, self.vertical_layers[1], "OUT")

        # Connect the inverter fet gates and drains:
        gate_connection_box = DBox(inv_pmos['gate'].left - self.Mn_min_distance, inv_nmos['gate'].top, inv_nmos['gate'].right, inv_pmos['gate'].bottom)
        self.draw_rect(gate_connection_box, self.poly_layer, "EN")
        drain_connection_box = DBox(inv_pmos['drain_contact'].right, inv_nmos['drain_contact'].bottom, inv_nmos['drain_contact'].right + self.inner_connection_width, inv_pmos['drain_contact'].top)
        self.draw_rect(drain_connection_box, self.vertical_layers[0], "EN_N")
        en_connection_inv_box = DBox(en_connection_box.left, gate_connection_box.bottom, gate_connection_box.right - self.Mn_min_distance, gate_connection_box.top)
        self.draw_rect(en_connection_inv_box, self.horizontal_layers[0], 'EN')
        # Connect the t-gate with enable signal
        en_connection_t_gate_box = DBox(en_connection_box.left, t_gate_nmos['gate_bottom_contact'].bottom, t_gate_nmos['gate_bottom_contact'].right, t_gate_nmos['gate_bottom_contact'].top)
        self.draw_rect(en_connection_t_gate_box, self.horizontal_layers[0], "EN")
        
        ## Connect t-gate pmos gate with inverter output:
        inv_gate_connection_box = DBox(t_gate_pmos_gt_connection.right, t_gate_pmos_gt_connection.bottom, drain_connection_box.left, t_gate_pmos_gt_connection.top)
        self.draw_rect(inv_gate_connection_box, self.horizontal_layers[0], "EN_N")
        
        self.connect_boxes(inv_gate_connection_box, drain_connection_box, self.vertical_layers[0], self.horizontal_layers[0])
        
        self.connect_boxes(en_connection_inv_box, gate_connection_box, self.poly_layer, self.horizontal_layers[0])
        self.connect_boxes(en_connection_inv_box, en_connection_box, self.horizontal_layers[0], self.vertical_layers[1])
        self.connect_boxes(en_connection_t_gate_box, en_connection_box, self.horizontal_layers[0], self.vertical_layers[1])
        
        
        # Connect the t-gate drains and sources
        in_drain_connection_box = DBox(t_gate_nmos['drain_contact'].right, t_gate_nmos['drain_contact'].bottom, t_gate_pmos['drain_contact'].right + self.inner_connection_width, t_gate_pmos['drain_contact'].top)
        self.draw_rect(in_drain_connection_box, self.vertical_layers[0], "IN")
        out_source_connection_box = DBox(t_gate_nmos['source_contact'].left, t_gate_nmos['source_contact'].bottom, t_gate_pmos['source_contact'].left - self.inner_connection_width, t_gate_pmos['source_contact'].top)
        self.draw_rect(out_source_connection_box, self.vertical_layers[0], "OUT")
        
        # Connect the IN OUT signals
        connection_drain_in_box = DBox(t_gate_nmos['drain_contact'].left, t_gate_nmos['drain_contact'].bottom, in_connection_box.right, t_gate_nmos['drain_contact'].top)
        self.draw_rect(connection_drain_in_box, self.horizontal_layers[0], "IN")
        connection_source_out_box = DBox(t_gate_pmos['source_contact'].left, t_gate_pmos['source_contact'].bottom, out_connection_box.right, t_gate_pmos['source_contact'].top)
        self.draw_rect(connection_source_out_box, self.horizontal_layers[0], "OUT")
        
        self.connect_boxes(t_gate_nmos['drain_contact'], connection_drain_in_box, self.vertical_layers[0], self.horizontal_layers[0])
        self.connect_boxes(connection_drain_in_box, in_connection_box, self.horizontal_layers[0], self.vertical_layers[1])
        self.connect_boxes(out_connection_box, connection_source_out_box, self.vertical_layers[1], self.horizontal_layers[0])
        self.connect_boxes(connection_source_out_box, t_gate_pmos['source_contact'], self.vertical_layers[0], self.horizontal_layers[0])
        
        # Draw taps
        # Draw nwell tap
        well_tap_bounding_box = DBox(0, min(inv_pmos['gate'].bottom, t_gate_pmos['gate'].bottom), total_width, inv_pmos['gate'].top + y_outer_b)
        self.gen_tap(well_tap_bounding_box, 'well', 'n', self.tap_width)
        # Draw psub tap
        sub_tap_bounding_box = DBox(0, -0.3, total_width, max(inv_nmos['gate'].top, t_gate_pmos['gate'].top)+y_inner/2)
        self.gen_tap(sub_tap_bounding_box, 'sub', 's', self.tap_width)

        # Connect the inverter sources:
        inverter_pmos_connection_box = DBox(inv_pmos['source_contact'].left,inv_pmos['source_contact'].bottom, inv_pmos['source_contact'].left - self.inner_connection_width, well_tap_bounding_box.top)
        self.draw_rect(inverter_pmos_connection_box, self.vertical_layers[0], 'VDD')        
        
        inverter_pmos_connection_box = DBox(inv_nmos['source_contact'].left,sub_tap_bounding_box.bottom, inv_nmos['source_contact'].left - self.inner_connection_width, inv_nmos['source_contact'].top)
        self.draw_rect(inverter_pmos_connection_box, self.vertical_layers[0], 'VSS')        