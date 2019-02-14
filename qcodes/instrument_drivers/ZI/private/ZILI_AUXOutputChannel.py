from qcodes.instrument.channel import InstrumentChannel

class _AUXOutputChannel(InstrumentChannel):

    def __init__(self, parent: '_ZILI_generic', name: str, channum: int) -> None:
        super().__init__(parent, name)

        # TODO better validations of parameters
        self.add_parameter('scale',
                           label='scale',
                           unit='',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 1, 'scale'),
                           set_cmd=partial(self._parent._setter, 'auxouts',
                                           channum - 1, 1, 'scale'),
                           vals=vals.Numbers()
                           )

        self.add_parameter('offset',
                           label='offset',
                           unit='V',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 1, 'offset'),
                           set_cmd=partial(self._parent._setter, 'auxouts',
                                           channum - 1, 1, 'offset'),
                           vals=vals.Numbers()
                           )


        # TODO the validator does not catch that there are only
        # 2 valid output channels for AU types
        self.add_parameter('channel',
                           label='Channel',
                           unit='',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 0, 'demodselect'),
                           set_cmd=partial(self._parent._setter, 'auxouts',
                                           channum - 1, 0, 'demodselect'),
                           get_parser=lambda x: x+1,
                           set_parser=lambda x: x-1,
                           vals=vals.Ints(0,7)
                           )

        self.add_parameter('output',
                           label='Output',
                           unit='',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 0, 'outputselect'),
                           set_cmd=partial(self._parent._setter, 'auxouts',
                                           channum - 1, 0, 'outputselect')
                           )

        self.add_parameter('value',
                           label='value',
                           unit='V',
                           get_cmd=partial(self._parent._getter, 'auxouts',
                                           channum - 1, 1, 'value'),
                           set_cmd=None
                           )