import re
import pya
from itertools import groupby

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
    
    def gen_mos(self, w, l, ng, gate_connection, device_model, x, y, device_name="", connection_params={
        's_d_mlayer': "M1", 
        'gate_metal': "M2"
    }):
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
        connection_params: used for the connection between the fingers
        
        return object: {gate: Box(), source_contact: Box(), drain_contact: Box(), gate_bottom_contact: Box(), gate_bottom_contact: Box()}
        
        """
        raise NotImplementedError()

    def get_mos_dimensions(self, w, l, ng, gate_connection, device_model, connection_params={}):
        """
        Template method for subclasses to overwrite
        
        w: width of the device
        l: length of the device
        ng: number of fingers
        gate_connection: gate connection position (T, B, T-B, none)
        device_model: device_model class
        
        return {Width: device_width, Height: device_height} : size of the device (active | gate)
        
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
    
    def fix_grid(self, size):
        """
        Fix Snap to grid
        """
        raise NotImplementedError()
        
    
    @staticmethod
    def format_one_line_string(input_str):
        """
        That function takes a string in format: ex, AAAA3BCDD*3
        then returns it like this: [4A3B1C2D, 4A3B1C2D, 4A3B1C2D]
        
        """
        # Step 1: Separate the string and the multiplier
        if '*' in input_str:
            base_str, repeat_count = input_str.split('*')
            repeat_count = int(repeat_count)
        else:
            base_str = input_str
            repeat_count = 1
            
        # Step 2: Expand the base string (e.g., 'AAAA' and '2B' both become 'AAAABBC')
        # The regex (\d*)([a-zA-Z]) finds an optional number followed by a letter
        expanded = "".join(
            char * (int(count) if count else 1)
            for count, char in re.findall(r'(\d*)([a-zA-Z])', base_str)
        )
        
        # Step 3: Compress the expanded string using standard Run-Length Encoding
        # groupby groups consecutive identical characters together
        compressed = "".join(
            f"{len(list(group))}{char}"
            for char, group in groupby(expanded)
        )
        
        # Step 4: Repeat the compressed string and join with spaces
        return [compressed] * repeat_count
    
    @staticmethod
    def format_pattern_string(input_str):
        """
        That function reformat the layout pattern string into iterable array
        the form of the array is: ex, [4A2B2C, 5A2B3C ....]
        """
        ## first we need to clean the input string:
        clean_input = re.sub(r'[^a-zA-Z0-9 *]', '', input_str)
        output_array = []
        for row in clean_input.split(" "):
            output_array += base_definitions.format_one_line_string(row)
        return output_array
    
    
    ######################################
    ##         PROCESS PATTERN          ##
    ######################################
    def parse_connections(self):
        """
        Converts space-separated connection strings into a netlist dictionary.
        Example: 'AB CD' -> A's Source and B's Source share 'SRC_NET_AB_1'
        """
        term_to_net = {}
        source_connected = self.source_connected_devices
        drain_connected = self.drain_connected_devices
        
        # Process Sources
        for i, group in enumerate(source_connected.split()):
            net_name = f"SRC_NET_{group}_{i+1}"
            for device_letter in group:
                term_to_net[(device_letter, 'S')] = net_name
                
        # Process Drains
        for i, group in enumerate(drain_connected.split()):
            net_name = f"DRN_NET_{group}_{i+1}"
            for device_letter in group:
                term_to_net[(device_letter, 'D')] = net_name
                
        self.term_to_net = term_to_net

    def get_net(self, device, terminal):
        """Returns the shared net ID, or a unique ID if it doesn't share anything."""
        return self.term_to_net.get((device, terminal), f"UNIQUE_{device}_{terminal}")

    @staticmethod
    def get_end_terminal(start_term, fingers):
        """
        Calculates the ending diffusion based on the start diffusion and finger count.
        - Even fingers (e.g., 4): Ends with the SAME terminal it started with (S...S or D...D).
        - Odd fingers (e.g., 3): Ends with the OPPOSITE terminal (S...D or D...S).
        """
        if fingers % 2 == 0:
            return start_term
        else:
            return 'D' if start_term == 'S' else 'S'

    def optimize_row_diffusion(self, row_string):
        """
        Uses Dynamic Programming to find the optimal S/D orientation for each device
        in the row to maximize diffusion merges.
        """
        # 1. Parse inputs
        term_to_net = self.term_to_net
        
        # Extract tuples of (fingers, device_letter) from string like "3A4B3A"
        row = [(int(count), char) for count, char in re.findall(r'(\d+)([a-zA-Z])', row_string)]
        if not row:
            return []

        # dp[i][state] = (max_merges, previous_state)
        # state is 'S' or 'D' (indicating the START terminal of the current device)
        dp = [{'S': (0, None), 'D': (0, None)}]
        
        # 2. Build the tree of possibilities
        for i in range(1, len(row)):
            prev_fingers, prev_dev = row[i-1]
            curr_fingers, curr_dev = row[i]
            
            current_dp = {}
            for curr_start in ['S', 'D']:
                best_merges = -1
                best_prev_start = None
                
                # Check both possible starting states of the PREVIOUS device
                for prev_start in ['S', 'D']:
                    prev_end = self.get_end_terminal(prev_start, prev_fingers)
                    
                    # Check if the abutting diffusions share the same net
                    prev_net = self.get_net(prev_dev, prev_end)
                    curr_net = self.get_net(curr_dev, curr_start)
                    
                    can_merge = (prev_net == curr_net)
                    merges_so_far = dp[i-1][prev_start][0] + (1 if can_merge else 0)
                    
                    if merges_so_far > best_merges:
                        best_merges = merges_so_far
                        best_prev_start = prev_start
                        
                current_dp[curr_start] = (best_merges, best_prev_start)
                
            dp.append(current_dp)

        # 3. Backtrack to find the best path
        last_dp = dp[-1]
        curr_state = 'S' if last_dp['S'][0] >= last_dp['D'][0] else 'D'
        
        path = []
        for i in range(len(row)-1, -1, -1):
            path.append(curr_state)
            curr_state = dp[i][curr_state][1]
        path.reverse()

        # 4. Format the layout instructions
        layout_instructions = []
        for i in range(len(row)):
            fingers, dev = row[i]
            start_term = path[i]
            end_term =self.get_end_terminal(start_term, fingers)
            
            merge_next = False
            if i < len(row) - 1:
                next_start = path[i+1]
                next_dev = row[i+1][1]
                
                prev_net = self.get_net(dev, end_term)
                curr_net = self.get_net(next_dev, next_start)
                merge_next = (prev_net == curr_net)
            instruction = {
                'device': dev,
                'fingers': fingers,
                'start_diffusion': start_term,
                'end_diffusion': end_term,
                'merge_next': merge_next
            }
            layout_instructions.append(instruction)
            if not merge_next and i < len(row) - 1:
                pya.MessageBox.info("Warning", f"It is prefered to use even number of fingers to merge diffusions. \n {instruction} \n Horizontal spacing param will be applied", pya.MessageBox.Ok)
            
        return layout_instructions
    
    ####################################################
    
    @staticmethod
    def extract_pairs(input_str):
        pair = re.findall(r'\d+[a-zA-Z]', input_str)
        return {'device': pair[1], 'fingers': int(pair[0])}
    
    def gen_via(self, box, b_layer, t_layer):
        """
        Template method for subclasses to overwrite
        
        box: Box() object to place the via
        b_layer: bottom layer of the via (e.g. "M1", "M2", "Poly", etc.)
        t_layer: top layer of the via (e.g. "M1", "M2", "Poly", etc.)
        
        return object: Box()
        
        """
        raise NotImplementedError()