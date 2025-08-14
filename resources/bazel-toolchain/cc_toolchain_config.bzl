# load("@bazel_tools//tools/cpp:cpp.bzl", "all_compile_actions", "all_link_actions")
# load("@bazel_tools//tools/cpp:toolchain_utils.bzl", "tool_path")
load("@bazel_tools//tools/cpp:cc_toolchain_config_lib.bzl", "tool_path")

def wasix_cc_toolchain_config_impl(ctx):
    return cc_common.create_cc_toolchain_config_info(
        ctx = ctx,
        toolchain_identifier = "wasix-toolchain",
        host_system_name = "local",
        target_system_name = "wasm32-wasi",
        target_cpu = "wasm32-wasi",
        target_libc = "unknown",
        compiler = "wasix-clang",
        abi_version = "unknown",
        abi_libc_version = "unknown",
        builtin_sysroot = env['WASIX_SYSROOT'],
        cxx_builtin_include_directories = [
            env['WASIX_CLANG_DIR'] + "/wasix-llvm/lib/clang/21/include",
            env['WASIX_SYSROOT'] + "/include/c++/v1/stddef.h",
            env['WASIX_SYSROOT'] + "/include",
            env['WASIX_SYSROOT'] + "/include/c++/v1",
            env['WASIX_SYSROOT'] + "/usr/local/include",
        ],
        tool_paths = [
        tool_path(name = "gcc", path = env['WASIX_CLANG_DIR'] + "/bin/wasix-clang"),   # will be wasix-clang
        tool_path(name = "g++", path = env['WASIX_CLANG_DIR'] + "/bin/wasix-clang++"), # will be wasix-clang++
        tool_path(name = "ar", path = env['WASIX_CLANG_DIR'] + "wasix-llvm/bin/llvm-ar"),
        tool_path(name = "ld", path = "/bin/false"),
        tool_path(name = "cpp",path = "/bin/false",
        ),
        tool_path(name = "gcov",path = "/bin/false",
        ),
        tool_path(name = "nm",path = "/bin/false",
        ),
        tool_path(name = "objdump",path = "/bin/false",
        ),
        tool_path(name = "strip",path = "/bin/false",
        ),
    ]
    )

wasix_cc_toolchain_config = rule(
    implementation = lambda ctx: [wasix_cc_toolchain_config_impl(ctx)],
    attrs = {},
    provides = [CcToolchainConfigInfo],
)