
from cni.dlo import *
from .dynamic_array_base import dynamic_array_base
from .ihp_base_definitions import ihp_base_definitions
from .device_base_code import DeviceBase
from .nmos_code import nmos
from .nmosHV_code import nmosHV
from .pmos_code import pmos
from .pmosHV_code import pmosHV
from types import SimpleNamespace



class dynamic_array(dynamic_array_base, ihp_base_definitions, DeviceBase):
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
        
        specs('cdf_version', CDFVersion, 'CDF Version', ReadOnlyConstraint())

        cls.add_separation(cls, specs, 'Devices Sizing')
        specs('pmos_w', 5e-6, 'PMOS Width')
        specs('pmos_l', 3e-6, 'PMOS Length')
        specs('nmos_w', 5e-6, 'NMOS Width')
        specs('nmos_l' , 3e-6, 'NMOS Length')
       
        cls.add_separation(cls, specs, 'Model Type')
        specs('model_type', 'LV', 'Model Type', ChoiceConstraint(['HV', 'LV']))
        
        cls.add_separation(cls, specs, 'Internal connections & patterns settings')
        specs('horizontal_spacing', 0.26, 'Horizental Spacing')
        specs('vertical_spacing', 0.3, 'Vertical Spacing')
        specs('gate_connection', 'T-B', 'Gate Connection Side', ChoiceConstraint(['T-B','T', 'B', 'none']))
        specs('connect_gates_use_poly', True, 'Connect gates using poly')
        specs('horizontal_connection_width', 0.5e-6, 'Horizontal Connection metal width')
        specs('vertical_connection_width', 0.5e-6, 'Vertical Connection metal width')
        specs('connection_spacing', 0.5e-6, 'Connection metal spacing')
        specs('nmos_layout_pattern', '3A4B3A', 'NMOS Layout Pattern')
        specs('pmos_layout_pattern', '3A4B3A', 'PMOS Layout Pattern')
        specs('gate_connected_to_source_devices', '', 'Devices which gate linked to source')
        specs('gate_connected_to_drain_devices', '', 'Devices which gate linked to drain')
        specs('gates_connected_devices', '', 'Devices which gates connected together')
        specs('source_connected_devices', 'AB', 'Devices which sources connected together')
        specs('drain_connected_devices', '', 'Devices which sources connected together')
        
        cls.add_separation(cls, specs, 'Dummies settings')
        specs('dummies_count', 2, 'Number of dummies')
        specs('inner_dummies_count',0,'Number of dummies between devices')
        specs('dummy_pmos_l', 0.5e-6, 'Dummy PMOS length')
        specs('dummy_nmos_l', 0.5e-6, 'Dummy NMOS length')
        specs('dummies_core_spacing', -0.3, 'Distance between core and dummy')
        specs('dummies_spacing', 0.2, 'Distance between dummies')
        specs('overlap_dummies_diffusions', True, 'Overlap Dummies S/D diffusions')
        specs('place_taps', False, 'Place taps between devices')
        
        cls.default_ring = 'auto'
        super().defineParamSpecs(specs)

    def setupParams(self, params):
        # process parameter values entered by user
        self.__dict__.update(params)
        
        if params['model_type'] == 'HV':
            self.nmos = nmosHV
            self.pmos = pmosHV
        else:
            self.nmos = nmos
            self.pmos = pmos
        params['guardRingType'] = 'auto'
        super().setupParams(params)
    
    def genLayout(self):
        self.gen_dynamic_array()