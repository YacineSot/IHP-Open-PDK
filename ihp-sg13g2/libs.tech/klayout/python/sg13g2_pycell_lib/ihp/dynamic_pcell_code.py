
from cni.dlo import *
from .dynamic_pcell_base import dynamic_pcell_base
from .guard_ring_code import GuardRingType
from .ihp_base_definitions import ihp_base_definitions
from .device_base_code import DeviceBase
from .nmos_code import nmos
from .nmosHV_code import nmosHV
from .pmos_code import pmos
from .pmosHV_code import pmosHV
from types import SimpleNamespace



class dynamic_pcell(dynamic_pcell_base, ihp_base_definitions, DeviceBase):
    @classmethod
    def defineParamSpecs(cls, specs):
        techparams = specs.tech.getTechParams()
        cls.techparams = techparams
        CDFVersion = techparams['CDFVersion']
        defL       = techparams['nmos_defL']
        defW       = techparams['nmos_defW']
        defNG      = techparams['nmos_defNG']
        minL       = techparams['nmos_minL']
        minW       = techparams['nmos_minW']

        cls.add_separation(cls, specs, 'Version readonly')
        descriptions = cls.read_description_file("./dynamic_pcell_descriptions.json")
        
        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint(), tooltip=descriptions['cdf_version'])

        cls.add_separation(cls, specs, 'Devices Sizing')
        specs('pmos_w', 5, 'PMOS Width', unit='um', tooltip=descriptions['pmos_w'])
        specs('pmos_l', 3, 'PMOS Length', unit='um', tooltip=descriptions['pmos_l'])
        specs('nmos_w', 5, 'NMOS Width', unit='um', tooltip=descriptions['nmos_w'])
        specs('nmos_l' , 3, 'NMOS Length', unit='um', tooltip=descriptions['nmos_l'])
    
        cls.add_separation(cls, specs, 'Model Type')
        specs('model_type', 'LV', 'Model Type', ChoiceConstraint(['HV', 'LV']), tooltip=descriptions['model_type'])
        
        cls.add_separation(cls, specs, 'Internal connections & patterns settings')
        specs('horizontal_spacing', 0.26, 'Horizental Spacing', unit='um', tooltip=descriptions['horizontal_spacing'])
        specs('vertical_spacing', 0.3, 'Vertical Spacing', unit='um', tooltip=descriptions['vertical_spacing'])
        specs('connect_gates_use_poly', True, 'Connect gates using poly', tooltip=descriptions['connect_gates_use_poly'])
        specs('horizontal_connection_width', 0.5, 'Horizontal Connection metal width', unit='um', tooltip=descriptions['horizontal_connection_width'])
        specs('vertical_connection_width', 0.5, 'Vertical Connection metal width', unit='um', tooltip=descriptions['vertical_connection_width'])
        specs('connection_spacing', 0.5, 'Connection metal spacing', unit='um', tooltip=descriptions['connection_spacing'])
        specs('nmos_layout_pattern', '3A4B3A', 'NMOS Layout Pattern', tooltip=descriptions['nmos_layout_pattern'])
        specs('pmos_layout_pattern', '3C4D3C', 'PMOS Layout Pattern', tooltip=descriptions['pmos_layout_pattern'])
        specs('gate_connection_top_devices', 'AC', 'Gate Connection On Top', tooltip=descriptions['gate_connection_top_devices'])
        specs('gate_connection_bot_devices', 'BD', 'Gate Connection On Bottom', tooltip=descriptions['gate_connection_bot_devices'])
        specs('gate_connected_to_source_devices', '', 'Devices which gate linked to source', tooltip=descriptions['gate_connected_to_source_devices'])
        specs('gate_connected_to_drain_devices', 'A', 'Devices which gate linked to drain', tooltip=descriptions['gate_connected_to_drain_devices'])
        specs('gates_connected_devices', 'AB', 'Devices which gates connected together', tooltip=descriptions['gates_connected_devices'])
        specs('source_connected_devices', 'AB CD', 'Devices which sources connected together', tooltip=descriptions['source_connected_devices'])
        specs('drain_connected_devices', '', 'Devices which drains connected together', tooltip=descriptions['drain_connected_devices'])
        # specs('drains_to_tap_devices', 'TBD', 'Devices which drains connected to tap',ReadOnlyConstraint(), tooltip=descriptions['drains_to_tap_devices'])
        # specs('sources_to_tap_devices', 'TBD', 'Devices which sources connected to tap',ReadOnlyConstraint(), tooltip=descriptions['sources_to_tap_devices'])
        specs('draw_vertical_connections', True, 'Draw Vertical Connections', tooltip=descriptions['draw_vertical_connections'])
        specs('draw_horizontal_connections', False, 'Draw Horizontal Connections', tooltip=descriptions['draw_horizontal_connections'])
        cls.additionnal_specs(cls, specs, descriptions)
        
        cls.add_separation(cls, specs, 'Dummies settings')
        specs('dummies_count', 2, 'Number of dummies', tooltip=descriptions['dummies_count'])
        specs('inner_dummies_count',0,'Number of dummies between devices', tooltip=descriptions['inner_dummies_count'])
        specs('dummy_pmos_l', 0.5, 'Dummy PMOS length', unit='um', tooltip=descriptions['dummy_pmos_l'])
        specs('dummy_nmos_l', 0.5, 'Dummy NMOS length', unit='um', tooltip=descriptions['dummy_nmos_l'])
        specs('dummies_core_spacing', -0.3, 'Distance between core and dummy', unit='um', tooltip=descriptions['dummies_core_spacing'])
        specs('dummies_spacing', 0.2, 'Distance between dummies', unit='um', tooltip=descriptions['dummies_spacing'])
        specs('overlap_dummies_diffusions', True, 'Overlap Dummies S/D diffusions', tooltip=descriptions['overlap_dummies_diffusions'])
        specs('place_taps', False, 'Place taps between devices', tooltip=descriptions['place_taps'])
        
        cls.default_ring = 'auto'
        super().defineParamSpecs(specs)

    def setupParams(self, params):
        # process parameter values entered by user
        self.__dict__.update(params)
        self.set_devices(self.model_type)
        self.convert_to_um(['pmos_w', 'pmos_l', 'nmos_w', 'nmos_l', 'dummy_pmos_l', 'dummy_nmos_l'])
        params['guardRingType'] = 'auto'
        self.use_deep_nwell = self.use_nbulay
        self.pmos_layout_pattern = self.sanitize_pattern_string(self.pmos_layout_pattern)
        self.nmos_layout_pattern = self.sanitize_pattern_string(self.nmos_layout_pattern)
        super().setupParams(params)
    
    
    def convert_to_um(self, param_names):
        for param_name in param_names:
            if hasattr(self, param_name):
                value = getattr(self, param_name)
                if isinstance(value, (int, float)):
                    setattr(self, param_name, value * 1e-6)  # Convert to micrometers
    
    def sanitize_pattern_string(self, pattern: str) -> str:
        """
        Cleans the user-input layout pattern string before processing.
        Fixes multiple spaces, tabs, newlines, and trailing/leading whitespace.
        """
        if not pattern or not isinstance(pattern, str):
            return ""
            
        # .split() without arguments automatically splits by ANY whitespace 
        # (spaces, tabs, newlines) and discards empty strings caused by multiple spaces.
        # .join() stitches them back together with exactly one space.
        cleaned_pattern = " ".join(pattern.split())
        
        # Convert to uppercase to ensure letters match device declarations safely
        return cleaned_pattern.upper()
    
    @classmethod
    def validGuardRingTypes(cls) -> List[GuardRingType]:
        """
        Template method for subclasses to restrict the guard ring types
        """
        return [GuardRingType.AUTO]
    
    def genLayout(self):
        self.gen_dynamic_array()