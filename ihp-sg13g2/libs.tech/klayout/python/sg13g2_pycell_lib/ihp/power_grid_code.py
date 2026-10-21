from .device_base_code import DeviceBase
from .ihp_base_definitions import ihp_base_definitions
from cni.dlo import *


class power_grid(DeviceBase, ihp_base_definitions):
    @classmethod
    def defineParamSpecs(cls, specs):
        cls.tech = specs.tech
        cls.init_metal_stacks(cls)
        techparams = specs.tech.getTechParams()
        cls.techparams = techparams
        CDFVersion = techparams['CDFVersion']

        cls.add_separation(cls, specs, 'Version readonly')
        descriptions = cls.read_description_file("./power_grid_descriptions.json")
        
        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint(), tooltip=descriptions['cdf_version'])
        
        specs('w', 10.0, 'Width', unit='um', tooltip=descriptions['w'])
        specs('l', 10.0, 'Length', unit='um', tooltip=descriptions['l'])
        specs('t_metal', cls.top_metal_stacks[-1], 'Top Metal Layer',ChoiceConstraint(cls.metal_stacks + cls.top_metal_stacks), tooltip=descriptions['t_metal'])
        specs('b_metal', cls.metal_stacks[-1], 'Bottom Metal Layer',ChoiceConstraint(cls.metal_stacks + cls.top_metal_stacks), tooltip=descriptions['b_metal'])
        specs('t_metal_width', 2.0, 'Top Metal Width', unit='um', tooltip=descriptions['t_metal_width'])
        specs('b_metal_width', 2.0, 'Bottom Metal Width', unit='um', tooltip=descriptions['b_metal_width'])
        specs('n_cols', 4, 'Number of Top Metal Columns', tooltip=descriptions['n_cols'])
        specs('n_rows', 4 , 'Number of Bottom Metal Rows', tooltip=descriptions['n_rows'])
        specs('min_spacing', 0.5, 'Minimum Spacing',  unit='um', tooltip=descriptions['min_spacing'])
        super().defineParamSpecs(specs)
    
    
    def setupParams(self, params):
        # process parameter values entered by user
        self.__dict__.update(params)
        super().setupParams(params)
        
    
    def genDeviceLayout(self):
        ## calculating the required metal spacing:
        full_space_w = self.w - self.n_cols*self.t_metal_width
        full_space_h = self.l - self.n_rows*self.b_metal_width
        
        t_metal_spacing = full_space_w / (self.n_cols - 1)
        b_metal_spacing = full_space_h / (self.n_rows - 1)
        min_required_spacing = (self.n_cols - 1) * self.min_spacing
        if full_space_w < min_required_spacing:
            self.show_warning("Warning: The specified width is too small to accommodate the requested number of top metal columns with the minimum spacing. Adjusting the width accordingly.")
            self.t_metal_width = (self.w - min_required_spacing) / self.n_cols
            t_metal_spacing = self.min_spacing  # Set to minimum spacing since we adjusted the width
        
        if full_space_h < min_required_spacing:
            self.show_warning("Warning: The specified length is too small to accommodate the requested number of bottom metal rows with the minimum spacing. Adjusting the length accordingly.")
            self.b_metal_width = (self.l - min_required_spacing) / self.n_rows
            b_metal_spacing = self.min_spacing  # Set to minimum spacing since we adjusted the length
        
        
        top_metal_layer = Layer(self.t_metal.replace("M", "Metal").replace("T", "Top"))
        bottom_metal_layer = Layer(self.b_metal.replace("M", "Metal").replace("T", "Top"))
        top_metal_net1 = []
        top_metal_net2 = []
        bottom_metal_net1 = []
        bottom_metal_net2 = []
        ## Create the top metal grid
        for i in range(self.n_cols):
            x = i * (self.t_metal_width + t_metal_spacing)
            box = Box(x, 0, x + self.t_metal_width, self.l)
            self.draw_rect(top_metal_layer, box)
            if i % 2 == 0:
                top_metal_net1.append(box)
            else:
                top_metal_net2.append(box)
        
        for i in range(self.n_rows):
            y = i * (self.b_metal_width + b_metal_spacing)
            box = Box(0, y, self.w, y + self.b_metal_width)
            self.draw_rect(bottom_metal_layer, box)
            if i % 2 == 0:
                bottom_metal_net1.append(box)
            else:
                bottom_metal_net2.append(box)
        
        ## Connect the top metal grid to the bottom metal grid using vias
        
        for top_box in top_metal_net1:
            for bottom_box in bottom_metal_net1:
                self.connect_boxes(top_box.box, bottom_box.box, top_metal_layer, bottom_metal_layer)
        
        for top_box in top_metal_net2:
            for bottom_box in bottom_metal_net2:
                self.connect_boxes(top_box.box, bottom_box.box, top_metal_layer, bottom_metal_layer)
            