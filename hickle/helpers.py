# %% IMPORTS
# Built-in imports
import re
import operator
import typing
import types
import collections
import numbers
import h5py as h5
import os.path as os_path
from pathlib import Path

# Package imports
import dill as pickle


# %% EXCEPTION DEFINITIONS

nobody_is_my_name = ()

class NotHicklable(Exception):
    """
    object can not be mapped to proper hickle HDF5 file structure and
    thus shall be converted to pickle string before storing.
    """
    pass

class ToDoError(Exception):     # pragma: no cover
    """ An exception raised for non-implemented functionality"""
    def __str__(self):
        return "Error: this functionality hasn't been implemented yet."

# %% CLASS DEFINITIONS

class PyContainer():
    """
    Abstract base class for all PyContainer classes acting as proxy between
    h5py.Group and python object represented by the content of the h5py.Group.
    Any container type object as well as complex objects are represented
    in a tree like structure on HDF5 file which PyContainer objects ensure to
    be properly mapped before beeing converted into the final object.

    Parameters:
    -----------
        h5_attrs (h5py.AttributeManager):
            attributes defined on h5py.Group object represented by this PyContainer

        base_type (bytes):
            the basic type used for representation on the HDF5 file

        object_type:
            type of Python object to be restored. Dependent upon container may
            be used by PyContainer.convert to convert loaded Python object into
            final one.
        
    Attributes:
    -----------
        base_type (bytes):
            the basic type used for representation on the HDF5 file

        object_type:
            type of Python object to be restored. Dependent upon container may
            be used by PyContainer.convert to convert loaded Python object into
            final one.
        
    """

    __slots__ = ("base_type", "object_type", "_h5_attrs", "_content","__dict__" )

    def __init__(self,h5_attrs, base_type, object_type,_content = None):
        """
        Parameters (protected):
        -----------------------
            _content (default: list):
                container to be used to collect the Python objects representing
                the sub items or the state of the final Python object. Shall only
                be set by derived PyContainer classes and not be set by

        """
        # the base type used to select this PyContainer
        self.base_type = base_type
        # class of python object represented by this PyContainer
        self.object_type = object_type
        # the h5_attrs structure of the h5_group to load the object_type from
        # can be used by the append and convert methods to obtain more
        # information about the container like object to be restored
        self._h5_attrs = h5_attrs
        # intermediate list, tuple, dict, etc. used to collect and store the sub items
        # when calling the append method
        self._content = _content if _content is not None else []

    def filter(self,h_parent):
        """
        PyContainer type child chasses may overload this function to
        filter and preprocess the content of h_parent h5py.Group or 
        h5py.Dataset to ensure it can be properly processed by recursive
        calls to hickle._load function.

        Per default yields from h_parent.items(). 

        For examples see: 
            hickle.lookup.ExpandReferenceContainer.filter
            hickle.loaders.load_scipy.SparseMatrixContainer.filter
        """
        yield from h_parent.items()
 
    def append(self,name,item,h5_attrs):
        """
        adds the passed item (object) to the content of this container.
       
        Parameters:
        -----------
            name (string):
                the name of the h5py.Dataset or h5py.Group subitem was loaded from

            item:
                the Python object of the subitem

            h5_attrs:
                attributes defined on h5py.Group or h5py.Dataset object sub item
                was loaded from.
        """
        self._content.append(item)

    def convert(self):
        """
        creates the final object and populates it with the items stored in the _content slot
        must be implemented by the derived Container classes

        Returns:
        --------
            py_obj: The final Python object loaded from file

        
        """
        raise NotImplementedError("convert method must be implemented")


class H5NodeFilterProxy():
    """
    Proxy class which allows to temporarily modify h5_node.attrs content.
    Original attributes of underlying h5_node are left unchanged.
    
    Parameters:
    -----------
        h5_node:
            node for which attributes shall be replaced by a temporary value
        
    """

    __slots__ = ('_h5_node','attrs','__dict__')

    def __init__(self,h5_node):
        self._h5_node = h5_node
        self.attrs = collections.ChainMap({},h5_node.attrs)

    def __getattribute__(self,name):
        # for attrs and wrapped _h5_node return local copy any other request
        # redirect to wrapped _h5_node
        if name in {"attrs","_h5_node"}:
            return super(H5NodeFilterProxy,self).__getattribute__(name)
        _h5_node = super(H5NodeFilterProxy,self).__getattribute__('_h5_node')
        return getattr(_h5_node,name)
        
    def __setattr__(self,name,value):
        # if wrapped _h5_node and attrs shall be set store value on local attributes
        # otherwise pass on to wrapped _h5_node
        if name in {'_h5_node','attrs'}:
            super(H5NodeFilterProxy,self).__setattr__(name,value)
            return
        _h5_node = super(H5NodeFilterProxy,self).__getattribute__('_h5_node')
        setattr(_h5_node,name,value)    

    def __getitem__(self,*args,**kwargs):
        _h5_node = super(H5NodeFilterProxy,self).__getattribute__('_h5_node')
        return _h5_node.__getitem__(*args,**kwargs)
    # TODO as needed add more function like __getitem__ to fully proxy h5_node
    # or consider using metaclass __getattribute__ for handling special methods


class no_compression(dict):
    """
    named dict comprehension which which temporarily removes any compression or data filter related
    arguments from the passed iterable. 
    """
    def __init__(self,mapping,**kwargs):
        super().__init__((
            (key,value)
            for key,value in ( mapping.items() if isinstance(mapping,dict) else mapping )
            if key not in {"compression","shuffle","compression_opts","chunks","fletcher32","scaleoffset"}
        ))
        

# %% FUNCTION DEFINITIONS

def not_dumpable( py_obj, h_group, name, **kwargs): # pragma: nocover
    """
    create_dataset method attached to dummy py_objects used to mimic container
    groups by older versions of hickle lacking generic PyContainer mapping
    h5py.Groups to corresponding py_object

        
    Raises:
    -------
        RuntimeError:
            in any case as this function shall never be called    
    """

    raise RuntimeError("types defined by loaders not dumpable")

# 
# def not_io_base_like(f,*args):
#     """
#     creates function which can be used in replacement for
#     IOBase.isreadable, IOBase.isseekable and IOBase.iswriteable
#     methods in case f would not provide any of them.
# 
#     Parameters:
#     ===========
#         f (file or file like):
#             file or file like object to which hickle shall
#             dump data too.
# 
#         *args (tuple):
#             tuple containg either 2 or 4 elements
#             inices 0, 2 :
#                 name of methods to be tested
#             odd indices  1, 3 :
#                 *args tuples passed to tested methods
#                 ( **kwargs not supported)
#                 ( optional if last item  in tuple)
# 
#     Returns:
#     ========
#         function to be called in replacement if any of IOBase.isreadable,
#         IOBase.isseekable or IOBase.isreadable wold be not implemented
# 
#     Example:
#     ========
#         if not getattr(f,'read',not_io_base_like(f,'read',0))():
#             raise ValueError("Not a reaable file or file like object")
#     """
#     def must_test():
#         if not args: # pragma: nocover
#             return False
#         cmd = getattr(f,args[0],None)
#         if not cmd:
#             return False
#         try:
#             cmd(*args[1:2])
#         except:
#             return False
#         if len(args) < 3:
#             return True
#         cmd = getattr(f,args[2],None)
#         if not cmd:
#             return False
#         try:
#             cmd(*args[3:4])
#         except:
#             return False
#         return True
#     return must_test
# 
# def file_opener(f, path, mode='r',filename = None):
#     """
#     A file opener helper function with some error handling.
#     This can open files through a file object, an h5py file, or just the
#     filename.
# 
#     Parameters
#     ----------
#     f : file object, str or :obj:`~h5py.Group` object
#         File to open for dumping or loading purposes.
#         If str, `file_obj` provides the path of the HDF5-file that must be
#         used.
#         If :obj:`~h5py.Group`, the group (or file) in an open
#         HDF5-file that must be used.
#     path : str
#         Path within HDF5-file or group to dump to/load from.
#     mode : str, optional
#         Accepted values are 'r' (read only), 'w' (write; default) or 'a'
#         (append).
#         Ignored if file is a file object.
# 
#     """
# 
#     # Make sure that the given path always starts with '/'
#     if not path.startswith('/'):
#         path = "/%s" % path
# 
#     # Were we handed a file object or just a file name string?
#     if isinstance(f, (str, Path)):
#         return h5.File(f, mode[:(-1 if mode[-1] == 'b' else None)]),path,True
#     if isinstance(f, h5.Group):
#         if not f:
#             raise ClosedFileError(
#                 "HDF5 file {}has been closed or h5py.Group or h5py.Dataset are not accessible. "
#                 "Please pass either a filename string, a pathlib.Path, a file or file like object, "
#                 "an opened h5py.File or h5py.Group or h5py.Dataset there outof.".format(
#                     "'{}' ".format(filename) if isinstance(filename,(str,bytes)) and filename else ''
#                 )
#             )
#         base_path = f.name
#         if not isinstance(f,h5.File):
#             f = f.file
#         if mode[0] == 'w' and f.mode != 'r+':
#             raise FileError( "HDF5 file '{}' not opened for writing".format(f.filename))
# 
#         # Since this file was already open, do not close the file afterward
#         return f,''.join((base_path,path.rstrip('/'))),False
# 
#     if not isinstance(filename,(str,bytes)):
#         if filename is not None:
#             raise ValueError("'filename' must be of type 'str' or 'bytes'")
#         if isinstance(f,(tuple,list)) and len(f) > 1:
#             f,filename = f[:2]
#         elif isinstance(f,dict):
#             f,filename = f['file'],f['name']
#         else:
#             filename = getattr(f,'filename',None)
#             if filename is None:
#                 filename = getattr(f,'name',None)
#                 if filename is None:
#                     filename = repr(f)
#     if getattr(f,'closed',False):
#         raise ClosedFileError(
#             "HDF5 file {}has been closed or h5py.Group or h5py.Dataset are not accessible. "
#             "Please pass either a filename string, a pathlib.Paht, a file or file like object, "
#             "an opened h5py.File or h5py.Group or h5py.Dataset there outof.".format(
#                 "'{}' ".format(filename) if isinstance(filename,(str,bytes)) and filename else ''
#             )
#         )
#     if (
#         getattr(f,'readable',not_io_base_like(f,'read',0))() and
#         getattr(f,'seekable',not_io_base_like(f,'seek',0,'tell'))()
#     ):
# 
#         if len(mode) > 1 and mode[1] == '+':
#             if not getattr(f,'writeable',not_io_base_like(f,'write',b''))():
#                 raise FileError(
#                     "file '{}' not writable. Please pass either a filename string, "
#                     "a pathlib.Path,  a file or file like object, "
#                     "an opened h5py.File or h5py.Group or h5py.Dataset there outof.".format(filename)
#                 )
#         if ( mode[0] != 'r' ):
#             if mode[0] not in 'xwa':
#                 raise ValueError("invalid file mode must be one outof 'w','w+','x','x+','r','r+','a'. A trailing 'b' is ignored")
#             if not getattr(f,'writeable',not_io_base_like(f,'write',b''))():
#                 raise FileError(
#                     "file '{}' not writable. Please pass either a filename string, "
#                     "a pathlib.Path, a file or file like object, "
#                     "an opened h5py.File or h5py.Group or h5py.Dataset there outof.".format(filename)
#                 )
#         return h5.File(
#             f,
#             mode[:( 1 if mode[0] == 'w' else ( -1 if mode[-1] == 'b' else None ) )],
#             driver='fileobj',
#             fileobj = f
#         ), path, True
# 
#     if mode[0] == 'w' and getattr(f,'mode','')[:2] not in ('r+','w+','a','x+',''):
#         raise FileError( "file or file like object '{}' not opened for reading and writing ".format(filename))
#         
#     raise FileError(
#         "'file_obj' must be a valid path string, pahtlib.Path, h5py.File, h5py.Group, h5py.Dataset, file  or file like object'"
#     )

if h5.version.version_tuple[0] >= 3: # pragma: nocover
    load_str_list_attr_ascii = load_str_list_attr = h5.AttributeManager.get
    load_str_attr_ascii = load_str_list_attr = h5.AttributeManager.get
else: # pragma: nocover
    def load_str_list_attr_ascii(attrs,name):
        return [ value.decode('ascii') for value in attrs[name]]
    def load_str_list_attr(attrs,name):
        return [ value.decode('utf8') for value in attrs[name]]
    def load_str_attr_ascii(attrs,name):
        return attrs[name].decode('ascii')
    def load_str_attr(attrs,name):
        return attrs[name].decode('utf8')

