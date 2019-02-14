import time
import logging
import numpy as np
from functools import partial
from math import sqrt, log10

from typing import Callable, List, Union, cast

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

class Scope(MultiParameter):
    """
    Parameter class for the ZI UHF-LI Scope Channel 1

    The .get method launches an acquisition and returns a tuple of two
    np.arrays
    FFT mode is NOT supported.

    Attributes:
        names (tuple): Tuple of strings containing the names of the sweep
          signals (to be measured)
        units (tuple): Tuple of strings containg the units of the signals
        shapes (tuple): Tuple of tuples each containing the Length of a
          signal.
        setpoints (tuple): Tuple of N copies of the sweep x-axis points,
          where N is he number of measured signals
        setpoint_names (tuple): Tuple of N identical strings with the name
          of the sweep x-axis.
    """
    def __init__(self, name, instrument, **kwargs):
        # The __init__ requires that we supply names and shapes,
        # but there is no way to know what they could be known at this time.
        # They are updated via build_scope.
        super().__init__(name, names=('',), shapes=((1,),), **kwargs)
        self._instrument = instrument
        self._scopeactions = []  # list of callables

    def add_post_trigger_action(self, action: Callable) -> None:
        """
        Add an action to be performed immediately after the trigger
        has been armed. The action must be a callable taking zero
        arguments
        """
        if action not in self._scopeactions:
            self._scopeactions.append(action)

    @property
    def post_trigger_actions(self) -> List[Callable]:
        return self._scopeactions

    def prepare_scope(self):
        """
        Prepare the scope for a measurement. Must immediately preceed a
        measurement.
        """

        log.info('Preparing the scope')

        # A convenient reference
        params = self._instrument.parameters

        # First figure out what the user has asked for
        chans = {1: (True, False), 2: (False, True), 3: (True, True)}
        channels = chans[params['scope_channels'].get()]

        npts = params['scope_length'].get()
        # Find out whether segments are enabled
        if params['scope_segments'].get() == 'ON':
            segs = params['scope_segments_count'].get()
        else:
            segs = 1

        inputunits = {'Signal Input 1': 'V',
                      'Signal Input 2': 'V',
                      'Trig Input 1': 'V',
                      'Trig Input 2': 'V',
                      'Aux Output 1': 'V',
                      'Aux Output 2': 'V',
                      'Aux Output 3': 'V',
                      'Aux Output 4': 'V',
                      'Aux In 1 Ch 1': 'V',
                      'Aux In 1 Ch 2': 'V',
                      'Osc phi Demod 4': '°',
                      'osc phi Demod 8': '°',
                      'AU Cartesian 1': 'arb. un.',
                      'AU Cartesian 2': 'arb. un',
                      'AU Polar 1': 'arb. un.',
                      'AU Polar 2': 'arb. un.',
                      'Demod 1 X': 'V',
                      'Demod 1 Y': 'V',
                      'Demod 1 R': 'V',
                      'Demod 1 Phase':  '°',
                      'Demod 2 X': 'V',
                      'Demod 2 Y': 'V',
                      'Demod 2 R': 'V',
                      'Demod 2 Phase': '°',
                      'Demod 3 X': 'V',
                      'Demod 3 Y': 'V',
                      'Demod 3 R': 'V',
                      'Demod 3 Phase': '°',
                      'Demod 4 X': 'V',
                      'Demod 4 Y': 'V',
                      'Demod 4 R': 'V',
                      'Demod 4 Phase': '°',
                      'Demod 5 X': 'V',
                      'Demod 5 Y': 'V',
                      'Demod 5 R': 'V',
                      'Demod 5 Phase': '°',
                      'Demod 6 X': 'V',
                      'Demod 6 Y': 'V',
                      'Demod 6 R': 'V',
                      'Demod 6 Phase': '°',
                      'Demod 7 X': 'V',
                      'Demod 7 Y': 'V',
                      'Demod 7 R': 'V',
                      'Demod 7 Phase': '°',
                      'Demod 8 X': 'V',
                      'Demod 8 Y': 'V',
                      'Demod 8 R': 'V',
                      'Demod 8 Phase': '°',
                      }

        #TODO: what are good names?
        inputnames = {'Signal Input 1': 'Sig. In 1',
                      'Signal Input 2': 'Sig. In 2',
                      'Trig Input 1': 'Trig. In 1',
                      'Trig Input 2': 'Trig. In 2',
                      'Aux Output 1': 'Aux. Out 1',
                      'Aux Output 2': 'Aux. Out 2',
                      'Aux Output 3': 'Aux. Out 3',
                      'Aux Output 4': 'Aux. Out 4',
                      'Aux In 1 Ch 1': 'Aux. In 1 Ch 1',
                      'Aux In 1 Ch 2': 'Aux. In 1 Ch 2',
                      'Osc phi Demod 4': 'Demod. 4 Phase',
                      'osc phi Demod 8': 'Demod. 8 Phase',
                      'AU Cartesian 1': 'AU Cartesian 1',
                      'AU Cartesian 2': 'AU Cartesian 2',
                      'AU Polar 1': 'AU Polar 1',
                      'AU Polar 2': 'AU Polar 2',
                      'Demod 1 X': 'Demodulator 1 X',
                      'Demod 1 Y': 'Demodulator 1 Y',
                      'Demod 1 R': 'Demodulator 1 R',
                      'Demod 1 Phase':  'Demodulator 1 Phase',
                      'Demod 2 X': 'Demodulator 2 X',
                      'Demod 2 Y': 'Demodulator 2 Y',
                      'Demod 2 R': 'Demodulator 2 R',
                      'Demod 2 Phase': 'Demodulator 2 Phase',
                      'Demod 3 X': 'Demodulator 3 X',
                      'Demod 3 Y': 'Demodulator 3 Y',
                      'Demod 3 R': 'Demodulator 3 R',
                      'Demod 3 Phase': 'Demodulator 3 Phase',
                      'Demod 4 X': 'Demodulator 4 X',
                      'Demod 4 Y': 'Demodulator 4 Y',
                      'Demod 4 R': 'Demodulator 4 R',
                      'Demod 4 Phase': 'Demodulator 4 Phase',
                      'Demod 5 X': 'Demodulator 5 X',
                      'Demod 5 Y': 'Demodulator 5 Y',
                      'Demod 5 R': 'Demodulator 5 R',
                      'Demod 5 Phase': 'Demodulator 5 Phase',
                      'Demod 6 X': 'Demodulator 6 X',
                      'Demod 6 Y': 'Demodulator 6 Y',
                      'Demod 6 R': 'Demodulator 6 R',
                      'Demod 6 Phase': 'Demodulator 6 Phase',
                      'Demod 7 X': 'Demodulator 7 X',
                      'Demod 7 Y': 'Demodulator 7 Y',
                      'Demod 7 R': 'Demodulator 7 R',
                      'Demod 7 Phase': 'Demodulator 7 Phase',
                      'Demod 8 X': 'Demodulator 8 X',
                      'Demod 8 Y': 'Demodulator 8 Y',
                      'Demod 8 R': 'Demodulator 8 R',
                      'Demod 8 Phase': 'Demodulator 8 Phase',
                      }

        # Make the basic setpoints (the x-axis)
        duration = params['scope_duration'].get()
        delay = params['scope_trig_delay'].get()
        starttime = params['scope_trig_reference'].get()*0.01*duration + delay
        stoptime = starttime + duration

        setpointlist = tuple(np.linspace(starttime, stoptime, npts))  # x-axis
        spname = 'Time'
        namestr = "scope_channel{}_input".format(1)
        name1 = inputnames[params[namestr].get()]
        unit1 = inputunits[params[namestr].get()]
        namestr = "scope_channel{}_input".format(2)
        name2 = inputnames[params[namestr].get()]
        unit2 = inputunits[params[namestr].get()]

        self.setpoints = ((tuple(range(segs)), (setpointlist,)*segs),)*2
        #self.setpoints = ((setpointlist,)*segs,)*2
        self.setpoint_names = (('Segments', 'Time'), ('Segments', 'Time'))
        self.names = (name1, name2)
        self.units = (unit1, unit2)
        self.labels = ('Scope channel 1', 'Scope channel 2')
        self.shapes = ((segs, npts), (segs, npts))

        self._instrument.daq.sync()
        self._instrument.scope_correctly_built = True

    def get_raw(self):
        """
        Acquire data from the scope.

        Returns:
            tuple: Tuple of two n X m arrays where n is the number of segments
                and m is the number of points in the scope trace.

        Raises:
            ValueError: If the scope has not been prepared by running the
                prepare_scope function.
        """
        t_start = time.monotonic()
        log.info('Scope get method called')

        if not self._instrument.scope_correctly_built:
            raise ValueError('Scope not properly prepared. Please run '
                             'prepare_scope before measuring.')

        # A convenient reference
        params = self._instrument.parameters
        #
        chans = {1: (True, False), 2: (False, True), 3: (True, True)}
        channels = chans[params['scope_channels'].get()]

        if params['scope_trig_holdoffmode'].get_latest() == 'events':
            raise NotImplementedError('Scope trigger holdoff in number of '
                                      'events not supported. Please specify '
                                      'holdoff in seconds.')

        #######################################################
        # The following steps SEEM to give the correct result

        # Make sure all settings have taken effect
        self._instrument.daq.sync()

        # Calculate the time needed for the measurement. We often have failed
        # measurements, so a timeout is needed.
        if params['scope_segments'].get() == 'ON':
            segs = params['scope_segments_count'].get()
        else:
            segs = 1
        deadtime = params['scope_trig_holdoffseconds'].get_latest()
        # We add one second to account for latencies and random delays
        meas_time = segs*(params['scope_duration'].get()+deadtime)+1
        npts = params['scope_length'].get()

        zi_error = True
        error_counter = 0
        num_retries = 10
        timedout = False
        while (zi_error or timedout) and error_counter < num_retries:
            # one shot per trigger. This needs to be set every time
            # a the scope is enabled as below using scope_runstop
            try:
                # we wrap this in try finally to ensure that
                # scope.finish is always called even if the
                # measurement is interrupted
                self._instrument.daq.setInt('/{}/scopes/0/single'.format(self._instrument.device), 1)


                scope = self._instrument.scope
                scope.set('scopeModule/clearhistory', 1)

                # Start the scope triggering/acquiring
                # set /dev/scopes/0/enable to 1
                params['scope_runstop'].set('run')

                self._instrument.daq.sync()

                log.debug('Starting ZI scope acquisition.')
                # Start something... hauling data from the scopeModule?
                scope.execute()

                # Now perform actions that may produce data, e.g. running an AWG
                for action in self._scopeactions:
                    action()

                starttime = time.time()
                timedout = False

                progress = scope.progress()
                while progress < 1:
                    log.debug('Scope progress is {}'.format(progress))
                    progress = scope.progress()
                    time.sleep(0.1)  # This while+sleep is how ZI engineers do it
                    if (time.time()-starttime) > 20*meas_time+1:
                        timedout = True
                        break
                metadata = scope.get("scopeModule/*")
                zi_error = bool(metadata['error'][0])

                # Stop the scope from running
                params['scope_runstop'].set('stop')

                if not (timedout or zi_error):
                    log.info('[+] ZI scope acquisition completed OK')
                    rawdata = scope.read()
                    if 'error' in rawdata:
                        zi_error = bool(rawdata['error'][0])
                    data = self._scopedataparser(rawdata, self._instrument.device,
                                                 npts, segs, channels)
                else:
                    log.warning('[-] ZI scope acquisition attempt {} '
                                'failed, Timeout: {}, Error: {}, '
                                'retrying'.format(error_counter, timedout, zi_error))
                    rawdata = None
                    data = (None, None)
                    error_counter += 1

                if error_counter >= num_retries:
                    log.error('[+] ZI scope acquisition failed, maximum number'
                              'of retries performed. No data returned')
                    raise RuntimeError('[+] ZI scope acquisition failed, maximum number'
                              'of retries performed. No data returned')
            finally:
                # cleanup and make ready for next scope acquisition
                scope.finish()

        t_stop = time.monotonic()
        log.info('scope get method returning after {} s'.format(t_stop -
                                                                t_start))
        return data

    @staticmethod
    def _scopedataparser(rawdata, deviceID, scopelength, segments, channels):
        """
        Cast the scope return value dict into a tuple.

        Args:
            rawdata (dict): The return of scopeModule.read()
            deviceID (str): The device ID string of the instrument.
            scopelength (int): The length of each segment
            segments (int): The number of segments
            channels (tuple): Tuple of two bools controlling what data to return
                (True, False) will return data for channel 1 etc.

        Returns:
            tuple: A 2-tuple of either None or np.array with dimensions
                segments x scopelength.
        """

        data = rawdata['{}'.format(deviceID)]['scopes']['0']['wave'][0][0]
        if channels[0]:
            ch1data = data['wave'][0].reshape(segments, scopelength)
        else:
            ch1data = None
        if channels[1]:
            ch2data = data['wave'][1].reshape(segments, scopelength)
        else:
            ch2data = None

        return (ch1data, ch2data)
    

class ZIUHF_Scope(Instrument)
    def __init__(self, name: str, device_ID: str, **kwargs) -> None:
        """
        Create an instance of the instrument.

        Args:
            name (str): The internal QCoDeS name of the instrument
            device_ID (str): The device name as listed in the web server, in the form 'devXXXX'
        """

        super().__init__(name, **kwargs)
        zisession = zhinst.utils.create_api_session(device_ID, api_level=5)
        (self.daq, self.device, self.props) = zisession

        self.daq.setDebugLevel(3)
        # create (instantiate) an instance of the scope node
        self.scope = self.daq.scopeModule()
        self.scope.subscribe('/{}/scopes/0/wave'.format(self.device))


        ########################################
        # SCOPE PARAMETERS
        # default parameters:

        # This parameter corresponds to the Run/Stop button in the GUI
        self.add_parameter('scope_runstop',
                           label='Scope run state',
                           set_cmd=partial(self._setter, 'scopes', 0, 0,
                                           'enable'),
                           get_cmd=partial(self._getter, 'scopes', 0, 0,
                                           'enable'),
                           val_mapping={'run': 1, 'stop': 0},
                           vals=vals.Enum('run', 'stop'),
                           docstring=('This parameter corresponds to the '
                                      'run/stop button in the GUI.'))

        self.add_parameter('scope_mode',
                            label="Scope's mode: time or frequency domain.",
                            set_cmd=partial(self._scope_setter, 1, 0,
                                            'mode'),
                            get_cmd=partial(self._scope_getter, 'mode'),
                            val_mapping={'Time Domain': 1,
                                         'Freq Domain FFT': 3},
                            vals=vals.Enum('Time Domain', 'Freq Domain FFT')
                            )

        # 1: Channel 1 on, Channel 2 off.
        # 2: Channel 1 off, Channel 2 on,
        # 3: Channel 1 on, Channel 2 on.
        self.add_parameter('scope_channels',
                           label='Recorded scope channels',
                           set_cmd=partial(self._scope_setter, 0, 0,
                                           'channel'),
                           get_cmd=partial(self._getter, 'scopes', 0,
                                           0, 'channel'),
                           vals=vals.Enum(1, 2, 3)
                           )

        self._samplingrate_codes = {'1.80 GHz': 0,
                                   '900 MHz': 1,
                                   '450 MHz': 2,
                                   '225 MHz': 3,
                                   '113 MHz': 4,
                                   '56.2 MHz': 5,
                                   '28.1 MHz': 6,
                                   '14.0 MHz': 7,
                                   '7.03 MHz': 8,
                                   '3.50 MHz': 9,
                                   '1.75 MHz': 10,
                                   '880 kHz': 11,
                                   '440 kHz': 12,
                                   '220 kHz': 13,
                                   '110 kHz': 14,
                                   '54.9 kHz': 15,
                                   '27.5 kHz': 16}

        self.add_parameter('scope_samplingrate',
                            label="Scope's sampling rate",
                            set_cmd=partial(self._scope_setter, 0, 0,
                                            'time'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            0, 'time'),
                            val_mapping=self._samplingrate_codes,
                            vals=vals.Enum(*list(self._samplingrate_codes.keys()))
                            )

        self.add_parameter('scope_length',
                            label="Length of scope trace (pts)",
                            set_cmd=partial(self._scope_setter, 0, 1,
                                            'length'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            1, 'length'),
                            vals=vals.Numbers(4096, 128000000),
                            get_parser=int
                            )

        self.add_parameter('scope_duration',
                           label="Scope trace duration",
                           set_cmd=partial(self._scope_setter, 0, 0,
                                           'duration'),
                           get_cmd=partial(self._scope_getter,
                                           'duration'),
                           vals=vals.Numbers(2.27e-6,4.660e3),
                           unit='s'
                           )

        # Map the possible input sources to LabOne's IDs.
        # The IDs can be seen in log file of LabOne UI
        inputselect = {'Signal Input 1': 0,
                       'Signal Input 2': 1,
                       'Trig Input 1': 2,
                       'Trig Input 2': 3,
                       'Aux Output 1': 4,
                       'Aux Output 2': 5,
                       'Aux Output 3': 6,
                       'Aux Output 4': 7,
                       'Aux In 1 Ch 1': 8,
                       'Aux In 1 Ch 2': 9,
                       'Osc phi Demod 4': 10,
                       'Osc phi Demod 8': 11,
                       'AU Cartesian 1': 112,
                       'AU Cartesian 2': 113,
                       'AU Polar 1': 128,
                       'AU Polar 2': 129,
                       }
        # Add all 8 demodulators and their respective parameters
        # to inputselect as well.
        # Numbers correspond to LabOne IDs, taken from UI log.
        for demod in range(1,9):
            inputselect['Demod {} X'.format(demod)] = 15+demod
            inputselect['Demod {} Y'.format(demod)] = 31+demod
            inputselect['Demod {} R'.format(demod)] = 47+demod
            inputselect['Demod {} Phase'.format(demod)] = 63+demod

        for channel in range(1,3):
            self.add_parameter('scope_channel{}_input'.format(channel),
                            label=("Scope's channel {}".format(channel) +
                                   " input source"),
                            set_cmd=partial(self._scope_setter, 0, 0,
                                            ('channels/{}/'.format(channel-1) +
                                             'inputselect')),
                            get_cmd=partial(self._getter, 'scopes', 0, 0,
                                            ('channels/{}/'.format(channel-1) +
                                             'inputselect')),
                            val_mapping=inputselect,
                            vals=vals.Enum(*list(inputselect.keys()))
                            )

        self.add_parameter('scope_average_weight',
                            label="Scope Averages",
                            set_cmd=partial(self._scope_setter, 1, 0,
                                            'averager/weight'),
                            get_cmd=partial(self._scope_getter,
                                            'averager/weight'),
                            vals=vals.Numbers(min_value=1)
                            )

        self.add_parameter('scope_trig_enable',
                            label="Enable triggering for scope readout",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            0, 'trigenable'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            0, 'trigenable'),
                            val_mapping={'ON': 1, 'OFF': 0},
                            vals=vals.Enum('ON', 'OFF')
                            )

        self.add_parameter('scope_trig_signal',
                            label="Trigger signal source",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            0, 'trigchannel'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            0, 'trigchannel'),
                            val_mapping=inputselect,
                            vals=vals.Enum(*list(inputselect.keys()))
                            )

        slopes = {'None': 0, 'Rise': 1, 'Fall': 2, 'Both': 3}

        self.add_parameter('scope_trig_slope',
                            label="Scope's triggering slope",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            0, 'trigslope'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            0, 'trigslope'),
                            val_mapping=slopes,
                            vals=vals.Enum(*list(slopes.keys()))
                            )

        # TODO: figure out how value/percent works for the trigger level
        self.add_parameter('scope_trig_level',
                            label="Scope trigger level",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            1, 'triglevel'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            1, 'triglevel'),
                            vals=vals.Numbers()
                            )

        self.add_parameter('scope_trig_hystmode',
                            label="Enable triggering for scope readout.",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            0, 'trighysteresis/mode'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            0, 'trighysteresis/mode'),
                            val_mapping={'absolute': 0, 'relative': 1},
                            vals=vals.Enum('absolute', 'relative')
                            )

        self.add_parameter('scope_trig_hystrelative',
                            label="Trigger hysteresis, relative value in %",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            1, 'trighysteresis/relative'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            1, 'trighysteresis/relative'),
                            # val_mapping= lambda x: 0.01*x,
                            vals=vals.Numbers(0)
                            )

        self.add_parameter('scope_trig_hystabsolute',
                            label="Trigger hysteresis, absolute value",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            1, 'trighysteresis/absolute'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            1, 'trighysteresis/absolute'),
                            vals=vals.Numbers(0, 20)
                            )

        triggates = {'Trigger In 3 High': 0, 'Trigger In 3 Low': 1,
                     'Trigger In 4 High': 2, 'Trigger In 4 Low': 3}
        self.add_parameter('scope_trig_gating_source',
                           label='Scope trigger gating source',
                           set_cmd=partial(self._setter, 'scopes', 0, 0,
                                           'triggate/inputselect'),
                           get_cmd=partial(self._getter, 'scopes', 0, 0,
                                           'triggate/inputselect'),
                           val_mapping=triggates,
                           vals=vals.Enum(*list(triggates.keys()))
                           )

        self.add_parameter('scope_trig_gating_enable',
                           label='Scope trigger gating ON/OFF',
                           set_cmd=partial(self._setter, 'scopes', 0, 0,
                                           'triggate/enable'),
                           get_cmd=partial(self._getter, 'scopes', 0, 0,
                                           'triggate/enable'),
                           val_mapping = {'ON': 1, 'OFF': 0},
                           vals=vals.Enum('ON', 'OFF'))

        # make this a slave parameter off scope_holdoff_seconds
        # and scope_holdoff_events
        self.add_parameter('scope_trig_holdoffmode',
                            label="Scope trigger holdoff mode",
                            set_cmd=partial(self._setter, 'scopes', 0,
                                            0, 'trigholdoffmode'),
                            get_cmd=partial(self._getter, 'scopes', 0,
                                            0, 'trigholdoffmode'),
                            val_mapping={'s': 0, 'events': 1},
                            vals=vals.Enum('s', 'events')
                            )

        self.add_parameter('scope_trig_holdoffseconds',
                           label='Scope trigger holdoff',
                           set_cmd=partial(self._scope_setter, 0, 1,
                                           'trigholdoff'),
                           get_cmd=partial(self._getter, 'scopes', 0,
                                           1, 'trigholdoff'),
                           unit='s',
                           vals=vals.Numbers(20e-6, 10)
                           )

        self.add_parameter('scope_trig_reference',
                           label='Scope trigger reference',
                           set_cmd=partial(self._scope_setter, 0, 1,
                                           'trigreference'),
                           get_cmd=partial(self._getter, 'scopes', 0,
                                           1, 'trigreference'),
                           vals=vals.Numbers(0, 100)
                           )

        # TODO: add validation. What's the minimal/maximal delay?
        self.add_parameter('scope_trig_delay',
                           label='Scope trigger delay',
                           set_cmd=partial(self._scope_setter, 0, 1,
                                           'trigdelay'),
                           get_cmd=partial(self._getter, 'scopes', 0, 1,
                                           'trigdelay'),
                           unit='s')

        self.add_parameter('scope_segments',
                           label='Enable/disable segments',
                           set_cmd=partial(self._scope_setter, 0, 0,
                                           'segments/enable'),
                           get_cmd=partial(self._getter, 'scopes', 0,
                                           0, 'segments/enable'),
                           val_mapping={'OFF': 0, 'ON': 1},
                           vals=vals.Enum('ON', 'OFF')
                           )

        self.add_parameter('scope_segments_count',
                           label='No. of segments returned by scope',
                           set_cmd=partial(self._setter, 'scopes', 0, 1,
                                           'segments/count'),
                           get_cmd=partial(self._getter, 'scopes', 0, 1,
                                          'segments/count'),
                           vals=vals.Ints(1, 32768),
                           get_parser=int
                           )

        self.add_function('scope_reset_avg',
                            call_cmd=partial(self.scope.set,
                                             'scopeModule/averager/restart', 1),
                            )

        ########################################
        # THE SCOPE ITSELF
        self.add_parameter('Scope',
                           parameter_class=Scope,
                           )


    def _scope_setter(self, scopemodule, mode, setting, value):
        """
        set_cmd for all scope parameters. The value and setting are saved in
        a dictionary which is read by the Scope parameter's build_scope method
        and only then sent to the instrument.

        Args:
            scopemodule (int): Indicates whether this is a setting of the
                scopeModule or not. 1: it is a scopeModule setting,
                0: it is not.
            mode (int): Indicates whether we are setting an int or a float.
                0: int, 1: float. NOTE: Ignored if scopemodule==1.
            setting (str): The setting, e.g. 'length'.
            value (Union[int, float, str]): The value to set.
        """
        # Because setpoints need to be built
        self.scope_correctly_built = False

        # Some parameters are linked to each other in specific ways
        # Therefore, we need special actions for setting these parameters

        SRtranslation = {'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9,
                         'khz': 1e3, 'Mhz': 1e6, 'Ghz': 1e9}

        def setlength(value):
            # TODO: add validation. The GUI seems to correect this value
            self.daq.setDouble('/{}/scopes/0/length'.format(self.device),
                               value)
            SR_str = self.parameters['scope_samplingrate'].get()
            (number, unit) = SR_str.split(' ')
            SR = float(number)*SRtranslation[unit]
            self.parameters['scope_duration']._save_val(value/SR)
            self.daq.setInt('/{}/scopes/0/length'.format(self.device), value)

        def setduration(value):
            # TODO: validation?
            SR_str = self.parameters['scope_samplingrate'].get()
            (number, unit) = SR_str.split(' ')
            SR = float(number)*SRtranslation[unit]
            N = int(np.round(value*SR))
            self.parameters['scope_length']._save_val(N)
            self.parameters['scope_duration']._save_val(value)
            self.daq.setInt('/{}/scopes/0/length'.format(self.device), N)

        def setholdoffseconds(value):
            self.parameters['scope_trig_holdoffmode'].set('s')
            self.daq.setDouble('/{}/scopes/0/trigholdoff'.format(self.device),
                               value)

        def setsamplingrate(value):
            # When the sample rate is changed, the number of points of the trace
            # remains unchanged and the duration changes accordingly
            newSR_str = dict(zip(self._samplingrate_codes.values(),
                                 self._samplingrate_codes.keys()))[value]
            (number, unit) = newSR_str.split(' ')
            newSR = float(number)*SRtranslation[unit]
            oldSR_str = self.parameters['scope_samplingrate'].get()
            (number, unit) = oldSR_str.split(' ')
            oldSR = float(number)*SRtranslation[unit]
            oldduration = self.parameters['scope_duration'].get()
            newduration = oldduration*oldSR/newSR
            self.parameters['scope_duration']._save_val(newduration)
            self.daq.setInt('/{}/scopes/0/time'.format(self.device), value)

        specialcases = {'length': setlength,
                        'duration': setduration,
                        'scope_trig_holdoffseconds': setholdoffseconds,
                        'time': setsamplingrate}

        if setting in specialcases:
            specialcases[setting](value)
            self.daq.sync()
            return
        else:
            # We have two different parameter types: those under
            # /scopes/0/ and those under scopeModule/
            if scopemodule:
                self.scope.set('scopeModule/{}'.format(setting), value)
            elif mode == 0:
                self.daq.setInt('/{}/scopes/0/{}'.format(self.device,
                                                         setting), value)
            elif mode == 1:
                self.daq.setDouble('/{}/scopes/0/{}'.format(self.device,
                                                            setting), value)
            return

    def _scope_getter(self, setting):
        """
        get_cmd for scopeModule parameters

        """
        # There are a few special cases
        SRtranslation = {'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9,
                         'khz': 1e3, 'Mhz': 1e6, 'Ghz': 1e9}

        def getduration():
            SR_str = self.parameters['scope_samplingrate'].get()
            (number, unit) = SR_str.split(' ')
            SR = float(number)*SRtranslation[unit]
            N = self.parameters['scope_length'].get()
            duration = N/SR
            return duration

        specialcases = {'duration': getduration}

        if setting in specialcases:
            value = specialcases[setting]()
        else:
            querystr = 'scopeModule/' + setting
            returndict =  self.scope.get(querystr)
            # The dict may have different 'depths' depending on the parameter.
            # The depth is encoded in the setting string (number of '/')
            keys = setting.split('/')[1:]

            while keys != []:
                key = keys.pop(0)
                returndict = returndict[key]
                rawvalue = returndict

            if isinstance(rawvalue, np.ndarray) and len(rawvalue) == 1:
                value = rawvalue[0]
            elif isinstance(rawvalue, list) and len(rawvalue) == 1:
                value = rawvalue[0]
            else:
                value = rawvalue

        return value

    def _setter(self, module, number, mode, setting, value):
        """
        General function to set/send settings to the device.

        The module (e.g demodulator, input, output,..) number is counted in a
        zero indexed fashion.

        Args:
            module (str): The module (eg. demodulator, input, output, ..)
                to set.
            number (int): Module's index
            mode (bool): Indicating whether we are setting an int or double
            setting (str): The module's setting to set.
            value (int/double): The value to set.
        """

        setstr = '/{}/{}/{}/{}'.format(self.device, module, number, setting)

        if mode == 0:
            self.daq.setInt(setstr, value)
        if mode == 1:
            self.daq.setDouble(setstr, value)

    def _getter(self, module: str, number: int,
                mode: int, setting: str) -> Union[float, int, str, dict]:
        """
        General get function for generic parameters. Note that some parameters
        use more specialised setter/getters.

        The module (e.g demodulator, input, output,..) number is counted in a
        zero indexed fashion.

        Args:
            module (str): The module (eg. demodulator, input, output, ..)
                we want to know the value of.
            number (int): Module's index
            mode (int): Indicating whether we are asking for an int or double.
                0: Int, 1: double, 2: Sample
            setting (str): The module's setting to set.
        returns:
            inquered value

        """

        querystr = '/{}/{}/{}/{}'.format(self.device, module, number, setting)
        log.debug("getting %s", querystr)
        if mode == 0:
            value = self.daq.getInt(querystr)
        elif mode == 1:
            value = self.daq.getDouble(querystr)
        elif mode == 2:
            value = self.daq.getSample(querystr)
        else:
            raise RuntimeError("Invalid mode supplied")
        # Weird exception, samplingrate returns a string
        return value

    def close(self):
        """
        Override of the base class' close function
        """
        self.scope.unsubscribe('/{}/scopes/0/wave'.format(self.device))
        self.scope.clear()
        self.daq.disconnect()
        super().close()
