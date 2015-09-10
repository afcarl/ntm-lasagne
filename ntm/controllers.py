import theano
import theano.tensor as T
import numpy as np

from lasagne.layers import Layer, MergeLayer, DenseLayer
from lasagne.layers.recurrent import Gate, LSTMLayer
import lasagne.nonlinearities
import lasagne.init


class Controller(object):
    """
    docstring for Controller
    """
    def __init__(self, num_reads, **kwargs):
        self.num_reads = num_reads

    def get_output_for(self, input, **kwargs):
        """
        Override the get_output_for method from the Layer
        since we want the controller to perform only a step
        """
        raise TypeError('A controller does not have the same '
            'behaviour as a Layer, therefore does not have '
            'a get_output_for method. Did you try to call '
            'get_output from the controller?')

    def step(self, input_and_reads, **kwargs):
        """
        Step function for the controller
        """
        raise NotImplementedError

    def non_sequences(self, **kwargs):
        raise NotImplementedError


class LSTMController(Controller, LSTMLayer):
    """
    docstring for LSTMController
    See: https://github.com/Lasagne/Lasagne/pull/294#issuecomment-112104602
    backwards, learn_init, gradient_steps are not used in the controller but
    are properties of the NTM
    """
    def __init__(self, incomings, num_units, num_reads,
                 ingate=Gate(),
                 forgetgate=Gate(),
                 cell=Gate(W_cell=None, nonlinearity=lasagne.nonlinearities.tanh),
                 outgate=Gate(),
                 nonlinearity=lasagne.nonlinearities.tanh,
                 cell_init=lasagne.init.Constant(0.),
                 hid_init=lasagne.init.Constant(0.),
                 W_reads_to_ingate=lasagne.init.GlorotUniform(),
                 b_reads_to_ingate=lasagne.init.Constant(0.),
                 W_reads_to_forgetgate=lasagne.init.GlorotUniform(),
                 b_reads_to_forgetgate=lasagne.init.Constant(0.),
                 W_reads_to_outgate=lasagne.init.GlorotUniform(),
                 b_reads_to_outgate=lasagne.init.Constant(0.),
                 W_reads_to_cell=lasagne.init.GlorotUniform(),
                 b_reads_to_cell=lasagne.init.Constant(0.),
                 learn_init=False,
                 peepholes=True,
                 **kwargs):
        Controller.__init__(self, num_reads, **kwargs)
        LSTMLayer.__init__(self, incomings[0], num_units, ingate=ingate, forgetgate=forgetgate,
            cell=cell, outgate=outgate, nonlinearity=nonlinearity, cell_init=cell_init,
            hid_init=hid_init, learn_init=learn_init, peepholes=peepholes, **kwargs)

        self.W_reads_to_ingate = self.add_param(W_reads_to_ingate, (num_reads, num_units), name='W_reads_to_ingate')
        self.b_reads_to_ingate = self.add_param(b_reads_to_ingate, (num_units,), name='b_reads_to_ingate')

        self.W_reads_to_forgetgate = self.add_param(W_reads_to_forgetgate, (num_reads, num_units), name='W_reads_to_forgetgate')
        self.b_reads_to_forgetgate = self.add_param(b_reads_to_forgetgate, (num_units,), name='b_reads_to_forgetgate')

        self.W_reads_to_outgate = self.add_param(W_reads_to_outgate, (num_reads, num_units), name='W_reads_to_outgate')
        self.b_reads_to_outgate = self.add_param(b_reads_to_outgate, (num_units,), name='b_reads_to_outgate')

        self.W_reads_to_cell = self.add_param(W_reads_to_cell, (num_reads, num_units), name='W_reads_to_cell')
        self.b_reads_to_cell = self.add_param(b_reads_to_cell, (num_units,), name='b_reads_to_cell')

    def step(self, input, reads, hid_previous, cell_previous, W_hid_stacked,
                 W_cell_to_ingate, W_cell_to_forgetgate,
                 W_cell_to_outgate, W_in_stacked, b_stacked, W_reads_stacked, b_reads_stacked):

        # At each call to scan, input_n will be (n_time_steps, 4*num_units).
        # We define a slicing function that extract the input to each LSTM gate
        def slice_w(x, n):
            return x[:, n*self.num_units:(n+1)*self.num_units]

        # if not self.precompute_input:
        input = T.dot(input, W_in_stacked) + b_stacked
        input += T.dot(reads, W_reads_stacked) + b_stacked

        # Calculate gates pre-activations and slice
        gates = input + T.dot(hid_previous, W_hid_stacked)

        # Clip gradients
        if self.grad_clipping is not False:
            gates = theano.gradient.grad_clip(
                gates, -self.grad_clipping, self.grad_clipping)

        # Extract the pre-activation gate values
        ingate = slice_w(gates, 0)
        forgetgate = slice_w(gates, 1)
        cell_input = slice_w(gates, 2)
        outgate = slice_w(gates, 3)

        if self.peepholes:
            # Compute peephole connections
            ingate += cell_previous * W_cell_to_ingate
            forgetgate += cell_previous * W_cell_to_forgetgate

        # Apply nonlinearities
        ingate = self.nonlinearity_ingate(ingate)
        forgetgate = self.nonlinearity_forgetgate(forgetgate)
        cell_input = self.nonlinearity_cell(cell_input)
        outgate = self.nonlinearity_outgate(outgate)

        # Compute new cell value
        cell = forgetgate * cell_previous + ingate * cell_input

        if self.peepholes:
            outgate += cell * W_cell_to_outgate

        # Compute new hidden unit activation
        hid = outgate * self.nonlinearity(cell)
        return [hid, cell]


# For the controller, create a step function that takes input and hidden states (stateS
# because of LSTM that outputs the hidden state and the cell state) and returns the 
# output and hidden states

if __name__ == '__main__':
    import lasagne.layers
    inp = lasagne.layers.InputLayer((None, None, 10))
    ctrl = LSTMController(inp, heads=[], num_units=100)
    print ctrl.num_units
    print ctrl.heads