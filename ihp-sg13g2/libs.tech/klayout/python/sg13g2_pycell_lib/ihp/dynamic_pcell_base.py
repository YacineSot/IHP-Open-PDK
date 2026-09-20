from collections import defaultdict

import pya

from .base_definitions import base_definitions


class dynamic_pcell_base(base_definitions):
    
    def get_row_dimentions(self, pattern, index, model, w, l, dl):
        ## Calculate Dummies dimentions
        dummies_overlap_sd = self.overlap_dummies_diffusions
        dummy_ng = self.dummies_count if dummies_overlap_sd else 1
        dummies_dimensions = self.get_mos_dimensions(w, dl,dummy_ng, self.gate_connection, model)
        one_dummy_width = dummies_dimensions['Width']
        if not dummies_overlap_sd:
            dummies_dimensions['Width'] = dummies_dimensions['Width']*self.dummies_count + self.dummies_spacing*(self.dummies_count - 1)
        
        ## Calculate dimentions
        current_processed_device = 1
        row_layout_instructions = self.layout_instructions[index]
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
        
    
    def gen_row(self, pattern, index, model, w, l, dl, y_position, guard_ring_shape, guard_ring_type, guard_ring_trans=None, connection_dir='up'):
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
        row_dimentions = self.get_row_dimentions(pattern, index, model, w, l, dl)
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
        current_row = self.layout_instructions[index]
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
        nets_horizontal_boxes = {}
        nets_device_boxes = defaultdict(list)
        current_src_net_y = top + self.vertical_spacing
        current_drn_net_y = bottom - self.vertical_spacing
        current_net_y = top + self.vertical_spacing if connection_dir == 'up' else bottom - self.vertical_spacing
        dir_sign = 1 if connection_dir == 'up' else -1
        for i, core_device in enumerate(core_devices):
            source_net = self.get_net(core_device['name'], 'S')
            drain_net = self.get_net(core_device['name'], 'D')
            gate_net = self.get_net(core_device['name'], 'G')
            nets_device_boxes[source_net] += core_device['sources']
            nets_device_boxes[drain_net] += core_device['drains']
            nets_device_boxes[gate_net] += core_device['gates_t'] if connection_dir == 'up' else core_device['gates_b']
            #print(f"pattern = {pattern},current_row[{i}]['vertical_connection']: {current_row[i]['vertical_connection']}")
        for net in nets_device_boxes:
            if ('SRC' in net and 'S' not in current_row[i]['vertical_connection']) or ('DRN' in net and 'D' not in current_row[i]['vertical_connection']):
                net_box = pya.DBox(min(box.center().x for box in nets_device_boxes[net]) - self.vertical_connection_width/2, current_net_y, max(box.center().x for box in nets_device_boxes[net]) + self.vertical_connection_width/2, current_net_y + self.vertical_connection_width*dir_sign)
                nets_horizontal_boxes[net] = net_box
                self.draw_rect(net_box, self.horizontal_layers[0], net)
                current_net_y += (self.vertical_connection_width + self.connection_spacing)*dir_sign
                for dev_src_box in nets_device_boxes[net]:
                    boundary_box = self.get_boundary_box(dev_src_box, net_box)
                    conn_center = dev_src_box.center().x
                    conn_box = pya.DBox(conn_center - self.horizontal_connection_width/2, boundary_box.bottom, conn_center + self.horizontal_connection_width/2, boundary_box.top)
                    self.draw_rect(conn_box, self.vertical_layers[0], net)
                    if self.metal_layers[0] != self.vertical_layers[0]:
                        self.connect_boxes(conn_box, dev_src_box, self.vertical_layers[0], self.metal_layers[0])
                    self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
                    
            # if 'DRN' in net and 'D' not in current_row[i]['vertical_connection']:
            #     if net not in nets_horizontal_boxes:
            #         net_box = pya.DBox(min(box.left for box in nets_device_boxes[net]), current_net_y, max(box.right for box in nets_device_boxes[net]), current_net_y + self.vertical_connection_width)
            #         nets_horizontal_boxes[net] = net_box
            #         self.draw_rect(net_box, self.horizontal_layers[0], net)
            #         current_net_y += (self.vertical_connection_width + self.connection_spacing)*dir_sign
            #     for dev_drn_box in nets_device_boxes[net]:
            #         boundary_box = self.get_boundary_box(dev_drn_box, net_box)
            #         conn_center = dev_drn_box.center().x
            #         conn_box = pya.DBox(conn_center - self.horizontal_connection_width/2, boundary_box.bottom, conn_center + self.horizontal_connection_width/2, boundary_box.top)
            #         self.draw_rect(conn_box, self.vertical_layers[0], net)
            #         if self.metal_layers[0] != self.vertical_layers[0]:
            #             self.connect_boxes(conn_box, dev_drn_box, self.vertical_layers[0], self.metal_layers[0])
            #         self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
            if 'GATE' in net:
                if net not in nets_horizontal_boxes:
                    net_box = pya.DBox(min(box.left for box in nets_device_boxes[net]), current_net_y, max(box.right for box in nets_device_boxes[net]), current_net_y + self.vertical_connection_width*dir_sign)
                    nets_horizontal_boxes[net] = net_box
                    self.draw_rect(net_box, self.horizontal_layers[0], net)
                    current_net_y += (self.vertical_connection_width + self.connection_spacing)*dir_sign
                for dev_gate_box in nets_device_boxes[net]:
                    boundary_box = self.get_boundary_box(dev_gate_box, net_box)
                    conn_center = dev_gate_box.center().x
                    # conn_box = pya.DBox(conn_center - self.horizontal_connection_width/2, dev_gate_box.bottom, conn_center + self.horizontal_connection_width/2, net_box.top)
                    conn_box = pya.DBox(dev_gate_box.left, boundary_box.bottom, dev_gate_box.right, boundary_box.top)
                    self.draw_rect(conn_box, self.vertical_layers[0], net)
                    if self.metal_layers[0] != self.vertical_layers[0]:
                        self.connect_boxes(conn_box, dev_gate_box, self.vertical_layers[0], self.metal_layers[0])
                    self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
        
        
        top = device['gate_top_contact'].top if device['gate_top_contact'] else device['gate'].top
        # top = max(top, max(box.top for box in nets_horizontal_boxes.values()))
        bottom = device['gate_bottom_contact'].bottom if device['gate_bottom_contact'] else device['gate'].bottom
        # bottom = min(bottom, min(box.bottom for box in nets_horizontal_boxes.values()))
        ## fixing height
        row_dimentions["Height"] = top-bottom
        ## Adding connecitions offset:
        left_dev = left_dummies[0] if len(left_dummies) > 0 else core_devices[0]
        right_dev = right_dummies[-1] if len(right_dummies) > 0 else core_devices[-1]
        left = left_dev['active_box'].left
        right = right_dev['active_box'].right
        ## fixing width
        row_dimentions["Full_Width"] = right - left
        guard_ring_top = top + self.vertical_spacing if not guard_ring_trans else guard_ring_trans['top']
        guard_ring_bottom = bottom - self.vertical_spacing if not guard_ring_trans else guard_ring_trans['bottom']
        ring_boundary_box = pya.DBox(left, bottom, right, top)
        if self.place_taps:
            ring_boundary_box = pya.DBox(left-self.guardRingDistance_X, guard_ring_bottom, right + self.guardRingDistance_X, guard_ring_top)
            
            self.gen_tap(ring_boundary_box,guard_ring_type , guard_ring_shape, self.guardRingWidth )
        
        ## connect dummies
        ## connect gates:
        ## left dummies
        gt_max_device = max(left_dummies, key= lambda d: d['gate_top_contact'].left)
        gt_bottom_contact = left_dummies[0]['gate_bottom_contact']
        gt_max_contact = max(gt_max_device['gates_t'], key = lambda d: d.left)
        gt_connection_left = ring_boundary_box.left - self.guardRingWidth
        gt_connection_box = pya.DBox(gt_connection_left, gt_max_contact.bottom, gt_max_contact.right, gt_max_contact.top)
        gt_connection_bbox = pya.DBox(gt_connection_left, gt_bottom_contact.bottom, gt_max_contact.right, gt_bottom_contact.top)
        
        self.draw_rect(gt_connection_box, self.metal_layers[0],'')
        self.draw_rect(gt_connection_bbox, self.metal_layers[0],'')
        ## connect diffusions
        for dummy in left_dummies:
            for diff_box in dummy['sources']+dummy['drains']:
                if diff_box.left > gt_connection_box.right: continue
                conn_box = pya.DBox(diff_box.left, diff_box.bottom, diff_box.right, gt_connection_box.top)
                self.draw_rect(conn_box, self.metal_layers[0],'')
        # ## right dummies
        gt_min_device = min(right_dummies, key= lambda d: d['gate_top_contact'].left)
        gt_bottom_contact = right_dummies[0]['gate_bottom_contact']
        gt_min_contact = min(gt_min_device['gates_t'], key = lambda d: d.right)
        gt_connection_right = ring_boundary_box.right + self.guardRingWidth
        gt_connection_box = pya.DBox(gt_min_contact.left, gt_min_contact.bottom, gt_connection_right, gt_min_contact.top)
        gt_connection_bbox = pya.DBox(gt_min_contact.left, gt_bottom_contact.bottom, gt_connection_right, gt_bottom_contact.top)

        self.draw_rect(gt_connection_box, self.metal_layers[0],'')
        self.draw_rect(gt_connection_bbox, self.metal_layers[0],'')
        ## connect diffusions
        for dummy in right_dummies:
            for diff_box in dummy['sources']+dummy['drains']:
                if diff_box.right < gt_connection_box.left: continue
                conn_box = pya.DBox(diff_box.left, diff_box.bottom, diff_box.right, gt_connection_box.top)
                self.draw_rect(conn_box, self.metal_layers[0],'')
        
        
        for net, boxes in nets_horizontal_boxes.items():
            if net not in self.all_horizontal_connections:
                self.all_horizontal_connections[net] = []
            self.all_horizontal_connections[net] += [boxes]
        
        if connection_dir == 'up':
            self.ntap = {
                        'max_top' :  max(self.ntap['max_top'], top),
                        'min_bottom' :  min(self.ntap['min_bottom'], bottom),
                        'min_left' :  min(self.ntap['min_left'], left),
                        'max_right' :  max(self.ntap['max_right'], right),
                    }
        else:
            self.ptap = {
                        'max_top' :  max(self.ptap['max_top'], top),
                        'min_bottom' :  min(self.ptap['min_bottom'], bottom),
                        'min_left' :  min(self.ptap['min_left'], left),
                        'max_right' :  max(self.ptap['max_right'], right),
                    }
        return {
            "row_pattern": pattern,
            "row_index": index,
            "left_dummies": left_dummies,
            "right_dummies": right_dummies,
            "core_devices": core_devices,
            "guard_ring_box": ring_boundary_box,
            "row_dimensions": row_dimentions,
        }
    
    def calc_overlapping_distance(self, device):
        return self.fix_grid(device['source_contact'].width() + 2*(device['source_contact'].left - device['active_box'].left))
    
    def gen_array_by_model(self,pattern, model,w, l, dl, guard_ring_type ,direction = 'up', start_y=0):
        ## Preprocessing, fix the layout pattern strings
        self.parse_connections()
        formatted_pattern = self.format_pattern_string(pattern)
        self.layout_instructions = {}
        for i in range(len(formatted_pattern)):
            row = formatted_pattern[i]
            next_row = formatted_pattern[i+1] if i < len(formatted_pattern)-1 else None
            #if row in self.layout_instructions: continue
            self.layout_instructions[i] = self.optimize_row_diffusion(row, next_row)
        #print (f'self.layout_instructions: {self.layout_instructions}')
        ##################################################
        y_position = start_y
        sign = 1 if direction == 'up' else -1
        drowed_rows = []
        guard_ring_trans = None
        for i, row in enumerate(formatted_pattern):
            row_ret = self.gen_row(row, i, model, w, l, dl, y_position, 'nsew', guard_ring_type, guard_ring_trans, direction)
            drowed_rows.append(row_ret)
            y_position += sign* (row_ret['guard_ring_box'].height() + self.guardRingWidth)
            if direction == 'up':
                ring_start = row_ret['guard_ring_box'].top + self.guardRingWidth
                guard_ring_trans = {
                    'bottom' : ring_start,
                    'top' : ring_start + row_ret['guard_ring_box'].height() 
                }
            else:
                ring_start = row_ret['guard_ring_box'].bottom - self.guardRingWidth
                guard_ring_trans = {
                    'top' : ring_start,
                    'bottom' : ring_start - row_ret['guard_ring_box'].height() 
                }
        
        return drowed_rows
    
    def gen_vertical_connections(self, rows, direction = 'up'):
        for i, row in enumerate(rows):
            if i == len(rows)-1: break
            current_row = row['core_devices']
            current_row_instructions = self.layout_instructions[row['row_index']]
            #print(f'processing instruction: {current_row_instructions}')
            next_row = rows[i+1]['core_devices']
            for j,inst in enumerate(current_row_instructions):
                current_diff = inst['start_diffusion'][0]
                next_connection_top = next_row[0]['source_contact'].top
                next_connection_bottom = next_row[0]['source_contact'].bottom
                connection_v_end = next_connection_bottom if direction == 'down' else next_connection_top
                for current_diff in ['S', 'D']:
                    if current_diff in inst['vertical_connection']:
                        diff_index = 'sources' if current_diff == 'S' else 'drains'
                        device = row['core_devices'][j]
                        for diff_box in device[diff_index]:
                            box_center = diff_box.center().x
                            connection_v_start = diff_box.top if direction == 'down' else diff_box.bottom
                            conn_box = pya.DBox(box_center - self.horizontal_connection_width/2, connection_v_end, box_center + self.horizontal_connection_width/2, connection_v_start)
                            self.draw_rect(conn_box, self.vertical_layers[0], self.get_net(device['name'], current_diff))
                            self.connect_boxes(conn_box, diff_box, self.vertical_layers[0], self.metal_layers[0])
                            next_diff_box = pya.DBox(conn_box.left, next_connection_bottom, conn_box.right, next_connection_top)
                            self.connect_boxes(conn_box, next_diff_box, self.vertical_layers[0], self.metal_layers[0])
                

    
    def gen_dynamic_array(self):
        self.ptap = {
            'max_top' :  float('-inf'),
            'min_bottom' :  float('inf'),
            'min_left' :  float('inf'),
            'max_right' :  float('-inf'),
        }
        self.ntap = {
            'max_top' :  float('-inf'),
            'min_bottom' :  float('inf'),
            'min_left' :  float('inf'),
            'max_right' :  float('-inf'),
        }
        self.all_horizontal_connections = {}
        down_start_y = 0
        connections_spacing = self.connection_spacing + self.horizontal_connection_width + self.connection_spacing + self.horizontal_connection_width
        pmos_rows = []
        nmos_rows = []
        if self.pmos_layout_pattern:
            pmos_rows = self.gen_array_by_model(self.pmos_layout_pattern, self.pmos, self.pmos_w, self.pmos_l, self.dummy_pmos_l, 'well')
            down_start_y = pmos_rows[0]['guard_ring_box'].bottom - self.guardRingWidth
            self.gen_vertical_connections(pmos_rows)
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
            self.gen_vertical_connections(nmos_rows, 'down')
        
        ### Global routing between same device rows and between the two types devices:
        ### Let set it to left since it fixed positions
        max_left = (pmos_rows + nmos_rows)[0]['guard_ring_box'].left - self.guardRingWidth - self.connection_spacing
        current_left = max_left
        for net,boxes in self.all_horizontal_connections.items():
            if len(boxes) < 2: continue
            box_bottom = min(boxes, key = lambda box: box.bottom).bottom
            box_top = max(boxes, key = lambda box: box.top).top
            print (f"box_bottom={box_bottom}, box_top={box_top}")
            box_right = current_left
            box_left = box_right - self.vertical_connection_width
            vertical_box = pya.DBox(box_left, box_bottom, box_right, box_top)
            self.draw_rect(vertical_box, self.vertical_layers[0], net)
            current_left = box_left - self.connection_spacing
            for box in boxes:
                connection_box = pya.DBox(vertical_box.left, box.bottom, box.right, box.top)
                self.draw_rect(connection_box, self.horizontal_layers[0], net)
                self.connect_boxes(connection_box, vertical_box, self.vertical_layers[0], self.horizontal_layers[0])
        
        if not self.place_taps:
            ## draw all around nwell guard ring
            tap_bbox = pya.DBox(self.ntap['min_left'], self.ntap['min_bottom'], self.ntap['max_right'], self.ntap['max_top']).enlarged(self.guardRingDistance_X, self.guardRingDistance_Y)
            self.gen_tap(tap_bbox, 'well', 'nswe', self.guardRingWidth, 'well')
            ## draw all around pwell guard ring
            tap_bbox = pya.DBox(self.ptap['min_left'], self.ptap['min_bottom'], self.ptap['max_right'], self.ptap['max_top']).enlarged(self.guardRingDistance_X, self.guardRingDistance_Y)
            self.gen_tap(tap_bbox, 'sub', 'nswe', self.guardRingWidth, 'sub')
            
        return