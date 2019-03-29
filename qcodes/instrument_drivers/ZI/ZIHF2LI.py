from .private.ZILI_generic import _ZILI_generic
from .private.ZIHF2LI_AuxOutputChannel import ZIHF2LI_AuxOutputChannel
from qcodes.instrument.channel import ChannelList

import enum

from qcodes.utils import validators as vals


class ZIHF2LI(_ZILI_generic):
    """
    QCoDeS driver for ZI HF2 Lockin.

    Currently implementing demodulator settings and AUXOutputs

    Requires ZI LabOne software to be installed on the computer running QCoDeS.
    """
    class DemodTrigger(enum.IntFlag):
        CONTINUOUS = 0
        DIO0_RISING = 1
        DIO0_FALLING = 2
        DIO1_RISING = 4
        DIO1_FALLING = 8
        DIO0_HIGH = 16
        DIO0_LOW = 32
        DIO1_HIGH = 64
        DIO1_LOW = 128

#TODO: change oscillatore validator


    def __init__(self, name: str, device_ID: str, **kwargs) -> None:
        super().__init__(name, device_ID, api_level=1, **kwargs)

        num_demod = 6
        out_map = {1:6, 2:7}

        if 'MF' in self.props['options']:
            num_osc = 6
        else
            num_osc = 2

        self._create_parameters(num_osc, num_demod, out_map)


        #Create HF2LI specific parameters

        ########################################
        # Oscillators
        for oscs in range(1,num_osc+1):
            param = getattr(self, f'oscillator{oscs}_freq')
            param.vals = vals.Numbers(0, 50e6)

        ########################################
        # DEMODULATOR PARAMETERS

        for demod in range(1, num_demod+1):
            # val_mapping for the demodX_signalin parameter
            dmsigins = {'Signal input 0': 0,
                        'Signal input 1': 1,
                        'Aux Input 0': 2,
                        'Aux Input 1': 3,
                        'DIO 0': 4,
                        'DIO 1': 5}

            param = getattr(self, f'demod{demod}_signalin')
            param.val_mapping = dmsigins
            param.vals = vals.Enum(*list(dmsigins.keys()))

            param = getattr(self, f'demod{demod}_trigger')
            param.get_parser = ZIHF2LI.DemodTrigger
            param.set_parser = int


        ########################################
        # SIGNAL INPUTS

        for sigin in range(1, 3):
            param = getattr(self, f'signal_input{sigin}_range')
            param.vals = vals.Numbers(0.0001, 2)

            param = getattr(self, f'signal_input{sigin}_diff')
            param.val_mapping = {'ON': 1, 'OFF': 0}
            param.vals = vals.Enum('ON', 'OFF')

        ########################################
        # SIGNAL OUTPUTS
        for sigout in range(1,3):
            param = getattr(self, f'signal_output{sigout}_range')
            param.vals = vals.Enum(0.01, 0.1, 1, 10)

            param = getattr(self, f'signal_output{sigout}_offset')
            param.vals = vals.Numbers(-1.0, 1.0)

        ########################################
        # AUX OUTPUTS
        auxoutputchannels = ChannelList(self, "ZIHF2LI_AUXOutputChannel", ZIHF2LI_AUXOutputChannel,
                               snapshotable=False)
        for auxchannum in range(1,5):
            name = 'aux_out{}'.format(auxchannum)
            auxchannel = ZIHF2LI_AUXOutputChannel(self, name, auxchannum)
            auxoutputchannels.append(auxchannel)
            self.add_submodule(name, auxchannel)
        auxoutputchannels.lock()
        self.add_submodule('aux_out_channels', auxoutputchannels)
