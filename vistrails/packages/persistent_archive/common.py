###############################################################################
##
## Copyright (C) 2014-2016, New York University.
## Copyright (C) 2013-2014, NYU-Poly.
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice,
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright
##    notice, this list of conditions and the following disclaimer in the
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the New York University nor the names of its
##    contributors may be used to endorse or promote products derived from
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################



from vistrails.core.modules.basic_modules import Constant, String
from vistrails.core.modules.config import IPort, OPort
from vistrails.core.modules.vistrails_module import ModuleError


@apply
class StoreHolder(object):
    def __init__(self):
        self.store = None

    def get_store(self):
        return self.store

    def set_store(self, store):
        self.store = store

set_default_store = StoreHolder.set_store
get_default_store = StoreHolder.get_store


# The type of the file, i.e. how VisTrails stored it
KEY_TYPE = 'vistrails_objecttype'
TYPE_CACHED =   'cached'    # A cached path, with very little metadata
TYPE_INPUT =    'input'     # An input file, i.e. an external file that
                            # VisTrails added to the store as-is
TYPE_OUTPUT =   'output'    # An intermediate or output file, i.e. a file that
                            # was generated by VisTrails

# Timestamp for file insertion
KEY_TIME = 'vistrails_timestamp'

# Signature of the module that added the file (cached and output, not input)
KEY_SIGNATURE = 'vistrails_signature'

# Identifier for the workflow
KEY_WORKFLOW = 'vistrails_workflow'

# Module ID in the workflow
KEY_MODULE_ID = 'vistrails_module_id'


class PersistentHash(Constant):
    """Reference to a specific file.

    Unequivocally references a specific file (by its full hash).
    """
    def __init__(self, h=None):
        Constant.__init__(self)
        if h is not None:
            self._set_hash(h)
        else:
            self._hash = None

    def _set_hash(self, h):
        if not (isinstance(h, str)):
            raise TypeError("File hash should be a string")
        elif len(h) != 40:
            raise ValueError("File hash should be 40 characters long")
        if not isinstance(h, bytes):
            h = bytes(h)
        self._hash = h

    @staticmethod
    def translate_to_python(h):
        try:
            return PersistentHash(h)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def translate_to_string(ref):
        if ref._hash is not None:
            return ref._hash
        else:
            raise ValueError("Reference is invalid")

    @staticmethod
    def validate(ref):
        return isinstance(ref, PersistentHash)

    def __str__(self):
        return self._hash

    def __repr__(self):
        if self._hash is not None:
            return "<PersistentHash %s>" % self._hash
        else:
            return "<PersistentHash (invalid)>"

    def compute(self):
        if self.has_input('value') == self.has_input('hash'):
            raise ModuleError(self, "Set either 'value' or 'hash'")
        if self.has_input('value'):
            self._hash = self.get_input('value')._hash
        else:
            try:
                self._set_hash(self.get_input('hash'))
            except ValueError as e:
                raise ModuleError(self, e.message)

PersistentHash._input_ports = [
        IPort('value', PersistentHash),
        IPort('hash', String)]
PersistentHash._output_ports = [
        OPort('value', PersistentHash)]
