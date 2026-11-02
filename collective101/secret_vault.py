"""Windows user-bound secret encryption. No plaintext persistence fallback."""
import base64
import ctypes
import os
from ctypes import wintypes

class SecretVault:
    def _transform(self,data,decrypt=False):
        if os.name!='nt': raise ValueError('Saving connector secrets requires Windows DPAPI on this build')
        class Blob(ctypes.Structure):
            _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_byte))]
        buffer=ctypes.create_string_buffer(data)
        source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_byte)));target=Blob()
        crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
        function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        function.restype=wintypes.BOOL
        kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
        if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
            raise ValueError('Windows could not access the connector secret for this user')
        try:return ctypes.string_at(target.data,target.size)
        finally:kernel.LocalFree(target.data)
    def seal(self,value):return 'dpapi:'+base64.b64encode(self._transform(value.encode())).decode()
    def reveal(self,value):
        if not value:return ''
        if not value.startswith('dpapi:'):raise ValueError('Unsupported secret format')
        return self._transform(base64.b64decode(value[6:]),True).decode()
