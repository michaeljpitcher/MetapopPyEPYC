import networkx
import numpy


class Network(networkx.Graph):
    """
    A MetapopPy network. Extends networkX graph, adding data for patch subpopulations and environmental attributes.
    """

    COMPARTMENTS = 'compartments'
    ATTRIBUTES = 'attributes'

    def __init__(self, compartments, patch_attributes, edge_attributes):
        """
        Create a network
        :param compartments: List of population compartments
        :param patch_attributes: List of patch attributes
        :param edge_attributes: List of edge attributes
        """
        self._compartments = compartments
        self._patch_attributes = patch_attributes
        self._edge_attributes = edge_attributes
        self._handler = None
        networkx.Graph.__init__(self)

    def compartments(self):
        """
        Get function for compartments
        :return:
        """
        return self._compartments

    def patch_attributes(self):
        """
        Get function for patch attributes
        :return:
        """
        return self._patch_attributes

    def edge_attributes(self):
        """
        Get function for edge attributes
        :return:
        """
        return self._edge_attributes

    def prepare(self, handler=None):
        """
        Prepare the network. Adds data to the node dictionary, for subpopulation, environmental attributes and events
        and rates. All set to zero, will be seeded with a value once simulation runs.
        :return:
        """
        # Prepare the network
        for _, patch_data in self.nodes(data=True):
            patch_data[Network.COMPARTMENTS] = dict([(c, 0) for c in self._compartments])
            patch_data[Network.ATTRIBUTES] = dict([(c, 0) for c in self._patch_attributes])
        for u, v in self.edges():
            for a in self._edge_attributes:
                self.edge[u][v][a] = 0.0
        self._handler = handler

    def get_compartment_value(self, patch_id, compartment):
        """
        Get function for finding a compartment value at a patch
        :param patch_id:
        :param compartment:
        :return:
        """
        return self.node[patch_id][Network.COMPARTMENTS][compartment]

    def get_attribute_value(self, patch_id, attribute):
        """
        Get function for finding an environmental attribute value at a patch
        :param patch_id:
        :param attribute:
        :return:
        """
        return self.node[patch_id][Network.ATTRIBUTES][attribute]

    def update_patch(self, patch_id, compartment_changes=None, attribute_changes=None):
        patch_data = self.node[patch_id]
        if compartment_changes:
            for comp, change in compartment_changes.iteritems():
                patch_data[Network.COMPARTMENTS][comp] += change
                assert patch_data[Network.COMPARTMENTS][comp] >= 0, "Compartment {0} cannot drop below zero".format(comp)
        if attribute_changes:
            for attr, change in attribute_changes.iteritems():
                patch_data[Network.ATTRIBUTES][attr] += change
        if self._handler:
            if not compartment_changes:
                compartment_changes = {}
            if not attribute_changes:
                attribute_changes = {}
            self._handler(patch_id, compartment_changes.keys(), attribute_changes.keys(), {})

    def update_edge(self, u,v, attribute_changes):
        edge = self.edge[u][v]
        for attr, change in attribute_changes.iteritems():
            edge[attr] += change
        if self._handler:
            self._handler(u, [], [], attribute_changes.keys())
            self._handler(v, [], [], attribute_changes.keys())


class TypedNetwork(Network):
    """
    A MetapopPy network where patches are assigned a "type", which can restrict which dynamics occurs there.
    """

    PATCH_TYPE = 'patch_type'

    def __init__(self, compartments, patch_attributes, edge_attributes):
        """
        Create a network
        :param compartments: List of population compartments
        :param patch_attributes: List of patch attributes
        :param edge_attributes: List of edge attributes
        """
        patch_attributes.append(TypedNetwork.PATCH_TYPE)
        Network.__init__(self, compartments, patch_attributes, edge_attributes)
        self._patch_types = {}

    def set_patch_type(self, patch_id, patch_type):
        self.node[patch_id][TypedNetwork.PATCH_TYPE] = patch_type

    def get_patches_by_type(self, patch_type):
        if patch_type not in self._patch_types:
            return []
        else:
            return self._patch_types[patch_type]

    def prepare(self, handler=None):
        # Ensure every patch has been given a type
        for patch_id, patch_data in self.nodes(data=True):
            assert TypedNetwork.PATCH_TYPE in patch_data, "Node {0} must be assigned a patch type".format(patch_id)
            # Create the shortcut list for this patch type if we haven't seen it yet
            if patch_data[TypedNetwork.PATCH_TYPE] not in self._patch_types:
                self._patch_types[patch_data[TypedNetwork.PATCH_TYPE]] = []
            # Add to the list
            self._patch_types[patch_data[TypedNetwork.PATCH_TYPE]].append(patch_id)
        Network.prepare(self, handler)
