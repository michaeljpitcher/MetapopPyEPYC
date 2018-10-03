import epyc
import numpy
import math
from network import *


class Dynamics(epyc.Experiment, object):
    INITIAL_TIME = 'initial_time'
    MAX_TIME = 'max_time'

    EVENTS = 'events'

    # the default maximum simulation time
    DEFAULT_MAX_TIME = 100  #: Default maximum simulation time.
    DEFAULT_START_TIME = 0

    def __init__(self, network):
        """
        Create MetapopPy dynamics to run over the given network.
        :param network: Network on which to run dynamics
        """
        assert isinstance(network, Network), "Graph must be instance of MetapopPy Network class"
        epyc.Experiment.__init__(self)
        self._compartments = network.compartments()
        self._patch_attributes = network.patch_attributes()
        self._edge_attributes = network.edge_attributes()

        # Prepare the network
        self.network_prototype = network
        self.network_prototype.prepare(lambda a, b, c, e: self._propagate_updates(a, b, c, e))

        # Create the events
        self._events = self._create_events()
        assert self._events, "No events created"
        assert self.network_prototype.nodes(), "Empty network is invalid"

        # Obtain the patches of the network (for lookup purposes)
        patch_ids = self.network_prototype.nodes()
        self._patch_columns = dict([(patch_ids[n], n) for n in range(len(patch_ids))])

        # Create a rate table. Rows are events, columns are patches
        self._rate_table = numpy.array([[d, ] * len(patch_ids) for d in [0.0, ] * len(self._events)],
                                       dtype=numpy.float)

        # Initial network is empty. Will be overwritten with a copy of the prototype network for each experiment.
        self._network = None
        self._start_time = self.DEFAULT_START_TIME
        self._max_time = self.DEFAULT_MAX_TIME

    def _propagate_updates(self, patch_id, compartment_changes, attribute_changes, edge_changes):
        """
        When a patch ID is changed, update the relevant entries in the rate table. This function is passed as a lambda
        function to the network, and is called whenever a change is made.
        :param patch_id:
        :param compartment_changes:
        :param attribute_changes:
        :param edge_changes:
        :return:
        """
        for row in range(len(self._events)):
            col = self._patch_columns[patch_id]
            event = self._events[row]
            self._rate_table[row][col] = event.calculate_rate_at_patch(self._network, patch_id)
        # TODO - only update events dependent on atts/comps changed

    def _create_events(self):
        raise NotImplementedError

    def network(self):
        """
        The network this set of dynamics runs upon
        :return:
        """
        return self._network

    def _at_equilibrium(self, t):
        """
        Function to end simulation. Default is when max time is exceeded, can be overriden to end on a certain
        condition.
        :param t: Current simulated time
        :return: True to finish simulation
        """
        return t >= self._max_time

    def _seed_events(self, params):
        """
        Set the event reaction parameters
        :param params:
        :return:
        """
        raise NotImplementedError

    def configure(self, params):
        epyc.Experiment.configure(self, params)

        # Set the event reactions parameters using the initial conditions
        self._seed_events(params)

    def setUp(self, params):
        """
        Configure the dynamics and the network ready for a simulation.
        :param params: Initial parameters - initial conditions of network and event reaction parameters.
        :return:
        """
        # Default setup
        epyc.Experiment.setUp(self, params)

        # Use a copy of the network prototype (must be done on every run in case network has changed)
        self._network = self.network_prototype.copy()

        # Seed the network patches & edges
        self._seed_network(params)

        # Allow for designated start time (used for time/age specific events)
        if Dynamics.INITIAL_TIME in params:
            self._start_time = params[Dynamics.INITIAL_TIME]

    def _seed_network(self, params):
        raise NotImplementedError

    def set_maximum_time(self, maximum_time):
        self._max_time = maximum_time

    def do(self, params):
        """
        Run a MetapopPy simulation. Uses Gillespie simulation - all combinations of events and patches are given a rate
        based on the state of the network. An event and patch combination are chosen and performed, the event is
        performed, updating the patch (and others). Time is incremented (based on total rates) and new rates calculated.
        :param params:
        :return:
        """
        time = self._start_time

        number_patches = len(self._patch_columns)

        indexes = range(0, self._rate_table.size)
        # print "t=", time

        while not self._at_equilibrium(time):

            # Get the total rate by summing rates of all events at all patches
            total_network_rate = numpy.sum(self._rate_table)

            # If no events can occur, then end
            if total_network_rate == 0:
                break

            # Calculate the timestep delta
            dt = (1.0 / total_network_rate) * math.log(1.0 / numpy.random.random())

            # Choose an event and patch based on the values in the rate table
            index_choice = numpy.random.choice(indexes, p=self._rate_table.flatten() / total_network_rate)
            # Given the index, find the event and patch this refers to
            event = self._events[index_choice / number_patches]
            patch_id = self._patch_columns[index_choice % number_patches]

            # Perform the event. Handler will propagate the effects of any network updates
            event.perform(self._network, patch_id)

            # Move simulated time forward
            time += dt
            # print "t=", time

        # TODO - experimental results. Maybe need to track populations over time
        return self._get_results()

    def _get_results(self):
        return dict([(n, d[Network.COMPARTMENTS]) for n, d in self._network.nodes(data=True)])

    def tearDown(self):
        """
        After a simulation ends, remove the used graph.
        :return:
        """
        # Perform the default tear-down
        epyc.Experiment.tearDown(self)

        # Remove the worked-on model
        self._network = None

        # Reset rate table
        self._rate_table.fill(0.0)
