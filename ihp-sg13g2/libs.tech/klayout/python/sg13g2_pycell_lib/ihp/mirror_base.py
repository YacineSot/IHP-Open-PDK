import math

class MirrorBase:
    """
    PDK-agnostic base class for generating parameterized mirror layouts.
    Requires subclasses to implement drawing and instantiation primitives.
    """

    # -------------------------------------------------------------------------
    # Abstract Methods (To be implemented by PDK-specific subclasses)
    # -------------------------------------------------------------------------
    def get_device_dimensions(self):
        """Returns (width, height, poly_origin_offset) in microns."""
        raise NotImplementedError

    def place_device(self, char, x, y):
        """
        Places a device at (x, y).
        Returns a dict with contact bounding boxes in microns:
        {
            'source': [left, bottom, right, top],
            'drain': [left, bottom, right, top],
            'gate_t': [left, bottom, right, top],
            'gate_b': [left, bottom, right, top]
        }
        """
        raise NotImplementedError

    def place_dummy(self, x, y):
        """Places a dummy device at (x, y) and returns its contact bounding boxes."""
        raise NotImplementedError

    def draw_rect(self, layer_name, box, label = ""):
        """
        Draws a rectangle on the given logical layer.
        box = [left, bottom, right, top] in microns.
        layer_name is a string (e.g. 'M1', 'M2', 'M3').
        """
        raise NotImplementedError

    def draw_label(self, layer_name, text, box, rotation="R0"):
        """
        Draws a text label in the center of the box.
        box = [left, bottom, right, top] in microns.
        rotation = 'R0' or 'R90'.
        """
        raise NotImplementedError

    def draw_via(self, box, metal_b, metal_t, direction="V"):
        """
        Draws a via filling the given box between metal_b and metal_t.
        box = [left, bottom, right, top] in microns.
        """
        raise NotImplementedError

    def generate_tap(self, box):
        """
        Places a tap / guard ring contact in the specified box.
        """
        raise NotImplementedError
        
    def generate_outer_guard_ring(self, box):
        """
        Generates an outer guard ring for the whole array if required by the PDK.
        """
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Core Logic
    # -------------------------------------------------------------------------
    @staticmethod
    def fix_string(string, separation=""):
        return ''.join([char for char in string if char.isalpha() or char == separation])

    def _intersect_boxes(self, box1, box2):
        """Returns the intersection of two boxes [l, b, r, t], or None if they don't overlap."""
        ix1, iy1 = max(box1[0], box2[0]), max(box1[1], box2[1])
        ix2, iy2 = min(box1[2], box2[2]), min(box1[3], box2[3])
        if ix1 < ix2 and iy1 < iy2:
            return [ix1, iy1, ix2, iy2]
        return None

    def _get_nearest_box(self, target_box, candidates):
        """Finds the box in candidates whose center X is closest to target_box's center X."""
        if not candidates: return None
        target_center_x = (target_box[0] + target_box[2]) / 2.0
        
        def dist(box):
            return abs(((box[0] + box[2]) / 2.0) - target_center_x)
            
        return min(candidates, key=dist)

    def generate_mirror_layout(self):
        # 1. Parse Pattern
        separation = " "
        clean_pattern = self.fix_string(self.layout_pattern, separation)
        cells = clean_pattern.upper().split(separation)
        cells = cells[::-1] # Draw from bottom to top
        cells = [self.fix_string(cell) for cell in cells]
        
        # Determine unique devices
        different_devices = set(clean_pattern.replace(separation, ''))
        N_dev = len(different_devices)
        if N_dev == 0 or len(cells) == 0 or len(cells[0]) == 0:
            return

        # Parameter extraction (assumes the subclass has mapped these to self attributes)
        conn_w = self.connection_metal_width
        conn_d = self.connection_metal_distance
        h_dist = self.horizontal_distance
        v_dist = self.vertical_distance
        
        # 2. Get Subcell Dimensions
        width, height, poly_origin_offset = self.get_device_dimensions()
        
        # 3. Grid Calculation
        outer_devs_l = set(cell[0] for cell in cells)
        outer_devs_r = set(cell[-1] for cell in cells)
        N_outer_dev_l = len(outer_devs_l)
        N_outer_dev_r = len(outer_devs_r)
        
        # Handling common connections
        linked_gate_to_source_devs = different_devices & set(self.gate_linked_to_source_devs) if hasattr(self, 'gate_linked_to_source_devs') else set()
        common_source_devs = different_devices & set(self.connected_source_devs) if hasattr(self, 'connected_source_devs') else set()
        common_gate_devs = set(self.connected_gate_devs) if hasattr(self, 'connected_gate_devs') else set()
        
        N_unique_gate_connection = N_dev if len(common_gate_devs) < 2 else N_dev - len(common_gate_devs) + 1
        N_unique_source_connection = N_dev if len(common_source_devs) < 2 else N_dev - len(common_source_devs) + 1
        N_linked_gate_to_source_devs = len(linked_gate_to_source_devs)
        N_unique_gate_connection -= N_linked_gate_to_source_devs
        
        bot_top_dist = 0.3
        
        # Outer gaps
        x_outer_l = h_dist + N_outer_dev_l * conn_w + conn_d * (N_outer_dev_l - 1) if N_outer_dev_l > 0 else h_dist
        x_outer_r = h_dist + N_outer_dev_r * conn_w + conn_d * (N_outer_dev_r - 1) if N_outer_dev_r > 0 else h_dist
        y_outer_t = bot_top_dist + N_dev * conn_w + conn_d * (N_dev - 1)
        y_outer_b = bot_top_dist + (N_unique_gate_connection + N_unique_source_connection) * conn_w + conn_d * ((N_unique_gate_connection + N_unique_source_connection) - 1)
        
        # Inner gaps
        num_inner = 2 * N_dev
        x_inner = 2 * h_dist + num_inner * conn_w + conn_d * (num_inner - 1)
        y_inner = getattr(self, 'inner_vertical_distance', v_dist)
        
        # Initialize contact lists
        contact_list = {}
        connections_list = {}
        for dev in different_devices:
            connections_list[dev] = {
                'drain_h': [], 'drain_v': [],
                'source_h': [], 'source_v': [],
                'gate_v': [], 'gate_h': []
            }
            contact_list[dev] = {
                'drain': [], 'gate_t': [], 'gate_b': [], 'source': []
            }

        # 4. Place Devices
        for i in range(len(cells[0])):
            for j, r in enumerate(cells):
                device_char = r[i]
                x_pos = x_outer_l + i * width + i * x_inner
                y_pos = y_outer_b + j * height + j * y_inner + poly_origin_offset
                
                conns = self.place_device(device_char, x_pos, y_pos)
                if conns:
                    contact_list[device_char]['source'].append(conns.get('source'))
                    contact_list[device_char]['drain'].append(conns.get('drain'))
                    contact_list[device_char]['gate_t'].append(conns.get('gate_t'))
                    contact_list[device_char]['gate_b'].append(conns.get('gate_b'))
        
        # 5. Dummies
        dummies_count = getattr(self, 'dummies_count', 0)
        dummies_offset = getattr(self, 'dummies_offset', 0.4)
        dummies_distance = getattr(self, 'dummies_distance', 0.4)
        guard_ring_distance = getattr(self, 'guard_ring_distance', 0.4)
        
        dummy_connection1 = {'top': None, 'bottom': None, 'left': None, 'right': None}     
        dummy_connection2 = {'top': None, 'bottom': None, 'left': None, 'right': None}   

        for i in range(int(dummies_count)):
            for j in range(len(cells)):
                # Left Dummy
                x_pos = x_outer_l - dummies_offset - (i+1)*(width + dummies_distance)
                y_pos = y_outer_b + j*height + j*y_inner + poly_origin_offset
                d_conns = self.place_dummy(x_pos, y_pos)
                if d_conns:
                    if j == 0 and i == 0 and d_conns.get('gate_b'): dummy_connection1['bottom'] = d_conns['gate_b'][1]
                    if j == (len(cells)-1) and i == 0 and d_conns.get('gate_t'): dummy_connection1['top'] = d_conns['gate_t'][3]
                    if i == 0 and j == 0 and d_conns.get('drain'): dummy_connection1['left'] = d_conns['drain'][2]
                    if i == (dummies_count - 1) and j == (len(cells)-1) and d_conns.get('source'): dummy_connection1['right'] = d_conns['source'][0] - guard_ring_distance - 0.3
                
                # Right Dummy
                x_pos = x_outer_l + dummies_offset + (i+1)*(width + dummies_distance) + (width + x_inner)*(len(cells[0])-1)
                d_conns2 = self.place_dummy(x_pos, y_pos)
                if d_conns2:
                    if j == 0 and i == 0 and d_conns2.get('gate_b'): dummy_connection2['bottom'] = d_conns2['gate_b'][1]
                    if j == (len(cells)-1) and i == 0 and d_conns2.get('gate_t'): dummy_connection2['top'] = d_conns2['gate_t'][3]
                    if i == 0 and j == 0 and d_conns2.get('source'): dummy_connection2['left'] = d_conns2['source'][0]
                    if i == (dummies_count - 1) and j == (len(cells)-1) and d_conns2.get('drain'): dummy_connection2['right'] = d_conns2['drain'][2] + guard_ring_distance + 0.3 

        # 6. Draw Routing Buses
        total_width = x_outer_l + len(cells[0]) * width + (len(cells[0]) - 1) * x_inner + x_outer_r if len(cells[0]) > 0 else width
        total_height = y_outer_b + len(cells) * height + (len(cells) - 1) * y_inner + y_outer_t if len(cells) > 0 else height

        # Taps
        place_taps = getattr(self, 'place_taps', False)
        gate_connection_horizontal_shift = 0.3 if place_taps else 0
        min_metal1_distance = getattr(self, 'min_metal1_distance', 0.24)
        if abs(self.horizontal_distance - gate_connection_horizontal_shift) < min_metal1_distance:
            gate_connection_horizontal_shift = 0

        if place_taps and gate_connection_horizontal_shift > 0:
            for j in range(len(cells) - 1):
                tap_x_center = x_outer_l + (j + 1)*(width + x_inner) - x_inner/2
                tap_box = [tap_x_center - 0.24, y_outer_b, tap_x_center + 0.24, y_outer_b + len(cells)*height + (len(cells)-1)*y_inner]
                self.generate_tap(tap_box)

        # Vertical Buses (M3)
        for i in range(len(cells[0]) + 1):
            if i == 0:
                gap_start_x = 0
                for k, dev in enumerate(outer_devs_l):
                    line_x = gap_start_x + k * (conn_w + conn_d)
                    box = [line_x, 0, line_x + conn_w, total_height]
                    self.draw_rect('M3', box, f"source {dev}")
                    connections_list[dev]['source_v'].append(box)
            elif i == len(cells[0]):
                gap_start_x = x_outer_l + i * width + (i - 1) * x_inner
                for k, dev in enumerate(outer_devs_r):
                    line_x = gap_start_x + h_dist + k * (conn_w + conn_d)
                    box = [line_x, 0, line_x + conn_w, total_height]
                    self.draw_rect('M3', box, f"drain {dev}")
                    connections_list[dev]['drain_v'].append(box)
            else:
                gap_start_x = x_outer_l + i * width + (i - 1) * x_inner
                for k, dev in enumerate(different_devices):
                    line_x_d = gap_start_x + h_dist + k * (conn_w + conn_d)
                    box_d = [line_x_d, 0, line_x_d + conn_w, total_height]
                    self.draw_rect('M3', box_d, f"drain {dev}")
                    connections_list[dev]['drain_v'].append(box_d)
                    
                    gate_box_d = [box_d[0] - gate_connection_horizontal_shift, box_d[1], box_d[2] - gate_connection_horizontal_shift, box_d[3]]
                    self.draw_rect('M1', gate_box_d, f"gate {dev}")
                    connections_list[dev]['gate_v'].append(gate_box_d)
                    
                    s_idx = k + N_dev
                    line_x_s = gap_start_x + h_dist + s_idx * (conn_w + conn_d)
                    box_s = [line_x_s, 0, line_x_s + conn_w, total_height]
                    self.draw_rect('M3', box_s, f"source {dev}")
                    connections_list[dev]['source_v'].append(box_s)
                    
                    gate_box_s = [box_s[0] + gate_connection_horizontal_shift, box_s[1], box_s[2] + gate_connection_horizontal_shift, box_s[3]]
                    self.draw_rect('M1', gate_box_s, f"gate {dev}")
                    connections_list[dev]['gate_v'].append(gate_box_s)

        # Horizontal Buses (M2)
        for j in range(len(cells) + 1):
            if j == 0:
                gap_start_y = 0
                k = 0
                for dev in different_devices:
                    dev_name = dev
                    if dev in common_source_devs:
                        dev_name = "+".join(common_source_devs)
                        for tdev in self.connected_source_devs:
                            if tdev == dev: continue
                            if len(connections_list[tdev]['source_h']) > 0:
                                connections_list[dev]['source_h'] = connections_list[tdev]['source_h']
                                break;                        
                        if connections_list[dev]['source_h']: continue
                    line_y = gap_start_y + (N_unique_gate_connection + k) * (conn_w + conn_d)
                    box = [0, line_y, total_width, line_y + conn_w]
                    self.draw_rect('M2', box, f"source {dev_name}")
                    connections_list[dev]['source_h'].append(box)
                    k += 1
                k = 0
                for dev in different_devices:
                    dev_name = dev
                    if dev in common_gate_devs:
                        dev_name = "+".join(common_gate_devs)
                        for tdev in self.connected_gate_devs:
                            if tdev == dev: continue;
                            if len(connections_list[tdev]['gate_h']) > 0:
                                connections_list[dev]['gate_h'] = connections_list[tdev]['gate_h']
                                break;                        
                        if connections_list[dev]['gate_h']: continue
                    if dev in linked_gate_to_source_devs:
                        continue
                    line_y = gap_start_y + k * (conn_w + conn_d)
                    box = [0, line_y, total_width, line_y + conn_w]
                    self.draw_rect('M2', box, f"gate {dev_name}")
                    connections_list[dev]['gate_h'].append(box)
                    k += 1
            elif j == len(cells):
                gap_start_y = total_height
                for k, dev in enumerate(different_devices):
                    line_y = gap_start_y - k * (conn_w + conn_d) - conn_w
                    box = [0, line_y, total_width, line_y + conn_w]
                    self.draw_rect('M2', box, f"drain {dev}")
                    connections_list[dev]['drain_h'].append(box)
            else:
                pass # Inner horizontal gaps skipped

        # 7. Connect Regions
        for dev in connections_list:
            c = connections_list[dev]
            
            # Intersection Vias
            for b_v in c['drain_v']:
                for b_h in c['drain_h']:
                    i_box = self._intersect_boxes(b_v, b_h)
                    if i_box: self.draw_via(i_box, 'M2', 'M3')
                    
            for b_v in c['source_v']:
                for b_h in c['source_h']:
                    i_box = self._intersect_boxes(b_v, b_h)
                    if i_box: self.draw_via(i_box, 'M2', 'M3')
                    
            for b_v in c['gate_v']:
                for b_h in c['gate_h']:
                    i_box = self._intersect_boxes(b_v, b_h)
                    if i_box: self.draw_via(i_box, 'M1', 'M2')
                    
            # Connect Terminals to Buses
            for dr in contact_list[dev]['drain']:
                if dr and c['drain_v']:
                    nearest = self._get_nearest_box(dr, c['drain_v'])
                    if nearest:
                        bridge = [min(dr[2], nearest[0]), dr[1], max(dr[0], nearest[2]), dr[3]]
                        self.draw_rect('M2', bridge)
                        via_box = [nearest[0], dr[1], nearest[2], dr[3]]
                        self.draw_via(via_box, 'M2', 'M3')
                    
            for sc in contact_list[dev]['source']:
                if sc and c['source_v']:
                    nearest = self._get_nearest_box(sc, c['source_v'])
                    if nearest:
                        bridge = [min(sc[2], nearest[0]), sc[1], max(sc[0], nearest[2]), sc[3]]
                        self.draw_rect('M2', bridge)
                        via_box = [nearest[0], sc[1], nearest[2], sc[3]]
                        self.draw_via(via_box, 'M2', 'M3')
                    
            for gt in contact_list[dev]['gate_t'] + contact_list[dev]['gate_b']:
                if gt and c['gate_v']:
                    nearest = self._get_nearest_box(gt, c['gate_v'])
                    if nearest:
                        bridge = [max(gt[2], nearest[0]), gt[1], min(gt[0], nearest[2]), gt[3]]
                        self.draw_rect('M2', bridge)
                        via_box = [nearest[0], gt[1], nearest[2], gt[3]]
                        self.draw_via(via_box, 'M1', 'M2')
                    
            if dev in linked_gate_to_source_devs:
                v_target = c['source_v'] if getattr(self, 'connect_gate_to', 'source') == 'source' else c['drain_v']
                for gt in contact_list[dev]['gate_t'] + contact_list[dev]['gate_b']:
                    if gt and v_target:
                        nearest = self._get_nearest_box(gt, v_target)
                        if nearest:
                            bridge = [min(gt[2], nearest[0]), gt[1], max(gt[0], nearest[2]), gt[3]]
                            self.draw_rect('M2', bridge) 
                            via_box = [nearest[0], gt[1], nearest[2], gt[3]]
                            self.draw_via(via_box, 'M2', 'M3')


        # Full guard ring
        self.generate_outer_guard_ring()

        # Dummy routing loops
        if int(dummies_count) > 0:
            if dummy_connection1['left'] is not None:
                top = max(y_outer_t + len(cells)*height, total_height) + guard_ring_distance + 0.3
                bottom = -0.3 - guard_ring_distance
                box1 = [dummy_connection1['left'], bottom, dummy_connection1['right'] - 0.3, top]
                self.draw_rect('M1', box1)
                
            if dummy_connection2['left'] is not None:
                box2 = [dummy_connection2['left'], bottom, dummy_connection2['right'] + 0.3, top]
                self.draw_rect('M1', box2)