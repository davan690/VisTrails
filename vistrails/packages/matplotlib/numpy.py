from __future__ import absolute_import # 'import numpy' is not ambiguous

import numpy

from vistrails.core.modules.vistrails_module import Module


class NumPyArray(Module):
    """
    A Numpy Array, that can be loaded from a file.

    Declared as returning a List, but returns a Numpy array instead!
    """
    _input_ports = [
            ('file', '(edu.utah.sci.vistrails.basic:File)'),
            ('datatype', '(edu.utah.sci.vistrails.basic:String)')]
    _output_ports = [
            ('value', '(edu.utah.sci.vistrails.basic:List)')]

    NPY_FMT = object()

    FORMAT_MAP = dict(
               npy = NPY_FMT,

              int8 = numpy.int8,
             uint8 = numpy.uint8,
             int16 = numpy.int16,
            uint16 = numpy.uint16,
             int32 = numpy.int32,
            uint32 = numpy.uint32,
             int64 = numpy.int64,
            uint64 = numpy.uint64,

           float32 = numpy.float32,
           float64 = numpy.float64,

         complex64 = numpy.complex64,
        complex128 = numpy.complex128,
    )

    def compute(self):
        filename = self.getInputFromPort('file').name
        if self.hasInputFromPort('datatype'):
            dtype = NumPyArray.FORMAT_MAP[self.getInputFromPort('datatype')]
        else:
            if filename[-4].lower() == '.npy':
                dtype = self.NPY_FMT
            else:
                dtype = numpy.float32
        if dtype is self.NPY_FMT:
            # Numpy's ".NPY" format
            # Written with: numpy.save('xxx.npy', array)
            array = numpy.load(filename)
        else:
            # Numpy's plain binary format
            # Written with: array.tofile('xxx.dat')
            array = numpy.fromfile(filename, dtype)
        self.setResult('value', array)


_modules = [NumPyArray]
