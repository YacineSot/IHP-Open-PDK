from collections import defaultdict

import pya

from .base_definitions import base_definitions


class dynamic_array_base(base_definitions):
    
    def get_row_dimentions(self, pattern, model, w, l, dl):
        ## Calculate Dummies dimentions
        dummies_overlap_sd = self.overlap_dummies_diffusions
        dummy_ng = self.dummies_count if dummies_overlap_sd else 1
        dummies_dimensions = self.get_mos_dimensions(w, dl,dummy_ng, self.gate_connection, model)
        one_dummy_width = dummies_dimensions['Width']
        if not dummies_overlap_sd:
            dummies_dimensions['Width'] = dummies_dimensions['Width']*self.dummies_count + self.dummies_spacing*(self.dummies_count - 1)
        
        ## Calculate dimentions
        current_processed_device = 1
        row_layout_instructions = self.layout_instructions[pattern]
        devices_fingers = [row_layout_instructions[0]['fingers']]
        while current_processed_device < len(row_layout_instructions):
            current_dev_fingers = row_layout_instructions[current_processed_device]['fingers']
            if row_layout_instructions[current_processed_device - 1]['merge_next']:
                devices_fingers[-1] += current_dev_fingers
            else: devices_fingers.append(current_dev_fingers)
            current_processed_device += 1
        
        different_devices_dimentions = []
        for fingers in devices_fingers:
            different_devices_dimentions.append(self.get_mos_dimensions(w,l,fingers, self.gate_connection, model))
        different_devices_width = sum(dev['Width'] for dev in different_devices_dimentions) + (len(different_devices_dimentions)-1)*self.horizontal_spacing
        dummies_width = dummies_dimensions['Width']
        return {
            'Full_Width': dummies_width + different_devices_width + dummies_width,
            'Core_Width': different_devices_width,
            'Dummies_Width': dummies_width,
            'Dummy_Width': one_dummy_width,
            'Height': different_devices_dimentions[0]['Height'] 
        }
        
    
    def gen_row(self, pattern, model, w, l, dl, y_position, guard_ring_shape, guard_ring_type):
        """
        STEPS: 
        Generate left dummies (like that the origin will be in the bottom left of the first dummy)
        Generate the main devices
        Generate right dummies
        """
        connections_dict = {
            'horizontal_connection_width': self.horizontal_connection_width,
            'vertical_connection_width': self.vertical_connection_width,
            'connect_diffusions': False,
            'connect_gates': True,
            'connection_spacing': self.connection_spacing,
            'connect_gates_use_poly': self.connect_gates_use_poly,
            's_d_mlayer': "M1", 
            'gate_metal': "M1",
            'odd_vertical': self.odd_vertical,
            'distribute_connections': True,
        }
        row_dimentions = self.get_row_dimentions(pattern, model, w, l, dl)
        space_needed_for_ovelapping = 0
        
        ## Generate left dummies
        dummies_ng = self.dummies_count if self.overlap_dummies_diffusions else 1
        dummies_count = 1 if self.overlap_dummies_diffusions else self.dummies_count
        left_dummies = []
        for i in range(dummies_count):
            x_position = (row_dimentions['Dummy_Width'] + self.dummies_spacing)*i
            left_dummies.append( self.gen_mos(w, dl, dummies_ng, self.gate_connection, model,x_position, y_position, 'dummy',connection_params={
                's_d_mlayer': "M1", 
                'gate_metal': "M1"
            }))
            if i == 0:
                space_needed_for_ovelapping = self.calc_overlapping_distance(left_dummies[0]) if len(left_dummies) > 0 else 0.3
            
        ## Generate the core device
        core_x_offset = row_dimentions['Dummies_Width'] + self.dummies_core_spacing
        current_x = core_x_offset
        current_row = self.layout_instructions[pattern]
        core_devices = []
        for i, dev in enumerate(current_row):
            device_dimensions = self.get_mos_dimensions(w, l, dev['fingers'], self.gate_connection, model)
            device = self.gen_mos(w, l, dev['fingers'], self.gate_connection, model, current_x, y_position, dev['device'], connections_dict, dev['start_diffusion'])
            core_devices.append(device)
            current_x += device_dimensions['Width']
            #print(f'device optimized params: {dev}')
            if dev['merge_next']:
                current_x += -space_needed_for_ovelapping
                #print('merging with next')
            else:
                current_x += self.horizontal_spacing
        
        ## Generate right dummies
        right_dummies_x_offset = core_x_offset + row_dimentions['Core_Width'] + self.dummies_core_spacing
        right_dummies = []
        for i in range(dummies_count):
            x_position = right_dummies_x_offset + (row_dimentions['Dummy_Width'] + self.dummies_spacing)*i
            right_dummies.append(self.gen_mos(w, dl, dummies_ng, self.gate_connection, model,x_position, y_position, 'dummy',connection_params={
                's_d_mlayer': "M1", 
                'gate_metal': "M1"
            }))
        
        top = device['top']
        bottom = device['bottom']
        ## Draw row connections
        nets_horizental_boxes = {}
        nets_device_boxes = defaultdict(list)
        current_src_net_y = top + self.vertical_spacing
        current_drn_net_y = bottom - self.vertical_spacing
        for core_device in core_devices:
            source_net = self.get_net(core_device['name'], 'S')
            drain_net = self.get_net(core_device['name'], 'D')
            gate_net = self.get_net(core_device['name'], 'G')
            nets_device_boxes[source_net] += core_device['sources']
            nets_device_boxes[drain_net] += core_device['drains']
            nets_device_boxes[gate_net] += core_device['gates_t']
        for net in nets_device_boxes:
            if 'SRC' in net:
                net_box = pya.DBox(min(box.left for box in nets_device_boxes[net]), current_src_net_y, max(box.right for box in nets_device_boxes[net]), current_src_net_y + self.vertical_connection_width)
                nets_horizental_boxes[net] = net_box
                self.draw_rect(net_box, self.horizontal_layers[0], net)
                current_src_net_y += self.vertical_connection_width + self.connection_spacing
                for dev_src_box in nets_device_boxes[net]:
                    conn_center = dev_src_box.center().x
                    conn_box = pya.DBox(conn_center - self.horizontal_connection_width/2, dev_src_box.bottom, conn_center + self.horizontal_connection_width/2, net_box.top)
                    self.draw_rect(conn_box, self.vertical_layers[0], net)
                    self.connect_boxes(conn_box, dev_src_box, self.vertical_layers[0], self.horizontal_layers[0])
                    self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
                    
            if 'DRN' in net:
                if net not in nets_horizental_boxes:
                    net_box = pya.DBox(min(box.left for box in nets_device_boxes[net]), current_drn_net_y - self.vertical_connection_width, max(box.right for box in nets_device_boxes[net]), current_drn_net_y)
                    nets_horizental_boxes[net] = net_box
                    self.draw_rect(net_box, self.horizontal_layers[0], net)
                    current_drn_net_y -= self.vertical_connection_width + self.connection_spacing
                for dev_drn_box in nets_device_boxes[net]:
                    conn_center = dev_drn_box.center().x
                    conn_box = pya.DBox(conn_center - self.horizontal_connection_width/2, net_box.bottom, conn_center + self.horizontal_connection_width/2, dev_drn_box.top)
                    self.draw_rect(conn_box, self.vertical_layers[0], net)
                    self.connect_boxes(conn_box, dev_drn_box, self.vertical_layers[0], self.horizontal_layers[0])
                    self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
            if 'GATE' in net:
                if net not in nets_horizental_boxes:
                    net_box = pya.DBox(min(box.left for box in nets_device_boxes[net]), current_src_net_y, max(box.right for box in nets_device_boxes[net]), current_src_net_y + self.vertical_connection_width)
                    nets_horizental_boxes[net] = net_box
                    self.draw_rect(net_box, self.horizontal_layers[0], net)
                    current_src_net_y += self.vertical_connection_width + self.connection_spacing
                for dev_gate_box in nets_device_boxes[net]:
                    conn_center = dev_gate_box.center().x
                    conn_box = pya.DBox(conn_center - self.horizontal_connection_width/2, dev_gate_box.bottom, conn_center + self.horizontal_connection_width/2, net_box.top)
                    self.draw_rect(conn_box, self.vertical_layers[0], net)
                    self.connect_boxes(conn_box, dev_gate_box, self.vertical_layers[0], self.horizontal_layers[0])
                    self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
        top = max(box.top for box in nets_horizental_boxes.values())
        bottom = min(box.bottom for box in nets_horizental_boxes.values())
        ## fixing height
        row_dimentions["Height"] = top-bottom
        ## Adding connecitions offset:
        left_dev = left_dummies[0] if len(left_dummies) > 0 else core_devices[0]
        right_dev = right_dummies[-1] if len(right_dummies) > 0 else core_devices[-1]
        left = left_dev['active_box'].left
        right = right_dev['active_box'].right
        ## fixing width
        row_dimentions["Full_Width"] = right - left
        ring_boundary_box = pya.DBox(left-self.guardRingDistance, bottom - self.vertical_spacing, right + self.guardRingDistance, top + self.vertical_spacing)
        
        self.gen_tap(ring_boundary_box,guard_ring_type , guard_ring_shape, self.guardRingWidth )
        return {
            "left_dummies": left_dummies,
            "right_dummies": right_dummies,
            "core_devices": core_devices,
            "guard_ring_box": ring_boundary_box,
            "row_dimensions": row_dimentions
        }
    
    def calc_overlapping_distance(self, device):
        return self.fix_grid(device['source_contact'].width() + 2*(device['source_contact'].left - device['active_box'].left))
    
    def gen_array_by_model(self,pattern, model,w, l, dl, guard_ring_type ,direction = 'up', start_y=0):
        ## Preprocessing, fix the layout pattern strings
        self.parse_connections()
        formatted_pattern = self.format_pattern_string(pattern)
        self.layout_instructions = {}
        for row in formatted_pattern:
            if row in self.layout_instructions: continue
            self.layout_instructions[row] = self.optimize_row_diffusion(row)
        ##################################################
        y_position = start_y
        sign = 1 if direction == 'up' else -1
        drowed_rows = []
        for row in formatted_pattern:
            row_ret = self.gen_row(row, model, w, l, dl, y_position, 'nsew', guard_ring_type)
            drowed_rows.append(row_ret)
            y_position += sign* (row_ret['guard_ring_box'].height() + self.guardRingWidth)
        
        return drowed_rows
    
    def gen_dynamic_array(self):
        down_start_y = 0
        connections_spacing = self.connection_spacing + self.horizontal_connection_width + self.connection_spacing + self.horizontal_connection_width
        pmos_rows = []
        nmos_rows = []
        if self.pmos_layout_pattern:
            pmos_rows = self.gen_array_by_model(self.pmos_layout_pattern, self.pmos, self.pmos_w, self.pmos_l, self.dummy_pmos_l, 'well')
            down_start_y = pmos_rows[0]['guard_ring_box'].bottom - self.guardRingWidth
        if any(char in self.nmos_layout_pattern for char in self.pmos_layout_pattern if char.isalpha()):
            self.show_warning("""Use different letters for the pmos and nmos layout patterns, otherwise the devices will be merged
                              Skipping drawing the nmos array""", False)
            return
        if self.nmos_layout_pattern:
            nmos_dimensions = self.get_mos_dimensions(self.nmos_w, self.nmos_l, 1, self.gate_connection, self.nmos, {'horizontal_connection_width': self.horizontal_connection_width, 'connection_spacing': self.connection_spacing})
            down_start_y -= self.vertical_spacing + self.guardRingWidth + self.vertical_spacing + nmos_dimensions["Height"]
            first_row_nets = set(self.get_row_nets([letter for letter in self.nmos_layout_pattern.split()[0] if letter.isalpha()]))
            first_row_nets = [net for net in first_row_nets if 'SRC' in net or 'GATE' in net]
            first_row_top_connections = (self.connection_spacing + self.horizontal_connection_width)*(len(first_row_nets) -1)
            down_start_y -= first_row_top_connections
            nmos_rows = self.gen_array_by_model(self.nmos_layout_pattern, self.nmos, self.nmos_w, self.nmos_l, self.dummy_nmos_l, 'sub','down', down_start_y)
            
        return