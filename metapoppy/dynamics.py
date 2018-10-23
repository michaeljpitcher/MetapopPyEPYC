import epyc
import math
from network import *
import copy
import numpy


class Dynamics(epyc.Experiment, object):
    INITIAL_TIME = 'initial_time'
    MAX_TIME = 'max_time'

    EVENTS = 'events'

    # the default maximum simulation time
    DEFAULT_MAX_TIME = 100.0  #: Default maximum simulation time.
    DEFAULT_START_TIME = 0.0
    DEFAULT_RESULT_INTERVAL = 1.0

    def __init__(self, network=None):
        """
        Create MetapopPy dynamics to run over the given network.
        :param network: Network on which to run dynamics
        """
        epyc.Experiment.__init__(self)
        # Initialise variables
        self._network_prototype = self._rate_table = self._network = None

        self._row_for_patch = {}
        self._active_patches = []

        # Create the events
        self._events = self._create_events()
        assert self._events, "No events created"

        # Set the network prototype if one has been provided (if not provided, will be required during the configure
        # stage)
        if network:
            self.set_network_prototype(network)

        # Default start and end times
        self._start_time = self.DEFAULT_START_TIME
        self._max_time = self.DEFAULT_MAX_TIME

        self._record_interval = self.DEFAULT_RESULT_INTERVAL

    def _create_events(self):
        """
        Create the events
        :return:
        """
        raise NotImplementedError

    def set_network_prototype(self, prototype):
        """
        Set the network prototype and configure rate tables
        :param prototype:
        :return:
        """
        # Prepare the network
        self._network_prototype = prototype
        assert isinstance(prototype, Network), "Graph must be instance of MetapopPy Network class"
        assert self._network_prototype.nodes(), "Empty network is invalid"

    def set_start_time(self, start_time):
        """
        Set the initial time of simulations
        :param start_time:
        :return:
        """
        self._start_time = start_time

    def set_maximum_time(self, maximum_time):
        """
        Set the maximum simulated run-time
        :param maximum_time:
        :return:
        """
        self._max_time = maximum_time

    def set_record_interval(self, record_interval):
        """
        Set the interval to record results
        :param record_interval:
        :return:
        """
        self._record_interval = record_interval

    def network(self):
        """
        The current state of the network this set of dynamics is running upon
        :return:
        """
        return self._network

    def configure(self, params):
        """
        Configure the experiment for the given parameters. Sets the parameters for events (by passing all parameters to
        events)m
        :param params:
        :return:
        """
        epyc.Experiment.configure(self, params)

        # Set the event reaction parameters
        for e in self._events:
            e.set_parameters(params)

        # Allow for designated start time (used for time/age specific events)
        if Dynamics.INITIAL_TIME in params:
            self._start_time = params[Dynamics.INITIAL_TIME]

        # Ensure a network prototype is in place
        assert self._network_prototype, "Network has not been configured"

    def setUp(self, params):
        """
        Configure the dynamics and the network ready for a repetition of an experiment.
        Copies the prototype network into the main network to be updated. Seeds this network with attribute and
        compartment values.
        :param params: Initial parameters - initial conditions of network and event reaction parameters.
        :return:
        """

        # Default setup
        epyc.Experiment.setUp(self, params)

        # Use a copy of the network prototype (must be done on every run in case network has changed in order to start
        # with a fresh network)
        # TODO - inefficient to deepcopy?
        self._network = copy.deepcopy(self._network_prototype)
        # Set up compartment and attribute values as 0
        self._network.prepare()

        # Seed the prototype network
        self._seed_network(params)

        # Attach the update handler
        self._network.set_handler(lambda a, b, c, d: self._propagate_updates(a, b, c, d))

        # Check which patches should be active based on seeding
        for patch_id, data in self._network.nodes.data():
            if self._patch_is_active(patch_id):
                self._activate_patch(patch_id)

        # Check that at least one patch is active
        assert any(self._active_patches), "No patches are active"

    def _seed_network(self, params):
        """
        Seed the network in some manner based on the parameters.
        :param params:
        :return:
        """
        raise NotImplementedError

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
        # TODO only update events which depend on changed compartments/attributes
        # Check if patch is active
        # TODO - more efficient way of checking if patch is active
        active = patch_id in self._active_patches
        # If patch is already active
        if active:
            row = self._row_for_patch[patch_id]
            for col in range(len(self._events)):
                event = self._events[col]
                self._rate_table[row][col] = event.calculate_rate_at_patch(self._network, patch_id)
        # Patch is not previously active but should become active from this update
        elif self._patch_is_active(patch_id):
            self._activate_patch(patch_id)

    def _patch_is_active(self, patch_id):
        """
        Determine if the given patch is active (from the network). Default is that patches are always active, can be
        overridden to only process patches based on a given condition.
        :param patch_id:
        :return:
        """
        return True

    def _activate_patch(self, patch_id):
        """
        A patch has become active, so create a new row in the rate table for it and determine rates of events there.
        :param patch_id:
        :return:
        """
        # Calculate the row number
        self._row_for_patch[patch_id] = len(self._active_patches)
        # Add to active patch list
        self._active_patches.append(patch_id)

        # Create a row of rates - value in each column is rate of an event at this patch
        rates = numpy.array([e.calculate_rate_at_patch(self._network, patch_id) for e in self._events]).reshape(1, len(
            self._events))
        if self._rate_table is None:
            # This row becomes the rate table if it's currently empty
            self._rate_table = rates
        else:
            # Add the rates for this patch as a new row (build a new table by concatenation)
            self._rate_table = numpy.concatenate((self._rate_table, rates), 0)

    def do(self, params):
        """
        Run a MetapopPy simulation. Uses Gillespie simulation - all combinations of events and patches are given a rate
        based on the state of the network. An event and patch combination are chosen and performed, the event is
        performed, updating the patch (and others). Time is incremented (based on total rates) and new rates calculated.
        :param params:
        :return:
        """
        results = {}

        time = self._start_time

        def record_results(results, record_time):
            # TODO - we don't record edges
            results["t=" + str(record_time)] = {}
            for p, data in self.network().nodes(data=True):
                results["t=" + str(record_time)][p] = copy.deepcopy(data)
            return results

        # indices = range(0, self._rate_table.size)

        results = record_results(results, time)
        next_record_interval = time + self._record_interval

        total_network_rate = numpy.sum(self._rate_table)
        assert total_network_rate, "No events possible at start of simulation"

        num_events = len(self._events)

        while not self._at_equilibrium(time):

            # Calculate the timestep delta
            dt = (1.0 / total_network_rate) * math.log(1.0 / numpy.random.random())

            # Choose an event and patch based on the values in the rate table
            # TODO - numpy multinomial is faster than numpy choice (in python 2, maybe not in 3?)
            # index_choice = numpy.random.choice(indices, p=self._rate_table.flatten() / total_network_rate)
            index_choice = numpy.random.multinomial(1, self._rate_table.flatten() / total_network_rate).argmax()
            # Given the index, find the patch (row) and event (column) this refers to
            patch_id = self._active_patches[index_choice / num_events]
            event = self._events[index_choice % num_events]

            # Perform the event. Handler will propagate the effects of any network updates
            event.perform(self._network, patch_id)

            # Move simulated time forward
            time += dt

            # Record results if interval(s) exceeded
            while time >= next_record_interval and next_record_interval <= self._max_time:
                record_results(results, next_record_interval)
                next_record_interval += self._record_interval

            # Get the total rate by summing rates of all events at all patches
            total_network_rate = numpy.sum(self._rate_table)

            # If no events can occur, then end
            if total_network_rate == 0:
                break

        return results

    def _at_equilibrium(self, t):
        """
        Function to end simulation. Default is when max time is exceeded, can be overriden to end on a certain
        condition.
        :param t: Current simulated time
        :return: True to finish simulation
        """
        return t >= self._max_time

    def tearDown(self):
        """
        After a repetition ends, remove the used graph and rate table.
        :return:
        """
        # Perform the default tear-down
        epyc.Experiment.tearDown(self)

        # Remove the worked-on model
        self._network = None

        # Reset rate table and lookups
        self._rate_table = None
        self._active_patches = []
        self._row_for_patch = {}
