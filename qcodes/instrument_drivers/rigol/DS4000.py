import logging
import binascii

import numpy as np
from pyvisa.errors import VisaIOError
from functools import partial

from qcodes import VisaInstrument, validators as vals
from qcodes import InstrumentChannel, ChannelList
from qcodes import ArrayParameter

log = logging.getLogger(__name__)


class TraceNotReady(Exception):
    pass


class DS4000(VisaInstrument):
    """
    This is the QCoDeS driver for the Rigol DS4000 serie oscilloscopes.
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

        super().__init__(name, address, timeout=timeout, device_clear=False, **kwargs)
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

        :TRIGger: SWE
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




    def _set_timescale(self, scale):
        """
        set_cmd for the horizontal_scale
        """
        self.trace_ready = False
        self.write('HORizontal:SCAle {}'.format(scale))


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