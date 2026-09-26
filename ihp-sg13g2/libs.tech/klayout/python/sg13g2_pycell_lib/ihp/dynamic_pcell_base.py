from collections import defaultdict
import pya
from .base_definitions import base_definitions

class dynamic_pcell_base(base_definitions):
    
    def get_row_dimensions(self, pattern, index, model, w, l, dl):
        """
        Calculates the full horizontal and vertical dimensions for a single row of devices, 
        including dummy transistors and spacing.
        """
        # 1. Calculate dummy dimensions
        dummies_overlap_sd = self.overlap_dummies_diffusions
        dummy_ng = self.dummies_count if dummies_overlap_sd else 1
        dummies_dimensions = self.get_mos_dimensions(w, dl, dummy_ng, 'T-B', model)
        one_dummy_width = dummies_dimensions['Width']
        
        if not dummies_overlap_sd:
            dummies_dimensions['Width'] = (dummies_dimensions['Width'] * self.dummies_count) + \
                                          (self.dummies_spacing * (self.dummies_count - 1))
        
        # 2. Calculate core device dimensions based on layout instructions
        current_processed_device = 1
        row_layout_instructions = self.layout_instructions[index]
        devices_fingers = [row_layout_instructions[0]['fingers']]
        
        while current_processed_device < len(row_layout_instructions):
            current_dev_fingers = row_layout_instructions[current_processed_device]['fingers']
            # Merge fingers if instructed, otherwise append as a new device
            if row_layout_instructions[current_processed_device - 1]['merge_next']:
                devices_fingers[-1] += current_dev_fingers
            else: 
                devices_fingers.append(current_dev_fingers)
            current_processed_device += 1
        
        # 3. Aggregate dimensions for all core devices
        different_devices_dimensions = [
            self.get_mos_dimensions(w, l, fingers, 'T-B', model) 
            for fingers in devices_fingers
        ]
        
        different_devices_width = sum(dev['Width'] for dev in different_devices_dimensions) + \
                                  (len(different_devices_dimensions) - 1) * self.horizontal_spacing
        dummies_width = dummies_dimensions['Width']
        
        return {
            'Full_Width': dummies_width + different_devices_width + dummies_width,
            'Core_Width': different_devices_width,
            'Dummies_Width': dummies_width,
            'Dummy_Width': one_dummy_width,
            'Height': different_devices_dimensions[0]['Height'] 
        }
        
    
    def gen_row(self, pattern, index, model, w, l, dl, y_position, guard_ring_shape, guard_ring_type, guard_ring_trans=None, connection_dir='up'):
        """
        Generates the physical layout for a single row.
        Execution Order: Left Dummies -> Core Devices -> Right Dummies -> Routing -> Guard Rings.
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
        
        row_dimensions = self.get_row_dimensions(pattern, index, model, w, l, dl)
        space_needed_for_overlapping = 0
        
        # --- Generate Left Dummies ---
        dummies_ng = self.dummies_count if self.overlap_dummies_diffusions else 1
        dummies_count = 1 if self.overlap_dummies_diffusions else self.dummies_count
        left_dummies = []
        
        for i in range(dummies_count):
            x_position = (row_dimensions['Dummy_Width'] + self.dummies_spacing) * i
            left_dummies.append(self.gen_mos(
                w, dl, dummies_ng, 'T-B', model, x_position, y_position, 'dummy', 
                connection_params={'s_d_mlayer': "M1", 'gate_metal': "M1"}
            ))
            if i == 0:
                space_needed_for_overlapping = self.calc_overlapping_distance(left_dummies[0]) if left_dummies else 0.3
            
        # --- Generate Core Devices ---
        core_x_offset = max(left_dummies, key=lambda dum: dum['active_box'].right)['active_box'].right + self.dummies_core_spacing
        current_x = core_x_offset
        current_row = self.layout_instructions[index]
        core_devices = []
        core_width = 0
        
        for i, dev in enumerate(current_row):
            gate_connection = ''
            gate_connection += 'T' if dev['device'] in self.gate_connection_top_devices else ''
            gate_connection += 'B' if dev['device'] in self.gate_connection_bot_devices else ''
            device_dimensions = self.get_mos_dimensions(w, l, dev['fingers'], 'T-B', model)
            device = self.gen_mos(
                w, l, dev['fingers'], gate_connection, model, current_x, y_position, 
                dev['device'], connections_dict, dev['start_diffusion']
            )
            if i==0:
                core_width = device['active_box'].left
            if i == len(current_row) - 1:
                core_width =  abs(device['active_box'].right - core_width)
            core_devices.append(device)
            current_x += device_dimensions['Width']
            
            # Handle diffusion sharing/merging between adjacent devices
            if dev['merge_next']:
                current_x -= space_needed_for_overlapping
            else:
                current_x += self.horizontal_spacing
        
        # --- Generate Right Dummies ---
        right_dummies_x_offset = core_x_offset + core_width + self.dummies_core_spacing
        right_dummies = []
        
        for i in range(dummies_count):
            x_position = right_dummies_x_offset + (row_dimensions['Dummy_Width'] + self.dummies_spacing) * i
            right_dummies.append(self.gen_mos(
                w, dl, dummies_ng, 'T-B', model, x_position, y_position, 'dummy',
                connection_params={'s_d_mlayer': "M1", 'gate_metal': "M1"}
            ))
        
        # Safely extract top/bottom boundaries from the last generated core device
        top = core_devices[-1]['gate'].top
        bottom = core_devices[-1]['gate'].bottom
        
        # --- Draw Row Connections (Routing) ---
        nets_horizontal_boxes = {}
        nets_device_boxes = defaultdict(list)
        
        current_top_net_y = top + self.connection_spacing + 0.3
        current_bot_net_y = bottom - self.connection_spacing - 0.3
        current_net_y = current_top_net_y if connection_dir == 'up' else current_bot_net_y
        dir_sign = 1 if connection_dir == 'up' else -1
        
        for i, core_device in enumerate(core_devices):
            source_net = self.get_net(core_device['name'], 'S')
            drain_net = self.get_net(core_device['name'], 'D')
            gate_net = self.get_net(core_device['name'], 'G')
            
            # Enforce minimum metal area rules on diffusions
            for box in core_device['sources'] + core_device['drains']:
                self.fix_min_met_area(box, 'v')
                
            nets_device_boxes[source_net] += core_device['sources']
            nets_device_boxes[drain_net] += core_device['drains']
            nets_device_boxes[gate_net] += core_device['gates_t'] if connection_dir == 'up' else core_device['gates_b']

        if self.draw_horizontal_connections:
            for net in nets_device_boxes:
                #if len(nets_device_boxes[net]) < 2: continue
                # Route Source/Drain
                if (('SRC' in net and 'S' not in current_row[i]['vertical_connection']) or \
                   ('DRN' in net and 'D' not in current_row[i]['vertical_connection'])) and \
                       nets_device_boxes[net]:
                    net_box = pya.DBox(
                        min(box.center().x for box in nets_device_boxes[net]) - self.vertical_connection_width / 2, 
                        current_net_y, 
                        max(box.center().x for box in nets_device_boxes[net]) + self.vertical_connection_width / 2, 
                        current_net_y + self.vertical_connection_width * dir_sign
                    )
                    nets_horizontal_boxes[net] = net_box
                    if net_box.width() > self.vertical_connection_width:
                        self.draw_rect(net_box, self.horizontal_layers[0], net)
                    current_net_y += (self.vertical_connection_width + self.connection_spacing) * dir_sign
                    
                    for dev_diff_box in nets_device_boxes[net]:
                        if 'GATE' in net: continue
                        boundary_box = self.get_boundary_box(dev_diff_box, net_box)
                        conn_center = dev_diff_box.center().x
                        conn_box = pya.DBox(
                            conn_center - self.horizontal_connection_width / 2, 
                            boundary_box.bottom, 
                            conn_center + self.horizontal_connection_width / 2, 
                            boundary_box.top
                        )
                        self.draw_rect(conn_box, self.vertical_layers[0], net)
                        if self.metal_layers[0] != self.vertical_layers[0]:
                            self.connect_boxes(conn_box, dev_diff_box, self.vertical_layers[0], self.metal_layers[0])
                        #if net_box.width() <= self.vertical_connection_width:
                        self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
                        
                # Route Gates
                if 'GATE' in net:
                    if net not in nets_horizontal_boxes and nets_device_boxes[net]:
                        net_box = pya.DBox(
                            min(box.left for box in nets_device_boxes[net]), 
                            current_net_y, 
                            max(box.right for box in nets_device_boxes[net]), 
                            current_net_y + self.vertical_connection_width * dir_sign
                        )
                        nets_horizontal_boxes[net] = net_box
                        self.draw_rect(net_box, self.horizontal_layers[0], net)
                        current_net_y += (self.vertical_connection_width + self.connection_spacing) * dir_sign
                        
                    for dev_gate_box in nets_device_boxes[net]:
                        boundary_box = self.get_boundary_box(dev_gate_box, net_box)
                        conn_center = dev_gate_box.center().x
                        conn_box = pya.DBox(
                            min(dev_gate_box.left, conn_center - self.horizontal_connection_width / 2), 
                            boundary_box.bottom, 
                            max(dev_gate_box.right, conn_center + self.horizontal_connection_width / 2), 
                            boundary_box.top
                        )
                        self.draw_rect(conn_box, self.vertical_layers[0], net)
                        if self.metal_layers[0] != self.vertical_layers[0]:
                            self.connect_boxes(conn_box, dev_gate_box, self.vertical_layers[0], self.metal_layers[0])
                        self.connect_boxes(conn_box, net_box, self.vertical_layers[0], self.horizontal_layers[0])
        
        # Calculate true height based on contacts or gate boundaries
        top = core_devices[-1]['gate'].top
        bottom = core_devices[-1]['gate'].bottom
        
        row_dimensions["Height"] = top - bottom
        
        # Calculate full width by looking at the outermost active boxes
        left_dev = left_dummies[0] if left_dummies else core_devices[0]
        right_dev = right_dummies[-1] if right_dummies else core_devices[-1]
        left = left_dev['active_box'].left
        right = right_dev['active_box'].right
        
        row_dimensions["Full_Width"] = right - left
        
        # --- Guard Ring & Taps ---
        guard_ring_top = top + self.vertical_spacing if not guard_ring_trans else guard_ring_trans['top']
        guard_ring_bottom = bottom - self.vertical_spacing if not guard_ring_trans else guard_ring_trans['bottom']
        guard_ring_left = left - self.guardRingDistance_X
        guard_ring_right = right + self.guardRingDistance_X
        ring_boundary_box = pya.DBox(left, bottom, right, top)
        
        if self.place_taps:
            ring_boundary_box = pya.DBox(guard_ring_left, guard_ring_bottom, guard_ring_right, guard_ring_top)
            self.gen_tap(ring_boundary_box, guard_ring_type, guard_ring_shape, self.guardRingWidth)
        
        # --- Dummy Connections ---
        # Connect left dummy gates and diffusions
        if left_dummies:
            gt_max_device = max(left_dummies, key=lambda d: d['gate_top_contact'].left)
            gt_bottom_contact = left_dummies[0]['gate_bottom_contact']
            gt_max_contact = max(gt_max_device['gates_t'], key=lambda d: d.left)
            gt_connection_left = guard_ring_left - self.guardRingWidth
            
            gt_connection_box = pya.DBox(gt_connection_left, gt_max_contact.bottom, gt_max_contact.right, gt_max_contact.top)
            gt_connection_bbox = pya.DBox(gt_connection_left, gt_bottom_contact.bottom, gt_max_contact.right, gt_bottom_contact.top)
            
            self.draw_rect(gt_connection_box, self.metal_layers[0], '')
            self.draw_rect(gt_connection_bbox, self.metal_layers[0], '')
            
            for dummy in left_dummies:
                for diff_box in dummy['sources'] + dummy['drains']:
                    if diff_box.left > gt_connection_box.right: continue
                    conn_box = pya.DBox(diff_box.left, gt_connection_bbox.bottom, diff_box.right, gt_connection_box.top)
                    self.draw_rect(conn_box, self.metal_layers[0], '')
                    
        # Connect right dummy gates and diffusions
        if right_dummies:
            gt_min_device = min(right_dummies, key=lambda d: d['gate_top_contact'].left)
            gt_bottom_contact = right_dummies[0]['gate_bottom_contact']
            gt_min_contact = min(gt_min_device['gates_t'], key=lambda d: d.right)
            gt_connection_right = guard_ring_right + self.guardRingWidth
            
            gt_connection_box = pya.DBox(gt_min_contact.left, gt_min_contact.bottom, gt_connection_right, gt_min_contact.top)
            gt_connection_bbox = pya.DBox(gt_min_contact.left, gt_bottom_contact.bottom, gt_connection_right, gt_bottom_contact.top)

            self.draw_rect(gt_connection_box, self.metal_layers[0], '')
            self.draw_rect(gt_connection_bbox, self.metal_layers[0], '')
            
            for dummy in right_dummies:
                for diff_box in dummy['sources'] + dummy['drains']:
                    if diff_box.right < gt_connection_box.left: continue
                    conn_box = pya.DBox(diff_box.left, gt_connection_bbox.bottom, diff_box.right, gt_connection_box.top)
                    self.draw_rect(conn_box, self.metal_layers[0], '')
        
        # Store nets for global array routing
        for net, boxes in nets_horizontal_boxes.items():
            if net not in self.all_horizontal_connections:
                self.all_horizontal_connections[net] = []
            self.all_horizontal_connections[net].append(boxes)
        
        # Update Tap bounding boxes for full array well generation
        if connection_dir == 'up':
            self.ntap['max_top'] = max(self.ntap['max_top'], top)
            self.ntap['min_bottom'] = min(self.ntap['min_bottom'], bottom)
            self.ntap['min_left'] = min(self.ntap['min_left'], left)
            self.ntap['max_right'] = max(self.ntap['max_right'], right)
        else:
            self.ptap['max_top'] = max(self.ptap['max_top'], top)
            self.ptap['min_bottom'] = min(self.ptap['min_bottom'], bottom)
            self.ptap['min_left'] = min(self.ptap['min_left'], left)
            self.ptap['max_right'] = max(self.ptap['max_right'], right)
            
        return {
            "row_pattern": pattern,
            "row_index": index,
            "left_dummies": left_dummies,
            "right_dummies": right_dummies,
            "core_devices": core_devices,
            "guard_ring_box": ring_boundary_box,
            "row_dimensions": row_dimensions,
        }
    
    def calc_overlapping_distance(self, device):
        """Calculates distance required to safely merge diffusions between adjacent devices."""
        return self.fix_grid(device['source_contact'].width() + 2 * (device['source_contact'].left - device['active_box'].left))
    
    def gen_array_by_model(self, pattern, model, w, l, dl, guard_ring_type, direction='up', start_y=0):
        """Generates all rows for a specific device type (PMOS or NMOS)."""
        formatted_pattern = self.format_pattern_string(pattern)
        self.layout_instructions = []
        
        for i in range(len(formatted_pattern)):
            row = formatted_pattern[i]
            next_row = formatted_pattern[i+1] if i < len(formatted_pattern) - 1 else None
            self.layout_instructions.append(self.optimize_row_diffusion(row, next_row))
            
        y_position = start_y
        sign = 1 if direction == 'up' else -1
        drawn_rows = []
        guard_ring_trans = None
        
        for i, row in enumerate(formatted_pattern):
            row_ret = self.gen_row(row, i, model, w, l, dl, y_position, 'nsew', guard_ring_type, guard_ring_trans, direction)
            drawn_rows.append(row_ret)
            
            # Step position for the next row based on guard ring boundaries
            y_position += sign * (row_ret['guard_ring_box'].height() + self.guardRingWidth)
            if direction == 'up':
                ring_start = row_ret['guard_ring_box'].top + self.guardRingWidth
                guard_ring_trans = {'bottom': ring_start, 'top': ring_start + row_ret['guard_ring_box'].height()}
            else:
                ring_start = row_ret['guard_ring_box'].bottom - self.guardRingWidth
                guard_ring_trans = {'top': ring_start, 'bottom': ring_start - row_ret['guard_ring_box'].height()}
        
        return drawn_rows
    
    def gen_vertical_connections(self, rows, direction='up'):
        """Routes vertical connections (Source/Drain) between adjacent rows in the array."""
        if not self.draw_vertical_connections: return
        
        for i, row in enumerate(rows):
            if i == len(rows) - 1: break
            
            current_row_instructions = self.layout_instructions[row['row_index']]
            next_row = rows[i+1]['core_devices']
            
            for j, inst in enumerate(current_row_instructions):
                next_row_core = next_row[0]
                next_connection_top = next_row_core['source_contact'].top
                next_connection_bottom = next_row_core['source_contact'].bottom
                connection_v_end = next_connection_bottom if direction == 'down' else next_connection_top
                
                for current_diff in ['S', 'D']:
                    if current_diff in inst['vertical_connection'] :
                        diff_index = 'sources' if current_diff == 'S' else 'drains'
                        device = row['core_devices'][j]
                        net = self.get_net(inst['device'], current_diff)
                        next_diffs = sum([
                            (dev['sources'] if net == self.get_net(dev['name'], 'S') else []) + 
                            (dev['drains'] if net == self.get_net(dev['name'], 'D') else []) 
                            for dev in next_row
                        ], [])
                        
                        for diff_box in device[diff_index]:
                            if not any(n_diff.left == diff_box.left for n_diff in next_diffs): continue
                            box_center = diff_box.center().x
                            connection_v_start = diff_box.top if direction == 'down' else diff_box.bottom
                            
                            conn_box = pya.DBox(
                                box_center - self.horizontal_connection_width / 2, 
                                connection_v_end, 
                                box_center + self.horizontal_connection_width / 2, 
                                connection_v_start
                            )
                            self.draw_rect(conn_box, self.vertical_layers[0], self.get_net(device['name'], current_diff))
                            self.connect_boxes(conn_box, diff_box, self.vertical_layers[0], self.metal_layers[0])
                            
                            next_diff_box = pya.DBox(conn_box.left, next_connection_bottom, conn_box.right, next_connection_top)
                            self.connect_boxes(conn_box, next_diff_box, self.vertical_layers[0], self.metal_layers[0])

    def gen_dynamic_array(self):
        """
        Main entry point. Orchestrates the creation of PMOS and NMOS arrays, 
        handles global routing between them, and draws well/substrate taps.
        """
        if not self.pmos_layout_pattern and not self.nmos_layout_pattern:
            self.draw_rect(pya.DBox(0, 0, 7, 5), self.metal_layers[0], "Error: Missing layout pattern")
            return
            
        # Initialize tap boundaries
        self.ptap = {'max_top': float('-inf'), 'min_bottom': float('inf'), 'min_left': float('inf'), 'max_right': float('-inf')}
        self.ntap = {'max_top': float('-inf'), 'min_bottom': float('inf'), 'min_left': float('inf'), 'max_right': float('-inf')}
        
        self.parse_connections()
        self.all_horizontal_connections = {}
        down_start_y = 0
        pmos_rows = []
        nmos_rows = []
        
        # 1. Generate PMOS Block
        if self.pmos_layout_pattern:
            pmos_rows = self.gen_array_by_model(self.pmos_layout_pattern, self.pmos, self.pmos_w, self.pmos_l, self.dummy_pmos_l, 'well')
            down_start_y = pmos_rows[0]['guard_ring_box'].bottom - self.guardRingWidth
            self.gen_vertical_connections(pmos_rows)
            
        # Verification to prevent layout collisions
        if any(char in self.nmos_layout_pattern for char in self.pmos_layout_pattern if char.isalpha()):
            self.show_warning("Use distinct identifiers for PMOS and NMOS layout patterns to avoid merging. Skipping NMOS array.", False)
            return
            
        # 2. Generate NMOS Block
        if self.nmos_layout_pattern:
            nmos_dimensions = self.get_mos_dimensions(
                self.nmos_w, self.nmos_l, 1, 'T-B', self.nmos, 
                {'horizontal_connection_width': self.horizontal_connection_width, 'connection_spacing': self.connection_spacing}
            )
            down_start_y -= self.vertical_spacing + self.guardRingWidth + nmos_dimensions["Height"]
            
            first_row_nets = set(self.get_row_nets([letter for letter in self.nmos_layout_pattern.split()[0] if letter.isalpha()]))
            first_row_nets = [net for net in first_row_nets if 'SRC' in net or 'GATE' in net]
            first_row_top_connections = (self.connection_spacing + self.horizontal_connection_width) * (len(first_row_nets) - 1)
            
            down_start_y -= first_row_top_connections
            nmos_rows = self.gen_array_by_model(self.nmos_layout_pattern, self.nmos, self.nmos_w, self.nmos_l, self.dummy_nmos_l, 'sub', 'down', down_start_y)
            self.gen_vertical_connections(nmos_rows, 'down')
        
        # 3. Global Routing (between matching devices/rows)
        all_rows = pmos_rows + nmos_rows
        if all_rows:
            max_left = all_rows[0]['guard_ring_box'].left - self.guardRingWidth - self.connection_spacing
            current_left = max_left
            
            if self.draw_vertical_connections and self.draw_horizontal_connections:
                for net, boxes in self.all_horizontal_connections.items():
                    if len(boxes) < 2: continue
                    box_bottom = min(boxes, key=lambda box: box.bottom).bottom
                    box_top = max(boxes, key=lambda box: box.top).top
                    
                    box_right = current_left
                    box_left = box_right - self.vertical_connection_width
                    vertical_box = pya.DBox(box_left, box_bottom, box_right, box_top)
                    self.draw_rect(vertical_box, self.vertical_layers[0], net)
                    
                    current_left = box_left - self.connection_spacing
                    
                    for box in boxes:
                        connection_box = pya.DBox(vertical_box.left, box.bottom, box.right, box.top)
                        self.draw_rect(connection_box, self.horizontal_layers[0], net)
                        self.connect_boxes(connection_box, vertical_box, self.vertical_layers[0], self.horizontal_layers[0])
        
        # 4. Generate Global Guard Rings
        if not self.place_taps:
            if self.pmos_layout_pattern:
                tap_bbox = pya.DBox(self.ntap['min_left'], self.ntap['min_bottom'], self.ntap['max_right'], self.ntap['max_top'])\
                               .enlarged(self.guardRingDistance_X, self.guardRingDistance_Y)
                self.gen_tap(tap_bbox, 'well', 'nswe', self.guardRingWidth, 'well')
                
            if self.nmos_layout_pattern:
                tap_bbox = pya.DBox(self.ptap['min_left'], self.ptap['min_bottom'], self.ptap['max_right'], self.ptap['max_top'])\
                               .enlarged(self.guardRingDistance_X, self.guardRingDistance_Y)
                self.gen_tap(tap_bbox, 'sub', 'nswe', self.guardRingWidth, 'sub')
        
        return