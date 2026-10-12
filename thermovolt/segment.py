import ctypes,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class CSegmentTree:
    def __init__(self,values):
        suffix='.dylib' if sys.platform=='darwin' else '.so';path=ROOT/'c'/('segment'+suffix)
        if not path.exists():
            flags=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
            subprocess.run(['cc',*flags,'-O2',str(ROOT/'c/segment_tree.c'),'-o',str(path),'-lm'],check=True)
        self.lib=ctypes.CDLL(str(path));self.lib.tree_create.argtypes=[ctypes.POINTER(ctypes.c_double),ctypes.c_int];self.lib.tree_create.restype=ctypes.c_void_p
        self.lib.tree_query.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_int)];self.lib.tree_query.restype=ctypes.c_int
        self.lib.tree_free.argtypes=[ctypes.c_void_p];self.lib.tree_free.restype=None
        arr=(ctypes.c_double*len(values))(*values);self.handle=self.lib.tree_create(arr,len(values))
        if not self.handle:raise ValueError('Provide finite temperature values.')
    def query(self,start,end):
        if type(start)!=int or type(end)!=int:raise ValueError('Use integer interval boundaries.')
        out=(ctypes.c_double*4)();visited=ctypes.c_int()
        if not self.lib.tree_query(self.handle,start,end,out,ctypes.byref(visited)):raise ValueError('Select a valid inclusive interval.')
        return {'min':out[0],'max':out[1],'sum':out[2],'count':int(out[3]),'average':out[2]/out[3],'visited':visited.value,'runtime':'C segment tree via ctypes'}
    def close(self):
        if self.handle:self.lib.tree_free(self.handle);self.handle=None
    def __del__(self):
        if getattr(self,'handle',None):self.close()
