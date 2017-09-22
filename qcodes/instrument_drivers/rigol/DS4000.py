
import numpy as np
from pyvisa.errors import VisaIOError
from functools import partial

from qcodes import VisaInstrument, validators as vals
from qcodes import InstrumentChannel, ChannelList
from qcodes import ArrayParameter
from qcodes.instrument.channel import InstrumentChannel, ChannelList

from collections import namedtuple

#TODO: convert call to long version


class ScopeArray(ArrayParameter):
    def __init__(self, name, instrument, channel, raw=False):
        super().__init__(name=name,
                         shape=(1400,),
                         label='Voltage',
                         unit='V',
                         setpoint_names=('Time', ),
                         setpoint_labels=('Time', ),
                         setpoint_units=('s',),
                         docstring='holds an array from scope')
        self.channel = channel
        self._instrument = instrument
        self.raw = raw
        self.max_read_step = 10

    def get(self):
        self.write(':WAV:FORM BYTE')                         # Set the data type for waveforms to "BYTE"
        self.write(':WAV:SOUR CHAN{}'.format(self.channel))  # Set read channel

        data_bin = b''
        if self.raw:
            self._instrument.stop()      # Stop acquisition
            self.write(':WAV:MODE RAW')  # Set RAW mode
            self.write(':WAV:RES')       # Resets the waveform data reading
            self.write(':WAV:BEG')       # Starts the waveform data reading

            for _ in range(self.max_read_step):
                status = self.ask(':WAV:STAT?').split(',')[0]
                self.write(':WAV:DATA?')
                data_bin += self.visa_handle.read_raw()

                if status == 'IDLE':
                    self.write(':WAV:END')
                    break
            else:
                raise ValueError('Communication error')

        else:
            self.write(':WAV:MODE NORM')  # Set normal mode
            self.write(':WAV:DATA?')  # Query data
            data_bin += self.visa_handle.read_raw()

        # Convert data to byte array
        data_bin = data_bin[11:]  # Strip header
        data_bin = data_bin.strip()  # Strip \n
        data_raw = np.fromstring(data_bin, dtype=np.uint8)  # Convert to an array

        # Convert byte array to real data
        p = self.get_preamble()
        data = (data_raw - p.yreference - p.yorigin) * p.yincrement

        # Generate time axis data
        xdata = np.linspace(p.xorigin, p.origin + p.xincrement * p.points, p.points)
        self.setpoints = (tuple(xdata),)
        self.shape = (p.points,)

        return data, xincrement

    def get_preamble(self):
        preamble_nt = namedtuple('preamble', ["format", "mode", "points", "count", "xincrement", "xorigin",
                                              "xreference", "yincrement", "yorigin", "yreference"])
        conv = lambda x: int(x) if x.isdigit() else float(x)

        preamble_raw = self.ask(':WAV:PRE?')
        preamble_num = [conv(x) for x in preamble_raw.strip().split(',')]
        preamble = preamble_nt(*preamble_num)

        return preamble


class RigolDS4000Channel(InstrumentChannel):

    def __init__(self, parent, name, channel):
        super().__init__(parent, name)

        self.add_parameter("amplitude",
                           get_cmd=":meas:vamp? chan{}".format(channel)
                          )
        self.add_parameter("vertical_scale",
                           get_cmd="chan{}:scale?".format(channel),
                           set_cmd="chan{}:scale ".format(channel) + "{}",
                           get_parser=float
                          )
        self.add_parameter('curvedata',
                           channel=channel,
                           parameter_class=ScopeArray,
                           raw=False
                           )
        self.add_parameter('curvedata_raw',
                           channel=channel,
                           parameter_class=ScopeArray,
                           raw=True
                           )

class DS4000(VisaInstrument):
    """
    This is the QCoDeS driver for the Rigol DS4000 series oscilloscopes.
    """

    def __init__(self, name, address, timeout=20, **kwargs):
        """
        Initialises the DS4000.

        Args:
            name (str): Name of the instrument used by QCoDeS
        address (string): Instrument address as used by VISA
            timeout (float): visa timeout, in secs. long default (180)
              to accommodate large waveforms
        """

        # Init VisaInstrument. device_clear MUST NOT be issued, otherwise communications hangs
        # due a bug in firmware
        super().__init__(name, address, timeout=timeout, **kwargs)  #device_clear=False, add when #752 is merged
        self.connect_message()

        # functions

        self.add_function('force_trigger',
                          call_cmd='TFOR',
                          docstring='Force trigger event')
        self.add_function('run',
                          call_cmd=':RUN',
                          docstring='Start acquisition')
        self.add_function('stop',
                          call_cmd=':STOP',
                          docstring='Stop acquisition')

        # general parameters
        self.add_parameter('trigger_type',
                           label='Type of the trigger',
                           get_cmd=':TRIG:MODE?',
                           set_cmd=':TRIG:MODE {}',
                           vals=vals.Enum('EDGE', 'PULS', 'RUNT', 'NEDG',
                                          'SLOP', 'VID', 'PATT', 'RS232',
                                          'IIC', 'SPI', 'CAN', 'FLEX', 'USB')
                           )

        self.add_parameter('trigger_mode',
                           label='Mode of the trigger',
                           get_cmd=':TRIG:SWE?',
                           set_cmd=':TRIG:SWE {}',
                           vals=vals.Enum('AUTO', 'NORM', 'SING')
                           )

        channels = ChannelList(self, "Channels", Rigol_DS4035_Channel, snapshotable=False)

        for channel_number in range(1, 5):
            channel = RigolDS4000Channel(self, "ch{}".format(channel_number), channel_number)
            channels.append(channel)

        channels.lock()
        self.add_submodule('channels', channels)

        # self.add_parameter('trigger_source',
        #                    label='Source for the trigger',
        #                    get_cmd='TRIGger:MAIn:EDGE:SOURce?',
        #                    set_cmd='TRIGger:MAIn:EDGE:SOURce {}',
        #                    vals=vals.Enum('CH1', 'CH2')
        #                    )
        # self.add_parameter('trigger_edge_slope',
        #                    label='Slope for edge trigger',
        #                    get_cmd='TRIGger:MAIn:EDGE:SLOpe?',
        #                    set_cmd='TRIGger:MAIn:EDGE:SLOpe {}',
        #                    vals=vals.Enum('FALL', 'RISE')
        #                    )
        # self.add_parameter('trigger_level',
        #                    label='Trigger level',
        #                    unit='V',
        #                    get_cmd='TRIGger:MAIn:LEVel?',
        #                    set_cmd='TRIGger:MAIn:LEVel {}',
        #                    vals=vals.Numbers()
        #                    )
        # self.add_parameter('data_source',
        #                    label='Data source',
        #                    get_cmd='DATa:SOUrce?',
        #                    set_cmd='DATa:SOURce {}',
        #                    vals=vals.Enum('CH1', 'CH2')
        #                    )
        # self.add_parameter('horizontal_scale',
        #                    label='Horizontal scale',
        #                    unit='s',
        #                    get_cmd='HORizontal:SCAle?',
        #                    set_cmd=self._set_timescale,
        #                    get_parser=float,
        #                    vals=vals.Enum(5e-9, 10e-9, 25e-9, 50e-9, 100e-9,
        #                                   250e-9, 500e-9, 1e-6, 2.5e-6, 5e-6,
        #                                   10e-6, 25e-6, 50e-6, 100e-6, 250e-6,
        #                                   500e-6, 1e-3, 2.5e-3, 5e-3, 10e-3,
        #                                   25e-3, 50e-3, 100e-3, 250e-3, 500e-3,
        #                                   1, 2.5, 5, 10, 25, 50))


    def get_waveform(self, ch = 1, raw=True, max_read_step=100):
        if ch < 1 or ch > 4:
            raise ValueError(f"Invalid channel number (got {ch}, must be between 1 and 4)")

        self.write(f':WAV:FORM BYTE')      # Set the data type for waveforms to "BYTE"
        self.write(f':WAV:SOUR CHAN{ch}')  # Set read channel

        data_bin = b''
        if raw:
            self.stop()                          # Stop acquisition
            self.write(':WAV:MODE RAW')         # Set RAW mode
            self.write(':WAV:RES')
            self.write(':WAV:BEG')

            for i in range(max_read_step):
                status = self.ask(':WAV:STAT?').split(',')[0]
                self.write(':WAV:DATA?')
                data_bin += self.visa_handle.read_raw()

                if status == 'IDLE':
                    self.write(':WAV:END')
                    break
                elif status == 'READ':
                    continue
                else:
                    raise ValueError('Communication error')
        else:
            self.write(':WAV:MODE NORM')                # Set RAW mode
            self.write(':WAV:DATA?')                    # Query data
            data_bin += self.visa_handle.read_raw()


        # Convert data to byte array
        data_bin = data_bin[11:]     # Strip header
        data_bin = data_bin.strip()  # Strip \n
        data_raw = np.fromstring(data_bin, dtype=np.uint8)  #Convert to an array

        # Convert byte array to real data
        preamble = self.ask(':WAV:PRE?').strip().split(',')
        xincrement = float(preamble[4])
        yincrement = float(preamble[7])
        yorigin = float(preamble[8])
        yreference = float(preamble[9])
        data = (data_raw - yreference - yorigin) * yincrement

        return data, xincrement