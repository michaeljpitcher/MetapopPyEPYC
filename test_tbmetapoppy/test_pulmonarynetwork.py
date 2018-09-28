import unittest
from tbmetapoppy import *


class PulmonaryNetworkTestCase(unittest.TestCase):

    def setUp(self):
        self.boundary = [(0,5), (0,10), (10,10), (10,0), (0,0)]
        self.network_config = {PulmonaryNetwork.TOPOLOGY: PulmonaryNetwork.SPACE_FILLING_TREE_2D,
                               PulmonaryNetwork.BOUNDARY: self.boundary,
                               PulmonaryNetwork.LENGTH_DIVISOR: 2,
                               PulmonaryNetwork.MINIMUM_AREA: 6}
        self.compartments = ['a', 'b', 'c']
        self.tree_network = PulmonaryNetwork(self.network_config, self.compartments)
        self.tree_network.prepare()

    def test_2d_space_filling_tree_initialise(self):
        self.assertEqual(len(self.tree_network.nodes()), 17)
        self.assertEqual(len(self.tree_network.get_patches_by_type(PulmonaryNetwork.ALVEOLAR_PATCH)), 16)
        self.assertEqual(len(self.tree_network.get_patches_by_type(PulmonaryNetwork.LYMPH_PATCH)), 1)

        positions = [1.25, 3.75, 6.25, 8.75]
        e = []
        for q in positions:
            for w in positions:
                e.append((q,w))
        self.assertItemsEqual(e, self.tree_network._alveolar_positions.values())
        self.assertEqual(len(self.tree_network.edges()), 16)
        self.assertEqual(len(self.tree_network.edges([PulmonaryNetwork.LYMPH_PATCH])), 16)

    def test_pulmonary_attribute_seeding(self):
        params = {PulmonaryNetwork.VENTILATION_SKEW: 3, PulmonaryNetwork.PERFUSION_SKEW: 2,
                  PulmonaryNetwork.DRAINAGE_SKEW: 1}
        self.tree_network.seed_pulmonary_attributes(params)

        alv_patch_ids = self.tree_network.get_patches_by_type(PulmonaryNetwork.ALVEOLAR_PATCH)

        for att in [PulmonaryNetwork.VENTILATION, PulmonaryNetwork.PERFUSION, PulmonaryNetwork.DRAINAGE]:
            self.assertEqual(sum(self.tree_network.get_attribute_value(a, att) for a in alv_patch_ids), 1)

        # Check all drainage values are the same (since we've set the skew to 1)
        self.assertEqual(len(set([self.tree_network.get_attribute_value(a, PulmonaryNetwork.DRAINAGE) for a in
                                  alv_patch_ids])), 1)

        for a in alv_patch_ids:
            self.assertEqual(self.tree_network.get_attribute_value(a, PulmonaryNetwork.OXYGEN_TENSION),
                             self.tree_network.get_attribute_value(a, PulmonaryNetwork.VENTILATION) /
                             self.tree_network.get_attribute_value(a, PulmonaryNetwork.PERFUSION),)

    def test_seed_alveolar_patches(self):
        params = {PulmonaryNetwork.VENTILATION_SKEW: 1, PulmonaryNetwork.PERFUSION_SKEW: 2,
                  PulmonaryNetwork.DRAINAGE_SKEW: 1}
        self.tree_network.seed_pulmonary_attributes(params)

        rates = {self.compartments[0]: (50, 0.2), self.compartments[1]: (100, 1.1)}
        self.tree_network.seed_alveolar_patches(rates)

        for _, d in self.tree_network.get_patches_by_type(PulmonaryNetwork.ALVEOLAR_PATCH, data=True):
            self.assertEqual(d[TypedNetwork.COMPARTMENTS][self.compartments[0]],
                            int(round(float(d[TypedNetwork.ATTRIBUTES][PulmonaryNetwork.PERFUSION] *
                            rates[self.compartments[0]][0]) / rates[self.compartments[0]][1])))
            self.assertEqual(d[TypedNetwork.COMPARTMENTS][self.compartments[1]],
                            int(round(float(d[TypedNetwork.ATTRIBUTES][PulmonaryNetwork.PERFUSION] *
                            rates[self.compartments[1]][0]) / rates[self.compartments[1]][1])))
            self.assertFalse(d[TypedNetwork.COMPARTMENTS][self.compartments[2]])

        for c in self.compartments:
            self.assertFalse(self.tree_network.get_compartment_value(PulmonaryNetwork.LYMPH_PATCH, c))

    def test_seed_lymph_patch(self):
        params = {PulmonaryNetwork.VENTILATION_SKEW: 1, PulmonaryNetwork.PERFUSION_SKEW: 2,
                  PulmonaryNetwork.DRAINAGE_SKEW: 1}
        self.tree_network.seed_pulmonary_attributes(params)

        rates = {self.compartments[1]: (100, 1.1), self.compartments[2]: (69, 0.5)}
        self.tree_network.seed_lymph_patches(rates)

        self.assertEqual(self.tree_network.get_compartment_value(PulmonaryNetwork.LYMPH_PATCH, self.compartments[1]),
                         int(round(float(rates[self.compartments[1]][0]) / rates[self.compartments[1]][1])))

        for n,d in self.tree_network.get_patches_by_type(PulmonaryNetwork.ALVEOLAR_PATCH, data=True):
            for c in self.compartments:
                self.assertFalse(d[PulmonaryNetwork.COMPARTMENTS][c])


if __name__ == '__main__':
    unittest.main()