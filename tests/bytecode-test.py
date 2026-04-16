import contextlib
import dis
import io
import sys
import types
import unittest

import bytecode
from bytecode import (
    __version__ as BYTECODE_VERSION,
    UNSET,
    BasicBlock,
    Bytecode,
    CellVar,
    Compare,
    ConcreteBytecode,
    ConcreteInstr,
    ControlFlowGraph,
    FreeVar,
    Instr,
    Label,
    SetLineno,
)

# Optional / version-dependent API (bytecode package + Python version)
InstrLocation = getattr(bytecode, "InstrLocation", None)
TryBegin = getattr(bytecode, "TryBegin", None)
TryEnd = getattr(bytecode, "TryEnd", None)
BinaryOp = getattr(bytecode, "BinaryOp", None)
Intrinsic1Op = getattr(bytecode, "Intrinsic1Op", None)
Intrinsic2Op = getattr(bytecode, "Intrinsic2Op", None)
infer_flags = getattr(bytecode, "infer_flags", None)
CompilerFlags = getattr(bytecode, "CompilerFlags", None)


def pick_opcode_name(*candidates: str) -> str:
    for name in candidates:
        if name in dis.opmap:
            return name
    raise unittest.SkipTest(f"None of these opcodes exist in this Python: {candidates!r}")


def call_concreteinstr_disassemble(code_bytes: bytes, offset: int = 0) -> ConcreteInstr:
    """
    ConcreteInstr.disassemble signature differs across bytecode versions.
    Known shapes include:
      - disassemble(code, offset)
      - disassemble(code, offset, lineno)
      - disassemble(self, code, offset)   (non-@staticmethod in some versions)
    We'll try the common combinations robustly.
    """
    # try as a staticmethod with kwargs
    try:
        return ConcreteInstr.disassemble(code=code_bytes, offset=offset)
    except TypeError:
        pass

    # try with required lineno kw
    try:
        return ConcreteInstr.disassemble(code=code_bytes, offset=offset, lineno=1)
    except TypeError:
        pass

    # try positional (code, offset)
    try:
        return ConcreteInstr.disassemble(code_bytes, offset)
    except TypeError:
        pass

    # try positional (code, offset, lineno)
    try:
        return ConcreteInstr.disassemble(code_bytes, offset, 1)
    except TypeError:
        pass

    # Some versions define it as an instance method (needs a dummy instance)
    dummy = ConcreteInstr(pick_opcode_name("NOP"))
    try:
        return dummy.disassemble(code_bytes, offset)  # type: ignore[attr-defined]
    except TypeError:
        pass
    try:
        return dummy.disassemble(code_bytes, offset, 1)  # type: ignore[attr-defined]
    except TypeError as e:
        raise unittest.SkipTest(f"ConcreteInstr.disassemble signature not supported here: {e!r}")


def make_simple_function():
    def f(x, y=3):
        z = x + y
        if z > 10:
            return z
        return z - 1

    return f


def make_closure_function():
    def outer(a):
        b = 7

        def inner(x):
            return a + b + x

        return inner

    return outer


class TestBytecodeModule(unittest.TestCase):
    def test_constants___version___and_UNSET(self):
        self.assertIsInstance(BYTECODE_VERSION, str)
        self.assertTrue(BYTECODE_VERSION)
        self.assertIsNot(UNSET, None)
        self.assertIs(UNSET, bytecode.UNSET)

    def test_format_and_dump_accept_multiple_types(self):
        fn = make_simple_function()
        bc = Bytecode.from_code(fn.__code__)
        cfg = ControlFlowGraph.from_bytecode(bc)
        cbc = bc.to_concrete_bytecode()

        self.assertIsInstance(bytecode.format_bytecode(bc), str)
        self.assertIsInstance(bytecode.format_bytecode(cfg), str)
        self.assertIsInstance(bytecode.format_bytecode(cbc), str)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            bytecode.dump_bytecode(bc, lineno=True)
            bytecode.dump_bytecode(cfg, lineno=True)
            bytecode.dump_bytecode(cbc, lineno=True)
        self.assertTrue(len(buf.getvalue()) > 10)

    def test_instr_basics_require_arg_copy_set_and_name_opcode_sync(self):
        nop = pick_opcode_name("NOP")
        load_const = pick_opcode_name("LOAD_CONST")

        i1 = Instr(nop)
        self.assertFalse(i1.require_arg())
        self.assertIs(i1.arg, UNSET)

        i2 = Instr(load_const, 123)
        self.assertTrue(i2.require_arg())
        self.assertEqual(i2.arg, 123)

        i3 = i2.copy()
        self.assertIsNot(i2, i3)
        self.assertEqual(i2.name, i3.name)
        self.assertEqual(i2.arg, i3.arg)
        self.assertEqual(i2.opcode, i3.opcode)

        i4 = Instr(load_const, 1)
        self.assertTrue(i4.require_arg())
        i4.set(nop)
        self.assertFalse(i4.require_arg())
        self.assertIs(i4.arg, UNSET)
        i4.set(load_const, 999)
        self.assertTrue(i4.require_arg())
        self.assertEqual(i4.arg, 999)

        i5 = Instr(load_const, 7)
        i5.opcode = dis.opmap[load_const]
        self.assertEqual(i5.name, load_const)

    def test_instr_jump_introspection(self):
        jmp_uncond = pick_opcode_name("JUMP_FORWARD", "JUMP_ABSOLUTE", "JUMP_BACKWARD", "JUMP_BACKWARD_NO_INTERRUPT")

        jmp_cond = None
        for cand in (
            "POP_JUMP_IF_FALSE",
            "POP_JUMP_IF_TRUE",
            "JUMP_IF_FALSE_OR_POP",
            "JUMP_IF_TRUE_OR_POP",
            "JUMP_BACKWARD_IF_FALSE",
            "JUMP_BACKWARD_IF_TRUE",
            "JUMP_FORWARD_IF_FALSE_OR_POP",
            "JUMP_FORWARD_IF_TRUE_OR_POP",
        ):
            if cand in dis.opmap:
                jmp_cond = cand
                break

        lbl = Label()
        j1 = Instr(jmp_uncond, lbl)
        self.assertTrue(j1.has_jump())
        self.assertTrue(j1.is_uncond_jump())
        self.assertIsInstance(j1.is_final(), bool)

        if jmp_cond:
            j2 = Instr(jmp_cond, lbl)
            self.assertTrue(j2.has_jump())
            self.assertTrue(j2.is_cond_jump())
            self.assertFalse(j2.is_uncond_jump())
        else:
            self.skipTest("No known conditional jump opcode available on this Python build")

        self.assertIsInstance(j1.is_abs_jump(), bool)
        self.assertIsInstance(j1.is_forward_rel_jump(), bool)
        self.assertIsInstance(j1.is_backward_rel_jump(), bool)

    def test_instr_stack_effect_and_pre_post_effect(self):
        load_const = pick_opcode_name("LOAD_CONST")

        if "BINARY_OP" in dis.opmap and BinaryOp is not None:
            binary_op = Instr("BINARY_OP", BinaryOp.ADD)
        else:
            legacy = None
            for cand in ("BINARY_ADD", "BINARY_MULTIPLY"):
                if cand in dis.opmap:
                    legacy = cand
                    break
            if not legacy:
                raise unittest.SkipTest("No binary operation opcode found")
            binary_op = Instr(legacy)

        ret = Instr(pick_opcode_name("RETURN_VALUE"))

        i1 = Instr(load_const, 1)
        self.assertIsInstance(i1.stack_effect(), int)
        pre1, post1 = i1.pre_and_post_stack_effect()
        self.assertIsInstance(pre1, int)
        self.assertIsInstance(post1, int)

        self.assertIsInstance(binary_op.stack_effect(), int)
        pre2, post2 = binary_op.pre_and_post_stack_effect()
        self.assertIsInstance(pre2, int)
        self.assertIsInstance(post2, int)

        self.assertIsInstance(ret.stack_effect(), int)

    def test_compare_enum(self):
        self.assertTrue(hasattr(Compare, "EQ"))
        self.assertTrue(hasattr(Compare, "LT"))
        if "COMPARE_OP" in dis.opmap:
            i = Instr("COMPARE_OP", Compare.EQ)
            self.assertEqual(i.name, "COMPARE_OP")
            self.assertEqual(i.arg, Compare.EQ)

    def test_cellvar_freevar_repr_and_usage(self):
        cv = CellVar("c")
        fv = FreeVar("f")
        self.assertEqual(cv.name, "c")
        self.assertEqual(fv.name, "f")

        deref_op = None
        for cand in ("LOAD_DEREF", "STORE_DEREF", "LOAD_CLOSURE", "MAKE_CELL"):
            if cand in dis.opmap:
                deref_op = cand
                break
        if deref_op:
            i1 = Instr(deref_op, cv)
            i2 = Instr(deref_op, fv)
            self.assertEqual(i1.arg.name, "c")
            self.assertEqual(i2.arg.name, "f")
        else:
            self.skipTest("No deref-like opcode present")

    def test_instr_location_if_available(self):
        if InstrLocation is None:
            self.skipTest("InstrLocation not exported by this bytecode version")

        fn = make_simple_function()
        positions = None
        for ins in dis.get_instructions(fn):
            if getattr(ins, "positions", None) is not None:
                positions = ins.positions
                break
        if positions is None:
            self.skipTest("dis.Instruction.positions not available on this Python")

        loc = InstrLocation.from_positions(positions)
        self.assertIsInstance(loc, InstrLocation)

        i = Instr(pick_opcode_name("NOP"), location=loc)
        self.assertIs(i.location, loc)

    def test_bytecode_from_code_and_to_code_roundtrip_executes(self):
        fn = make_simple_function()
        bc = Bytecode.from_code(fn.__code__)
        code = bc.to_code()
        self.assertIsInstance(code, types.CodeType)
        g = types.FunctionType(code, {})
        self.assertEqual(g(8, 3), fn(8, 3))
        self.assertEqual(g(9, 3), fn(9, 3))
        self.assertEqual(g(1, 3), fn(1, 3))

    def test_bytecode_manual_labels_and_legalize(self):
        bc = Bytecode()
        bc.name = "const42"
        bc.argcount = 0
        bc.first_lineno = 123
        bc.filename = "<test>"
        bc.extend(
            [
                SetLineno(123),
                Instr(pick_opcode_name("LOAD_CONST"), 42, lineno=123),
                Instr(pick_opcode_name("RETURN_VALUE"), lineno=123),
            ]
        )

        bc2 = Bytecode(bc)
        bc2.legalize()
        self.assertTrue(all(not isinstance(x, SetLineno) for x in bc2))
        self.assertTrue(any(isinstance(x, Instr) and x.lineno == 123 for x in bc2))

        code = bc2.to_code()
        f = types.FunctionType(code, {})
        self.assertEqual(f(), 42)

        lbl = Label()
        jmp = pick_opcode_name("JUMP_FORWARD", "JUMP_ABSOLUTE", "JUMP_BACKWARD", "JUMP_BACKWARD_NO_INTERRUPT")
        bc3 = Bytecode()
        bc3.name = "jump_to_return"
        bc3.first_lineno = 1
        bc3.extend(
            [
                Instr(pick_opcode_name("LOAD_CONST"), 1),
                Instr(jmp, lbl),
                Instr(pick_opcode_name("LOAD_CONST"), 999),
                lbl,
                Instr(pick_opcode_name("RETURN_VALUE")),
            ]
        )
        cbc = bc3.to_concrete_bytecode()
        self.assertIsInstance(cbc, ConcreteBytecode)

        code3 = bc3.to_code()
        f3 = types.FunctionType(code3, {})
        self.assertEqual(f3(), 1)

    def test_bytecode_compute_stacksize_and_update_flags(self):
        fn = make_simple_function()
        bc = Bytecode.from_code(fn.__code__)
        ss = bc.compute_stacksize()
        self.assertIsInstance(ss, int)
        self.assertGreaterEqual(ss, 0)

        bc.update_flags()
        self.assertIsInstance(bc.flags, int)

        if infer_flags is not None and CompilerFlags is not None:
            flags = infer_flags(bc)
            self.assertGreaterEqual(int(flags), 0)

    def test_concretebytecode_from_code_and_to_bytecode_roundtrip(self):
        fn = make_simple_function()
        cbc = ConcreteBytecode.from_code(fn.__code__)
        self.assertIsInstance(cbc, ConcreteBytecode)

        bc = cbc.to_bytecode()
        self.assertIsInstance(bc, Bytecode)

        code = cbc.to_code()
        f = types.FunctionType(code, {})
        self.assertEqual(f(8, 3), fn(8, 3))

        ss = cbc.compute_stacksize()
        self.assertIsInstance(ss, int)
        self.assertGreaterEqual(ss, 0)

        if sys.version_info >= (3, 11):
            self.assertTrue(hasattr(cbc, "exception_table"))
            self.assertIsInstance(cbc.exception_table, list)

    def test_concreteinstr_assemble_disassemble_size_and_jump_target(self):
        load_const = pick_opcode_name("LOAD_CONST")
        ci = ConcreteInstr(load_const, 0)
        b = ci.assemble()
        self.assertIsInstance(b, (bytes, bytearray))
        self.assertTrue(len(b) >= 1)

        ci2 = call_concreteinstr_disassemble(bytes(b), 0)
        self.assertIsInstance(ci2, ConcreteInstr)
        self.assertEqual(ci2.name, ci.name)

        small = ConcreteInstr(load_const, 1)
        big = ConcreteInstr(load_const, 1 << 20)
        self.assertIsInstance(small.size, int)
        self.assertIsInstance(big.size, int)
        self.assertGreaterEqual(big.size, small.size)

        jname = None
        for cand in ("JUMP_FORWARD", "JUMP_ABSOLUTE", "JUMP_BACKWARD", "JUMP_BACKWARD_NO_INTERRUPT"):
            if cand in dis.opmap:
                jname = cand
                break
        if jname is None:
            self.skipTest("No known jump opcode for ConcreteInstr.get_jump_target")

        j = ConcreteInstr(jname, 1)
        tgt = j.get_jump_target(instr_offset=10)
        self.assertTrue(tgt is None or isinstance(tgt, int))

        ncache = j.use_cache_opcodes()
        self.assertIsInstance(ncache, int)
        self.assertGreaterEqual(ncache, 0)

    def test_basicblock_legalize_get_jump_and_trailing_end(self):
        bb = BasicBlock()
        bb.extend(
            [
                SetLineno(1),
                Instr(pick_opcode_name("LOAD_CONST"), 123),
                Instr(pick_opcode_name("RETURN_VALUE")),
            ]
        )
        bb.legalize(first_lineno=1)
        self.assertTrue(all(not isinstance(x, SetLineno) for x in bb))
        self.assertIsNone(bb.get_jump())

        cond_name = None
        for cand in (
            "POP_JUMP_IF_FALSE",
            "POP_JUMP_IF_TRUE",
            "JUMP_IF_FALSE_OR_POP",
            "JUMP_IF_TRUE_OR_POP",
            "JUMP_BACKWARD_IF_FALSE",
            "JUMP_BACKWARD_IF_TRUE",
            "JUMP_FORWARD_IF_FALSE_OR_POP",
            "JUMP_FORWARD_IF_TRUE_OR_POP",
        ):
            if cand in dis.opmap:
                cond_name = cand
                break
        if cond_name is None:
            self.skipTest("No conditional jump opcode available for BasicBlock.get_jump")

        target = BasicBlock([Instr(pick_opcode_name("LOAD_CONST"), 999), Instr(pick_opcode_name("RETURN_VALUE"))])
        bb2 = BasicBlock()
        bb2.extend([Instr(pick_opcode_name("LOAD_CONST"), 0), Instr(cond_name, target)])
        bb2.legalize(first_lineno=1)
        self.assertIs(bb2.get_jump(), target)

        trailing_name = None
        for cand in ("get_trailing_end", "get_trailing_try_end"):
            if hasattr(BasicBlock, cand):
                trailing_name = cand
                break

        if TryBegin is not None and TryEnd is not None and sys.version_info >= (3, 11) and trailing_name is not None:
            lbl = BasicBlock([Instr(pick_opcode_name("RETURN_VALUE"))])
            tb = TryBegin(target=lbl, push_lasti=False)
            te = TryEnd(tb)
            bb3 = BasicBlock([tb, Instr(pick_opcode_name("NOP")), te, Instr(pick_opcode_name("RETURN_VALUE"))])
            bb3.legalize(first_lineno=1)
            found = getattr(bb3, trailing_name)(0)
            self.assertTrue(found is None or isinstance(found, TryEnd))

    def test_cfg_from_bytecode_add_split_dead_blocks_and_to_code(self):
        fn = make_simple_function()
        bc = Bytecode.from_code(fn.__code__)
        cfg = ControlFlowGraph.from_bytecode(bc)
        self.assertIsInstance(cfg, ControlFlowGraph)
        self.assertGreaterEqual(len(cfg), 1)

        newb = cfg.add_block([Instr(pick_opcode_name("NOP"))])
        idx = cfg.get_block_index(newb)
        self.assertIsInstance(idx, int)

        block0 = cfg[0]
        if len(block0) >= 1:
            created = cfg.split_block(block0, 0)
            self.assertIs(created, block0)
        if len(block0) >= 2:
            created2 = cfg.split_block(block0, 1)
            self.assertIsInstance(created2, BasicBlock)

        dead = cfg.add_block([Instr(pick_opcode_name("LOAD_CONST"), 123), Instr(pick_opcode_name("RETURN_VALUE"))])
        deads = cfg.get_dead_blocks()
        self.assertIsInstance(deads, list)
        self.assertIn(dead, deads)

        bc2 = cfg.to_bytecode()
        self.assertIsInstance(bc2, Bytecode)

        ss = cfg.compute_stacksize()
        self.assertIsInstance(ss, int)

        code = cfg.to_code()
        self.assertIsInstance(code, types.CodeType)

    def test_closure_freevars_cellvars_roundtrip(self):
        outer = make_closure_function()
        inner = outer(5)
        bc = Bytecode.from_code(inner.__code__)
        self.assertIsInstance(bc.freevars, list)
        self.assertTrue(all(isinstance(x, str) for x in bc.freevars))

        code = bc.to_code()
        self.assertIsInstance(code, types.CodeType)
        self.assertIsInstance(code.co_freevars, tuple)

    def test_trybegin_tryend_presence_and_copy(self):
        if TryBegin is None or TryEnd is None or sys.version_info < (3, 11):
            self.skipTest("TryBegin/TryEnd not available in this environment")

        lbl = Label()
        tb = TryBegin(target=lbl, push_lasti=False)
        tb2 = tb.copy()
        self.assertIsNot(tb, tb2)
        self.assertEqual(tb.push_lasti, tb2.push_lasti)
        self.assertIsInstance(TryEnd(tb), TryEnd)

        bc = Bytecode()
        bc.extend(
            [
                tb,
                Instr(pick_opcode_name("LOAD_CONST"), 1),
                TryEnd(tb),
                lbl,
                Instr(pick_opcode_name("RETURN_VALUE")),
            ]
        )
        cbc = bc.to_concrete_bytecode()
        self.assertIsInstance(cbc, ConcreteBytecode)

    def test_optional_enums_binaryop_intrinsics_exist_if_applicable(self):
        if sys.version_info >= (3, 11):
            self.assertTrue("BINARY_OP" in dis.opmap)

        if sys.version_info >= (3, 12):
            if Intrinsic1Op is not None:
                self.assertTrue(hasattr(Intrinsic1Op, "INTRINSIC_1_INVALID"))
            if Intrinsic2Op is not None:
                self.assertTrue(hasattr(Intrinsic2Op, "INTRINSIC_2_INVALID"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
