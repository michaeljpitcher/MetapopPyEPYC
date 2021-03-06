from metapoppy import *
from epidemic import *
from ..events import *
from compartments import *


class SIRDynamics(Epidemic):

    INIT_S = 'initial_population_susceptible'
    INITAL_INFECTION_LOCATION = 'initial_infection_location'
    INIT_I = 'initial_population_infected'

    def __init__(self, template_network):
        self.rp_infect_key = self.rp_recover_key = self.rp_move_s_key = self.rp_move_i_key = self.rp_move_r_key = None
        Epidemic.__init__(self, [SUSCEPTIBLE, INFECTIOUS, RECOVERED], template_network)

    def _create_events(self):
        infect = Infect(SUSCEPTIBLE, INFECTIOUS, INFECTIOUS)
        self.rp_infect_key = infect.reaction_parameter()
        recover = Change(INFECTIOUS, RECOVERED)
        self.rp_recover_key = recover.reaction_parameter()
        move_s = Move(SUSCEPTIBLE)
        self.rp_move_s_key = move_s.reaction_parameter()
        move_i = Move(INFECTIOUS)
        self.rp_move_i_key = move_i.reaction_parameter()
        move_r = Move(RECOVERED)
        self.rp_move_r_key = move_r.reaction_parameter()
        return [infect, recover, move_s, move_i]

    def _build_network(self, params):
        raise NotImplementedError

    def _get_initial_patch_seeding(self, params):
        seed = {params[SIRDynamics.INITAL_INFECTION_LOCATION]:
                    {TypedMetapopulationNetwork.COMPARTMENTS: {INFECTIOUS: params[SIRDynamics.INIT_I]}}}
        return seed

    def _seed_activated_patch(self, patch_id, params):
        seed = {TypedMetapopulationNetwork.COMPARTMENTS: {SUSCEPTIBLE: params[SIRDynamics.INIT_S]}}
        return seed

    def _get_initial_edge_seeding(self, params):
        return {}