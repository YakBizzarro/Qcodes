from .private.ZILI_AUXOutputChannel import _AUXOutputChannel
import enum

from qcodes.utils import validators as vals

class ZIUHFLI_AUXOutputChannel(_AUXOutputChannel):
    def __init__(self, parent: 'ZIUHFLI', name: str, channum: int) -> None:
        super().__init__(parent, name, channum)

        self.add_parameter('preoffset',
                           label='preoffset',
                           unit='',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 1, 'preoffset'),
                           set_cmd=partial(self._parent._setter, 'auxouts',
                                           channum - 1, 1, 'preoffset'),
                           vals=vals.Numbers()
                           )

        self.add_parameter('limitlower',
                           label='Lower limit',
                           unit='V',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 1, 'limitlower'),
                           set_cmd=partial(self._parent._setter, 'auxouts',
                                           channum - 1, 1, 'limitlower'),
                           vals=vals.Numbers()
                           )

        self.add_parameter('limitupper',
                           label='Upper limit',
                           unit='V',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 1, 'limitupper'),
                           set_cmd=partial(self._parent._setter, 'auxouts',
                                           channum - 1, 1, 'limitupper'),
                           vals=vals.Numbers()
                           )

        outputvalmapping = {'Manual': -1,
                            'Demod X': 0,
                            'Demod Y': 1,
                            'Demod R': 2,
                            'Demod THETA': 3,
                            'AWG': 4,
                            'PID': 5,
                            'Boxcar': 6,
                            'AU Cartesian': 7,
                            'AU Polar': 8,
                            'PID Shift': 9,
                            'PID Error': 10,
                            'Pulse Counter': 12
                        }
        param = getattr(self, 'output')
        param.val_mapping = outputvalmapping
        param.vals = vals.Enum(*list(outputvalmapping.keys()))
