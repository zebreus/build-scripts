from cryptography.hazmat.bindings.openssl.binding import Binding
binding = Binding()
ffi = binding.ffi
ffi.callback( "void (*)(const SSL *, const char *)", lambda a : a + 10 )