# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
""""""

__docformat__ = 'restructuredtext'

import argparse

from mvpa2.base import verbose
if __debug__:
    from mvpa2.base import debug
from mvpa2.base.types import is_datasetlike
from mvpa2.cmdline import common_args

def parser_add_common_args(parser, pos=None, opt=None):
    if not pos is None:
        for arg in pos:
            arg_tmpl = getattr(common_args, arg)
            parser.add_argument(arg_tmpl[0], **arg_tmpl[2])
    if not opt is None:
        for arg in opt:
            arg_tmpl = getattr(common_args, arg)
            parser.add_argument(arg_tmpl[1], **arg_tmpl[2])
    return parser

def _load_if_hdf5(arg):
    # just try it, who knows whether we can trust file extensions and whether
    # we have HDF5
    try:
        from mvpa2.base.hdf5 import h5load
        return h5load(arg)
    except:
        # didn't work
        return arg

def _mask_data(data, mask):
    if is_datasetlike(data):
        if not mask is None:
            if isinstance(mask, basestring):
                raise ValueError("masks for readily loaded datasets need to be "
                                 "valid slice arguments")
            else:
                data = data[:, mask]
        return data
    elif data is None:
        return None
    else:
        from mvpa2.datasets.mri import fmri_dataset
        return fmri_dataset(data, mask=mask)

def args2data(args):
    data = []
    for arg in args:
        if arg == '_none':
            data.append(None)
            continue
        res = _load_if_hdf5(arg)
        if is_datasetlike(res) or isinstance(res, basestring):
            # keep the filenames for now
            data.append(res)
        else:
            # might be a container
            data.extend(res)
    return data

def args2datasets(data_specs, mask_specs=None):
    data = args2data(data_specs)
    if mask_specs is None:
        masks = [None]
    else:
        masks = args2data(mask_specs)
        if len(masks) > 1 and len(masks) != len(data):
            raise ValueError("if more than one mask is given, their number "
                             "must equal those of data arguments")
    if len(masks) == 1:
        # duplicate for all data
        masks *= len(data)
    maskdata = zip(data, masks)
    dss = [_mask_data(*vals) for vals in maskdata]
    return dss

def strip_from_docstring(doc, paragraphs=None, sections=None):
    if paragraphs is None:
        paragraphs = []
    if sections is None:
        sections = []
    out = []
    # split into paragraphs
    doc = doc.split('\n\n')
    section = ''
    for par_i, par in enumerate(doc):
        lines = par.split('\n')
        if len(lines) > 1 \
           and len(lines[0]) == len(lines[1]) \
           and lines[1] == '-' * len(lines[0]):
               section = lines[0]
        if (par_i in paragraphs) or (section in sections):
            continue
        out.append(par)
    return '\n\n'.join(out)

def param2arg(parser, klass, param, arg_names=None):
    param = klass._collections_template['params'][param]
    if arg_names is None:
        arg_names = ('--%s' % param.name.replace('_', '-'),)
    # TODO add more useful information from the parameter definition
    # into the parser
    parser.add_argument(*arg_names, help=param.__doc__,
                        default=param.default,
                        type=CmdArg2ParameterType(param))

def ca2arg(parser, klass, ca, arg_names=None):
    ca = klass._collections_template['ca'][ca]
    if arg_names is None:
        arg_names = ('--%s' % ca.name.replace('_', '-'),)
    parser.add_argument(*arg_names, help=ca.__doc__, default=False,
                        action='store_true')


class CmdArg2ParameterType(object):
    def __init__(self, param):
        supported = ('allowedtype', 'min', 'max', 'name')
        for p in supported:
            varname = '_%s' % p
            if hasattr(param, p):
                setattr(self, varname, getattr(param, p))

    def __call__(self, arg):
        # interpret out type specs for parameters and return callables that convert
        # cmdline args (i.e. strings) into the required format
        # look here for more info: http://docs.python.org/library/argparse.html#type
        converted = self._arg2types(arg)
        self._range_check(converted)
        return converted

    def _range_check(self, val):
        if hasattr(self, '_min'):
            if val < self._min:
                raise argparse.ArgumentTypeError(
                        "range error "
                        "(value '%s' less than configured minimum '%s')"
                        % (val, self._min))
        if hasattr(self, '_max'):
            if val > self._max:
                raise argparse.ArgumentTypeError(
                        "range error "
                        "(value '%s' larger than configured maximum '%s')"
                        % (val, self._max))

    def _arg2types(self, arg):
        allowed = self._allowedtype
        if __debug__:
            debug('CMDLINE',
                    "type conversion for parameter '%s': %s -> %s"
                    % (self._name, arg, allowed))
        # loop over alternatives
        types = allowed.split(' or ')
        # strip out types we would not need to convert anyway
        not_convert_types = ('basestring', 'str')
        effective_types = [t for t in types if not t in not_convert_types]
        for type_ in effective_types:
            try:
                return self._arg2type(arg, type_)
            except argparse.ArgumentTypeError:
                if __debug__:
                    debug('CMDLINE', "type conversion into '%s' failed" % type_)
        # we only get here if conversion failed
        if len([t for t in types if t in not_convert_types]):
            # continuing without exception is possible
            return arg
        raise argparse.ArgumentTypeError(
                "cannot convert '%s' into '%s'" % (arg, allowed))

    def _arg2type(self, arg, allowed):
        if allowed == None:
            # we know nothing
            if __debug__:
                debug('CMDLINE',
                      "skipping parameter value conversion -- no type "
                      "spec for '%s' available" % self._name)
            return arg
        elif allowed == 'bool':
            return arg2bool(arg)
        elif allowed == 'int':
            return int(arg)
        elif allowed in ('None', 'none'):
            return arg
        elif allowed in ('float', 'float32', 'float64'):
            return float(arg)
        else:
            raise argparse.ArgumentTypeError(
                "unsupported parameter type specification: '%s'" % allowed)


def arg2bool(arg):
    arg = arg.lower()
    if arg in ['0', 'no', 'off', 'disable', 'false']:
        return False
    elif arg in ['1', 'yes', 'on', 'enable', 'true']:
        return True
    else:
        raise argparse.ArgumentTypeError(
                "'%s' cannot be converted into a boolean" % arg)

def arg2none(arg):
    arg = arg.lower()
    if arg == 'none':
        return None
    else:
        raise argparse.ArgumentTypeError(
                "'%s' cannot be converted into `None`" % arg)
