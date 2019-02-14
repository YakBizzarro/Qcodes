from .private.ZILI_AUXOutputChannel import _AUXOutputChannel
import enum

from qcodes.utils import validators as vals

class ZIHF2LI_AUXOutputChannel(_AUXOutputChannel):
    def __init__(self, parent: 'ZIHF2LI', name: str, channum: int) -> None:
        super().__init__(parent, name, channum)

        outputvalmapping = {'Manual': -1,
                            'Demod X': 0,
                            'Demod Y': 1,
                            'Demod R': 2,
                            'Demod THETA': 3,
                        }
        param = getattr(self, 'output')
        param.val_mapping = outputvalmapping
        param.vals = vals.Enum(*list(outputvalmapping.keys()))
