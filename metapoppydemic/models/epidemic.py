from metapoppy import *
from ..events import *
from compartments import *


class Epidemic(Dynamics):

    def __init__(self, compartments, template_network):
        g = Environment(compartments, [], [], template=template_network)
        Dynamics.__init__(self, g)

    def _create_events(self):
        raise NotImplementedError

    def _build_network(self, params):
        raise NotImplementedError

    def _get_initial_patch_seeding(self, params):
        raise NotImplementedError

    def _get_initial_edge_seeding(self, params):
        raise NotImplementedError
