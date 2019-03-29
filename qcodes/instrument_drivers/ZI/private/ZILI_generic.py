import time
import logging
import numpy as np
from functools import partial
from math import sqrt, log10

from typing import Callable, List, Union, cast
from enum import Enum, auto

try:
    import zhinst.utils
except ImportError:
    raise ImportError('''Could not find Zurich Instruments LabOne software.
                         Please refer to the ZI User Manual for
                         download and installation instructions.
                      ''')

from qcodes.instrument.parameter import MultiParameter
from qcodes.instrument.base import Instrument
from qcodes.utils import validators as vals

log = logging.getLogger(__name__)


class ValueType(Enum):
    INT = auto()
    DOUBLE = auto()
    SAMPLE = auto()

class _ZILI_generic(Instrument):
    """
    Abstract QCoDeS driver for ZI Lockins

    TODOs:
        * Add zoom-FFT
    """

    def __init__(self, name: str, device_ID: str, api_level: int, **kwargs) -> None:
        """
        Create an instance of the instrument.

        Args:
            name (str): The internal QCoDeS name of the instrument
            device_ID (str): The device name as listed in the web server, in the form 'devXXXX'
            api_level (int): The required version of LabOne API version
        """

        super().__init__(name, **kwargs)
        zisession = zhinst.utils.create_api_session(device_ID, api_level)
        (self.daq, self.device, self.props) = zisession

        self.daq.setDebugLevel(3)

    def _create_parameters(self, num_osc, num_demod, out_map):
        ########################################
        # INSTRUMENT PARAMETERS

        ########################################
        # Oscillators
        for oscs in range(1,num_osc+1):
            self.add_parameter(f'oscillator{oscs}_freq',
                               label=f'Frequency of oscillator {oscs}',
                               unit='Hz',
                               set_cmd=self._setter('oscs', oscs, 'freq', ValueType.DOUBLE),
                               get_cmd=self._getter('oscs', oscs, 'freq', ValueType.DOUBLE)
                               )

        ########################################
        # DEMODULATOR PARAMETERS

        for demod in range(1, num_demod+1):
            self.add_parameter(f'demod{demod}_order',
                               label='Filter order',
                               get_cmd=self._getter('demods', demod, 'order', ValueType.INT),
                               set_cmd=self._setter('demods', demod, 'order', ValueType.INT),
                               vals=vals.Ints(1, 8)
                               )

            self.add_parameter(f'demod{demod}_harmonic',
                               label=('Reference frequency multiplication' +
                                      ' factor'),
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 1, 'harmonic'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 1, 'harmonic'),
                               vals=vals.Ints(1, 1023)
                               )

            self.add_parameter('demod{}_timeconstant'.format(demod),
                               label='Filter time constant',
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 1, 'timeconstant'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 1, 'timeconstant'),
                               unit='s'
                               )

            self.add_parameter('demod{}_samplerate'.format(demod),
                               label='Sample rate',
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 1, 'rate'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 1, 'rate'),
                               unit='Sa/s',
                               docstring="""
                                         Note: the value inserted by the user
                                         may be approximated to the
                                         nearest value supported by the
                                         instrument.
                                         """)

            self.add_parameter('demod{}_phaseshift'.format(demod),
                               label='Phase shift',
                               unit='degrees',
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 1, 'phaseshift'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 1, 'phaseshift'),
                               vals=vals.Numbers(-180, 180),
                               )

            self.add_parameter('demod{}_signalin'.format(demod),
                               label='Signal input',
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 0,'adcselect'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 0, 'adcselect'),
                               )

            self.add_parameter('demod{}_sinc'.format(demod),
                               label='Sinc filter',
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 0, 'sinc'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 0, 'sinc'),
                               val_mapping={'ON': 1, 'OFF': 0},
                               vals=vals.Enum('ON', 'OFF')
                               )

            self.add_parameter('demod{}_streaming'.format(demod),
                               label='Data streaming',
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 0, 'enable'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 0, 'enable'),
                               val_mapping={'ON': 1, 'OFF': 0},
                               vals=vals.Enum('ON', 'OFF')
                               )

            self.add_parameter('demod{}_trigger'.format(demod),
                               label='Trigger',
                               get_cmd=partial(self._getter, 'demods',
                                               demod-1, 0, 'trigger'),
                               set_cmd=partial(self._setter, 'demods',
                                               demod-1, 0, 'trigger'),
                               )

            self.add_parameter('demod{}_sample'.format(demod),
                               label='Demod sample',
                               get_cmd=partial(self._getter, 'demods',
                                               demod - 1, 2, 'sample'),
                               snapshot_value=False
                               )

            for demod_param in ['x', 'y', 'R', 'phi']:
                if demod_param in ('x', 'y', 'R'):
                    unit = 'V'
                else:
                    unit = 'deg'
                self.add_parameter('demod{}_{}'.format(demod, demod_param),
                                   label='Demod {} {}'.format(demod, demod_param),
                                   get_cmd=partial(self._get_demod_sample,
                                                   demod - 1, demod_param),
                                   snapshot_value=False,
                                   unit=unit
                                   )

        ########################################
        # SIGNAL INPUTS

        for sigin in range(1, 3):

            self.add_parameter('signal_input{}_range'.format(sigin),
                               label='Input range',
                               set_cmd=partial(self._setter, 'sigins',
                                               sigin-1, 1, 'range'),
                               get_cmd=partial(self._getter, 'sigins',
                                               sigin-1, 1, 'range'),
                               unit='V')

            self.add_parameter('signal_input{}_AC'.format(sigin),
                               label='AC coupling',
                               set_cmd=partial(self._setter,'sigins',
                                               sigin-1, 0, 'ac'),
                               get_cmd=partial(self._getter, 'sigins',
                                               sigin-1, 0, 'ac'),
                               val_mapping={'ON': 1, 'OFF': 0},
                               vals=vals.Enum('ON', 'OFF')
                               )

            self.add_parameter('signal_input{}_impedance'.format(sigin),
                               label='Input impedance',
                               set_cmd=partial(self._setter, 'sigins',
                                                sigin-1, 0, 'imp50'),
                               get_cmd=partial(self._getter, 'sigins',
                                               sigin-1, 0, 'imp50'),
                               val_mapping={50: 1, 1000: 0},
                               vals=vals.Enum(50, 1000)
                               )

            self.add_parameter('signal_input{}_diff'.format(sigin),
                               label='Input signal subtraction',
                               set_cmd=partial(self._setter, 'sigins',
                                                sigin-1, 0, 'diff'),
                               get_cmd=partial(self._getter, 'sigins',
                                               sigin-1, 0, 'diff')
                              )

        ########################################
        # SIGNAL OUTPUTS
        for sigout in range(1,3):

            self.add_parameter('signal_output{}_on'.format(sigout),
                                label='Turn signal output on and off.',
                                set_cmd=partial(self._sigout_setter,
                                                sigout-1, 0, 'on'),
                                get_cmd=partial(self._sigout_getter,
                                                sigout-1, 0, 'on'),
                                val_mapping={'ON': 1, 'OFF': 0},
                                vals=vals.Enum('ON', 'OFF') )

            amp_node = f'amplitudes/{out_map[sigout]}'
            self.add_parameter('signal_output{}_amplitude'.format(sigout),
                                label='Signal output amplitude',
                                set_cmd=partial(self._sigout_setter,
                                                sigout-1, 1, amp_node),
                                get_cmd=partial(self._sigout_getter,
                                               sigout-1, 1, amp_node),
                                unit='V')

            self.add_parameter('signal_output{}_ampdef'.format(sigout),
                                get_cmd=None, set_cmd=None,
                                initial_value='Vpk',
                                label="Signal output amplitude's definition",
                                vals=vals.Enum('Vpk','Vrms', 'dBm'))

            self.add_parameter('signal_output{}_range'.format(sigout),
                                label='Signal output range',
                                set_cmd=partial(self._sigout_setter,
                                                sigout-1, 1, 'range'),
                                get_cmd=partial(self._sigout_getter,
                                                sigout-1, 1, 'range'))

            self.add_parameter('signal_output{}_offset'.format(sigout),
                                label='Signal output offset',
                                set_cmd=partial(self._sigout_setter,
                                                sigout-1, 1, 'offset'),
                                get_cmd=partial(self._sigout_getter,
                                                sigout-1, 1, 'offset'),
                                unit='V')

            out_enable_node = f'enables/{out_map[sigout]}'
            self.add_parameter('signal_output{}_enable'.format(sigout),
                                label="Enable signal output's amplitude.",
                                set_cmd=partial(self._sigout_setter,
                                                sigout-1, 0,
                                                out_enable_node),
                                get_cmd=partial(self._sigout_getter,
                                                sigout-1, 0,
                                                out_enable_node),
                                val_mapping={'ON': 1, 'OFF': 0},
                                vals=vals.Enum('ON', 'OFF') )

    def _setter(self, module: str, number: int, setting: str, value_type: ValueType):
        """
        General function to set/send settings to the device.

        The module (e.g demodulator, input, output,..) number is counted in a
        ONE indexed fashion.

        This function return a function that do the correct setting.

        Args:
            module (str): The module (eg. demodulator, input, output, ..)
                to set.
            number (int): Module's index
            setting (str): The module's setting to set.
            value_type (ValueType): The value type to set.
        """

        function_table = {
            ValueType.INT: self.daq.setInt,
            ValueType.DOUBLE: self.daq.setDouble,
        }
        set_function = function_table[value_type]

        setstr = f'/{self.device}/{module}/{number-1}/{setting}'

        return partial(set_function, setstr)

    def _getter(self, module: str, number: int, setting: str, value_type: ValueType):
        """
        General function to get settings to the device.

        The module (e.g demodulator, input, output,..) number is counted in a
        zero indexed fashion.

        This function return a function that return the correct setting.

        Args:
            module (str): The module (eg. demodulator, input, output, ..)
                to set.
            number (int): Module's index
            setting (str): The module's setting to set.
            value_type (ValueType): The value type to set.
        """

        function_table = {
            ValueType.INT: self.daq.getInt,
            ValueType.DOUBLE: self.daq.getDouble,
            ValueType.SAMPLE: self.daq.getSample
        }
        get_function = function_table[value_type]

        getstr = f'/{self.device}/{module}/{number-1}/{setting}'

        return partial(get_function, getstr)


    def _get_demod_sample(self, number: int, demod_param: str) -> float:
        log.debug("getting demod %s param %s", number, demod_param)
        mode = 2
        module = 'demods'
        setting = 'sample'
        if demod_param not in ['x', 'y', 'R', 'phi']:
            raise RuntimeError("Invalid demodulator parameter")
        datadict = cast(dict, self._getter(module, number, mode, setting))
        datadict['R'] = np.abs(datadict['x'] + 1j * datadict['y'])
        datadict['phi'] = np.angle(datadict['x'] + 1j * datadict['y'], deg=True)
        return datadict[demod_param]

    def _sigout_setter(self, number, mode, setting, value):
        """
        Function to set signal output's settings. A specific setter function is
        needed as parameters depend on each other and need to be checked and
        updated accordingly.

        Args:
            number (int):
            mode (bool): Indicating whether we are asking for an int or double
            setting (str): The module's setting to set.
            value (Union[int, float]): The value to set the setting to.
        """

        # convenient reference
        params = self.parameters

        def amp_valid():
            nonlocal value
            toget = params['signal_output{}_ampdef'.format(number+1)]
            ampdef_val = toget.get()

            autorange_name = 'signal_output{}_autorange'.format(number+1)
            if autorange_name in params.keys():
                toget = params[autorange_name]
                autorange_val = toget.get()
            else:
                autorange_val = 'OFF'

            if autorange_val == 'ON':
                toget = params['signal_output{}_imp50'.format(number+1)]
                imp50_val = toget.get()
                imp50_dic = {'OFF': 1.5, 'ON': 0.75}
                range_val = imp50_dic[imp50_val]

            else:
                so_range = params['signal_output{}_range'.format(number+1)].get()
                range_val = round(so_range, 3)

            amp_val_dict={'Vpk': lambda value: value,
                          'Vrms': lambda value: value*sqrt(2),
                          'dBm': lambda value: 10**((value-10)/20)
                         }

            if -range_val < amp_val_dict[ampdef_val](value) > range_val:
                raise ValueError('Signal Output:'
                                 + ' Amplitude too high for chosen range.')
            value /= range_val
            value = amp_val_dict[ampdef_val](value)

        def offset_valid():
            nonlocal value
            nonlocal number
            range_val = params['signal_output{}_range'.format(number+1)].get()
            range_val = round(range_val, 3)
            amp_val = params['signal_output{}_amplitude'.format(number+1)].get()
            amp_val = round(amp_val, 3)
            if -range_val< value+amp_val > range_val:
                raise ValueError('Signal Output: Offset too high for '
                                 'chosen range.')
            value /= range_val

        def range_valid():
            nonlocal value
            nonlocal number

            #Don't validate again if another validator is set
            if hasattr(params[f'signal_output{number+1}_range'], 'vals'):
                return

            toget = params['signal_output{}_autorange'.format(number+1)]
            autorange_val = toget.get()
            imp50_val = params['signal_output{}_imp50'.format(number+1)].get()
            imp50_dic = {'OFF': [1.5, 0.15], 'ON': [0.75, 0.075]}

            if autorange_val == "ON":
                raise ValueError('Signal Output :'
                                ' Cannot set range as autorange is turned on.')

            if value not in imp50_dic[imp50_val]:
                raise ValueError('Signal Output: Choose a valid range:'
                                 '[0.75, 0.075] if imp50 is on, [1.5, 0.15]'
                                 ' otherwise.')

        def update_range_offset_amp():
            range_val = params['signal_output{}_range'.format(number+1)].get()
            offset_val = params['signal_output{}_offset'.format(number+1)].get()
            amp_val = params['signal_output{}_amplitude'.format(number+1)].get()
            if -range_val < offset_val + amp_val > range_val:
                #The GUI would allow higher values but it would clip the signal.
                raise ValueError('Signal Output: Amplitude and/or '
                                 'offset out of range.')

        def update_offset():
            self.parameters['signal_output{}_offset'.format(number+1)].get()

        def update_amp():
            self.parameters['signal_output{}_amplitude'.format(number+1)].get()

        def update_range():
            self.parameters['signal_output{}_range'.format(number+1)].get()

        #Do the validation of the parameter
        dynamic_validation = {'range': range_valid,
                              'amplitudes': amp_valid,
                              'offset': offset_valid}
        setbase = setting.split('/')[0]
        if setbase in dynamic_validation:
            dynamic_validation[setbase]()

        #Set the value
        self._setter('sigouts', number, mode, setting, value)

        # parameters which will potentially change other parameters
        # so we update all the relevant ones
        changing_param = {'imp50': [update_range_offset_amp, update_range],
                          'autorange': [update_range],
                          'range': [update_offset, update_amp],
                          'amplitudes': [update_range, update_amp],
                          'offset': [update_range]
                         }
        if setbase in changing_param:
            _ = [f() for f in changing_param[setbase]]

    def _sigout_getter(self, number, mode, setting):
        """
        Function to query the settings of signal outputs. Specific setter
        function is needed as parameters depend on each other and need to be
        checked and updated accordingly.

        Args:
            number (int):
            mode (bool): Indicating whether we are asking for an int or double
            setting (str): The module's setting to set.
        """

        # convenient reference
        params = self.parameters

        value = self._getter('sigouts', number, mode, setting)

        #Correct values for range, if needed
        setbase = setting.split('/')[0]
        if setbase.startswith('amplitudes') or setbase == 'offset':
            range_val = params['signal_output{}_range'.format(number+1)].get()
            value *= range_val

        # Adjust value according to amplitude definition
        if setbase.startswith('amplitudes'):
            toget = params['signal_output{}_ampdef'.format(number+1)]
            ampdef_val = toget.get()
            amp_val_dict={'Vpk': lambda value: value,
                          'Vrms': lambda value: value/sqrt(2),
                          'dBm': lambda value: 10+20*log10(value)
                         }
            value = amp_val_dict[ampdef_val](value)

        return value

    def _list_nodes(self, node):
        """
        Returns a list with all nodes in the sub-tree below the specified node.

        Args:
            node (str): Module of which you want to know the parameters.
        return:
            list of sub-nodes
        """
        node_list = self.daq.getList('/{}/{}/'.format(self.device, node))
        return node_list

    def close(self):
        """
        Override of the base class' close function
        """
        self.daq.disconnect()
        super().close()
