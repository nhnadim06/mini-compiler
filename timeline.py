"""
=============================================================================
CSE 430 - Compiler Design Lab Project
PHASE 7: CODE QUALITY ANALYZER
=============================================================================
Job: Deep analysis of compiled code quality across 3 severity levels:

  🔴 ERROR LEVEL   — Dead code, Infinite loops, Type mismatches,
                     Division by zero
  🟡 WARNING LEVEL — Duplicate code, Write-only vars, Overwritten values,
                     Deeply nested conditions
  🟢 SUGGESTION    — Naming issues, Performance tips, Grade & Score,
                     Function call depth report

Input: parser_obj (has intermediate_code + symbol_table), raw_code (string)
=============================================================================
"""


class CodeQualityChecker:

    # -------------------------------------------------------------------------
    # Constants
    # -------------------------------------------------------------------------
    SINGLE_LETTER_NAMES = set('abcdefghijklmnopqrstuvwxyz')
    MEANINGFUL_NAMES    = {
        'result', 'total', 'count', 'index', 'sum', 'value',
        'temp', 'flag', 'max', 'min', 'avg', 'num', 'len',
    }

    def __init__(self):
        self.reset()

    def reset(self):
        """Clear all state so the checker can be reused across compilations."""
        # variable tracking
        self.var_tracker = {}
        self.unused_vars = []

        # issue buckets
        self.errors      = []      # 🔴  plain strings
        self.warnings    = []      # 🟡  plain strings
        self.suggestions = []      # 🟢  list of (category, message) tuples

        # internal diagnostics — checker's own errors shown at bottom of report
        self._internal_warnings = []

        # scoring
        self.score = 100
        self.grade = 'A'

    # -------------------------------------------------------------------------
    # Helper: safely run one check, catch & record any unexpected exception
    # -------------------------------------------------------------------------

    def _run_check(self, method, *args, check_name=None):
        """
        Call method(*args).  If it raises, record the failure in
        _internal_warnings so the rest of the report still renders.

        Usage:
            self._run_check(self._check_dead_code, ic, check_name="Dead code")
        The last keyword-only argument 'check_name' is optional but recommended
        so error messages are human-readable.

        Because *args collects positional args, the check_name keyword must
        always be passed as keyword, never positional.
        """
        name = check_name or method.__name__
        try:
            method(*args)
        except Exception as e:
            self._internal_warnings.append(
                f"'{name}' encountered an unexpected error "
                f"({type(e).__name__}: {e}) and was skipped."
            )

    def _suggest(self, category, message):
        """Append a typed suggestion — always use this instead of
        self.suggestions.append() so the category label is always stored."""
        self.suggestions.append((category, message))

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def analyze(self, parser_obj, raw_code):
        """Run all checks and return the full report string."""
        self.reset()

        # ── Guard: make sure parser gave us valid objects ──────────────────────
        try:
            ic  = parser_obj.intermediate_code
            sym = parser_obj.symbol_table
            if not isinstance(ic, list):
                raise TypeError("intermediate_code is not a list")
        except Exception as e:
            return (
                "\n  ⚠️  CODE QUALITY ANALYZER — INTERNAL ERROR\n"
                f"  Could not read compiler output: {e}\n"
                "  Please compile the code again and try once more.\n"
            )

        # ── Variable tracker (foundation for all checks) ───────────────────────
        try:
            self._build_var_tracker(sym, ic)
        except Exception as e:
            self._internal_warnings.append(
                f"Variable tracker failed ({type(e).__name__}: {e}). "
                "Some checks may be incomplete."
            )

        # ── 🔴 Error checks ────────────────────────────────────────────────────
        self._run_check(self._check_dead_code,        ic,      check_name="Dead code detector")
        self._run_check(self._check_infinite_loops,   ic,      check_name="Infinite loop detector")
        self._run_check(self._check_type_mismatch,    ic, sym, check_name="Type mismatch checker")
        self._run_check(self._check_division_by_zero, ic,      check_name="Division-by-zero checker")

        # ── 🟡 Warning checks ──────────────────────────────────────────────────
        self._run_check(self._check_duplicate_blocks,          ic, check_name="Duplicate code detector")
        self._run_check(self._check_write_only_vars,               check_name="Write-only variable checker")
        self._run_check(self._check_overwritten_values,        ic, check_name="Overwritten value checker")
        self._run_check(self._check_deeply_nested_conditions,  ic, check_name="Nesting depth checker")

        # ── 🟢 Suggestion checks ───────────────────────────────────────────────
        self._run_check(self._check_variable_naming,     sym,  check_name="Naming checker")
        self._run_check(self._check_performance_tips,    ic,   check_name="Performance tips")
        self._run_check(self._check_function_call_depth, ic,   check_name="Call depth analyzer")

        # ── Score & report ─────────────────────────────────────────────────────
        try:
            self._compute_score()
        except Exception as e:
            self._internal_warnings.append(f"Scoring failed ({type(e).__name__}: {e}).")
            self.score = 0
            self.grade = '?'

        return self._build_report()

    # =========================================================================
    # VARIABLE TRACKER  (shared foundation)
    # =========================================================================

    def _build_var_tracker(self, sym, ic):
        for symbol in sym.get_all():
            name = symbol['name']
            if name.startswith('t') and name[1:].isdigit():
                continue                        # skip compiler temporaries
            if name.startswith('L') and name[1:].isdigit():
                continue                        # skip labels
            self.var_tracker[name] = {
                'type':          symbol['type'],
                'scope':         symbol['scope'],
                'used':          False,
                'times_read':    0,
                'times_written': 0,
                'write_values':  [],            # values written (for overwrite check)
                'first_write_line': None,       # source line of first write
            }

        for instr in ic:
            op, arg1, arg2, result = (
                instr['op'], instr['arg1'], instr['arg2'], instr['result']
            )
            lineno = instr.get('lineno')
            # writes
            if result and str(result) in self.var_tracker:
                entry = self.var_tracker[str(result)]
                entry['times_written'] += 1
                if arg1 is not None:
                    entry['write_values'].append(arg1)
                if entry['first_write_line'] is None and lineno:
                    entry['first_write_line'] = lineno
            # reads
            for arg in [arg1, arg2]:
                if arg and str(arg) in self.var_tracker:
                    self.var_tracker[str(arg)]['used']        = True
                    self.var_tracker[str(arg)]['times_read'] += 1

        self.unused_vars = [
            v for v, info in self.var_tracker.items() if not info['used']
        ]

    # =========================================================================
    # 🔴 ERROR CHECKS
    # =========================================================================

    def _check_dead_code(self, ic):
        """
        Dead code: instructions that appear after an unconditional jump (goto /
        return) and before the next label — they can never be reached.
        func_end / func_start are structural markers, never dead code.
        """
        dead_segments = []
        in_dead       = False
        dead_start    = 0
        dead_lineno   = None

        STRUCTURAL = {'label', 'func_start', 'func_end'}

        for idx, instr in enumerate(ic):
            op = instr['op']

            if in_dead:
                if op in STRUCTURAL:
                    # structural marker ends the dead zone
                    if dead_start <= idx - 1:
                        dead_segments.append((dead_start, idx - 1, dead_lineno))
                    in_dead = False

            else:
                if op in ('goto', 'return') and idx + 1 < len(ic):
                    next_op = ic[idx + 1]['op']
                    if next_op not in STRUCTURAL:
                        in_dead     = True
                        dead_start  = idx + 1
                        dead_lineno = ic[idx + 1].get('lineno')

        if in_dead and dead_start <= len(ic) - 1:
            dead_segments.append((dead_start, len(ic) - 1, dead_lineno))

        for start, end, lineno in dead_segments:
            count    = end - start + 1
            line_msg = f" (source line {lineno})" if lineno else ""
            self.errors.append(
                f"DEAD CODE{line_msg}: {count} instruction(s) can never be executed — "
                f"they appear after an unconditional jump/return with no label to reach them."
            )

    # -------------------------------------------------------------------------

    def _check_infinite_loops(self, ic):
        """
        Infinite loop heuristic (improved):
          1. Find label..goto pairs that form backward jumps (loops).
          2. Extract the condition temp from if_false, then trace it back
             through the 3AC data-flow to find the real user variables it
             depends on (e.g. t4 = count < 4  →  depends on 'count').
          3. Check whether ANY of those user variables (or the temp itself)
             is written inside the loop body.
          4. Also check function calls in the body — if a called function
             writes any user variable, treat the loop as safe.
          5. Only flag when nothing in the body can affect the condition.
        """
        # ── Build a data-flow map: result -> {arg1, arg2} for the whole ic ──────
        # Used to trace temporaries back to their source variables.
        def_map = {}   # str(result) -> (arg1, arg2)
        for instr in ic:
            if instr['result'] is not None:
                def_map[str(instr['result'])] = (
                    str(instr['arg1'])  if instr['arg1']  is not None else None,
                    str(instr['arg2'])  if instr['arg2']  is not None else None,
                )

        def _is_temp(v):
            return v is not None and v.startswith('t') and v[1:].isdigit()

        def _source_vars(var, visited=None):
            """
            Walk the def_map backwards from `var` and collect all
            non-temporary variables that ultimately feed into it.
            """
            if visited is None:
                visited = set()
            if var is None or var in visited:
                return set()
            visited.add(var)
            if not _is_temp(var):
                return {var}          # it's already a user variable
            sources = set()
            if var in def_map:
                for src in def_map[var]:
                    sources |= _source_vars(src, visited)
            return sources

        # ── Build call graph: func_name -> set of user vars it assigns ──────────
        func_writes  = {}
        current_func = None
        for instr in ic:
            op = instr['op']
            if op == 'func_start':
                current_func = instr['arg1']
                func_writes.setdefault(current_func, set())
            elif op == 'func_end':
                current_func = None
            elif current_func is not None and instr['result'] is not None:
                if op in ('=', '+', '-', '*', '/', '%'):
                    r = str(instr['result'])
                    if not _is_temp(r):
                        func_writes[current_func].add(r)

        # ── Find loop ranges ────────────────────────────────────────────────────
        label_pos = {}
        for idx, instr in enumerate(ic):
            if instr['op'] == 'label':
                label_pos[instr['arg1']] = idx

        for goto_idx, instr in enumerate(ic):
            if instr['op'] != 'goto':
                continue
            target_label = instr['arg1']
            if target_label not in label_pos:
                continue
            loop_start = label_pos[target_label]
            if loop_start >= goto_idx:
                continue                        # forward jump, not a loop

            body = ic[loop_start + 1: goto_idx + 1]

            # ── Find condition temp from if_false ──────────────────────────────
            cond_temp   = None
            loop_lineno = None
            for bi in body:
                if bi['op'] == 'if_false':
                    cond_temp   = str(bi['arg1']) if bi['arg1'] is not None else None
                    loop_lineno = bi.get('lineno')
                    break

            if cond_temp is None:
                continue

            # ── Trace cond_temp back to real user variables ────────────────────
            cond_sources = _source_vars(cond_temp)
            # remove pure labels / things that look like labels
            cond_sources = {v for v in cond_sources if not v.startswith('L')}

            if not cond_sources:
                continue   # can't determine sources → skip (avoid false positive)

            # ── Collect user variables written inside the loop body ────────────
            written_user = set()
            calls_in_body = []
            for bi in body:
                if bi['result'] is not None and bi['op'] in ('=', '+', '-', '*', '/', '%'):
                    r = str(bi['result'])
                    if not _is_temp(r):
                        written_user.add(r)
                if bi['op'] == 'call':
                    calls_in_body.append(bi['arg1'])

            # ── Check if any source variable is updated in the body ────────────
            if cond_sources & written_user:
                continue    # at least one source variable IS updated → safe

            # ── Check if any called function updates a source variable ──────────
            func_can_update = False
            for callee in calls_in_body:
                if callee in func_writes:
                    if cond_sources & func_writes[callee]:
                        func_can_update = True
                        break
                    # Conservative: if function writes ANY user var, treat as safe
                    if func_writes[callee]:
                        func_can_update = True
                        break

            if func_can_update:
                continue

            src_names = ', '.join(f"'{v}'" for v in sorted(cond_sources))
            line_msg  = f" (source line {loop_lineno})" if loop_lineno else ""
            self.errors.append(
                f"INFINITE LOOP{line_msg}: Loop condition depends on {src_names}, "
                f"but the loop body never updates {'it' if len(cond_sources) == 1 else 'them'} "
                f"— this loop will run forever."
            )

    # -------------------------------------------------------------------------

    def _check_type_mismatch(self, ic, sym):
        """
        Type mismatch: an int variable receives a float literal, or vice-versa.
        We check every '=' instruction where arg1 is a numeric literal.
        """
        for instr in ic:
            if instr['op'] != '=':
                continue
            result  = instr['result']
            value   = instr['arg1']
            lineno  = instr.get('lineno')

            if result not in self.var_tracker:
                continue
            declared_type = self.var_tracker[result]['type']
            if not isinstance(value, (int, float)):
                continue

            if declared_type == 'int' and isinstance(value, float):
                line_msg = f" (line {lineno})" if lineno else ""
                self.errors.append(
                    f"TYPE MISMATCH{line_msg}: '{result}' is declared as 'int' but "
                    f"receives float value {value}. This truncates the decimal part."
                )

    # -------------------------------------------------------------------------

    def _check_division_by_zero(self, ic):
        """
        Division by zero: any '/' or '%' instruction where arg2 is the
        literal integer 0.  This is a static (compile-time) guarantee that
        the program will crash at runtime.
        """
        for idx, instr in enumerate(ic):
            if instr['op'] in ('/', '%') and instr['arg2'] == 0:
                op_name  = 'Division' if instr['op'] == '/' else 'Modulo'
                result   = instr['result'] or '?'
                lineno   = instr.get('lineno')
                line_msg = f" (line {lineno})" if lineno else ""
                self.errors.append(
                    f"DIVISION BY ZERO{line_msg}: '{result} = {instr['arg1']} "
                    f"{instr['op']} 0'. "
                    f"{op_name} by zero will crash the program at runtime."
                )

    # =========================================================================
    # 🟡 WARNING CHECKS
    # =========================================================================

    def _check_duplicate_blocks(self, ic):
        """
        Duplicate code: look for identical consecutive sequences of ≥ 3
        arithmetic / assignment instructions that appear more than once.
        We compare (op, arg1, arg2) tuples, ignoring result temps.
        """
        MIN_SEQ = 3

        def sig(instr):
            return (instr['op'], str(instr['arg1']), str(instr['arg2']))

        sigs    = [sig(i) for i in ic]
        seen    = {}
        flagged = set()

        for start in range(len(sigs) - MIN_SEQ + 1):
            key = tuple(sigs[start: start + MIN_SEQ])
            if key in seen:
                first = seen[key]
                pair  = (first, start)
                if pair not in flagged:
                    flagged.add(pair)
                    line1 = ic[first].get('lineno')
                    line2 = ic[start].get('lineno')
                    loc1  = f"line {line1}" if line1 else f"instruction {first + 1}"
                    loc2  = f"line {line2}" if line2 else f"instruction {start + 1}"
                    self.warnings.append(
                        f"DUPLICATE CODE: A block of {MIN_SEQ} similar instructions "
                        f"appears at {loc1} and again at {loc2}. "
                        f"Consider extracting it into a function."
                    )
            else:
                seen[key] = start

    # -------------------------------------------------------------------------

    def _check_write_only_vars(self):
        """
        Write-only variables: written at least once but never read.
        (Subset of unused_vars check, but these are more dangerous — the
        programmer clearly intended to use them.)
        """
        for var, info in self.var_tracker.items():
            if info['times_written'] > 0 and info['times_read'] == 0:
                line_msg = f" (first assigned at line {info['first_write_line']})" \
                           if info.get('first_write_line') else ""
                self.warnings.append(
                    f"WRITE-ONLY VARIABLE: '{var}' ({info['type']}){line_msg} is assigned "
                    f"{info['times_written']} time(s) but its value is never read. "
                    f"The assignment(s) have no effect."
                )

    # -------------------------------------------------------------------------

    def _check_overwritten_values(self, ic):
        """
        Overwritten value: a variable is assigned a value that is immediately
        overwritten before being read — the first write is wasted.
        """
        last_write  = {}   # var -> (instruction index, lineno) of last unread write
        overwritten = set()

        for idx, instr in enumerate(ic):
            op, arg1, arg2, result = (
                instr['op'], instr['arg1'], instr['arg2'], instr['result']
            )
            lineno = instr.get('lineno')
            # reads
            for arg in [arg1, arg2]:
                if arg and str(arg) in last_write:
                    del last_write[str(arg)]    # consumed → no longer "pending"

            # writes
            if result and str(result) in self.var_tracker and op in ('=', '+', '-', '*', '/', '%'):
                r = str(result)
                if r in last_write and r not in overwritten:
                    overwritten.add(r)
                    prev_idx, prev_line = last_write[r]
                    line_msg = f" (line {prev_line})" if prev_line else f" (instruction {prev_idx + 1})"
                    self.warnings.append(
                        f"OVERWRITTEN VALUE: '{r}' is assigned a value at{line_msg} "
                        f"that is overwritten before being used. The earlier assignment is wasted."
                    )
                last_write[r] = (idx, lineno)

    # -------------------------------------------------------------------------

    def _check_deeply_nested_conditions(self, ic):
        """
        Deeply nested conditions: track how many if_false instructions are
        'open' (their false-label has not yet been emitted) at any point.
        If the open depth reaches 3 or more, flag it.

        Strategy:
          - Each 'if_false' instruction opens a new conditional level.
            Record its false_label.
          - Each 'label' instruction that matches a recorded false_label
            closes that level.
          - Track the running depth; record the maximum.
        """
        THRESHOLD    = 3
        open_labels  = []      # stack of false-labels currently open
        max_depth    = 0
        peak_instr   = 0

        for idx, instr in enumerate(ic):
            op = instr['op']

            if op == 'if_false':
                open_labels.append(instr['arg2'])   # arg2 = false_label
                depth = len(open_labels)
                if depth > max_depth:
                    max_depth  = depth
                    peak_instr = idx + 1

            elif op == 'label' and instr['arg1'] in open_labels:
                open_labels.remove(instr['arg1'])

        if max_depth >= THRESHOLD:
            peak_instr_lineno = ic[peak_instr - 1].get('lineno') if peak_instr > 0 else None
            line_msg = f" (around line {peak_instr_lineno})" if peak_instr_lineno else f" (around instruction {peak_instr})"
            self.warnings.append(
                f"DEEPLY NESTED CONDITIONS{line_msg}: Maximum nesting depth is {max_depth} "
                f"level(s). More than {THRESHOLD - 1} nested if/else blocks make code hard "
                f"to read and maintain. Consider extracting inner logic into "
                f"separate functions or using early returns."
            )

    # =========================================================================
    # 🟢 SUGGESTION CHECKS
    # =========================================================================

    def _check_variable_naming(self, sym):
        """
        Naming suggestions:
          • Single-letter names  (except 'i' / 'j' / 'k' in loop context)
          • ALL_CAPS names that are not constants
          • Very long names (> 20 chars)
        """
        for symbol in sym.get_all():
            name = symbol['name']
            if name.startswith('t') and name[1:].isdigit():
                continue
            if name.startswith('L') and name[1:].isdigit():
                continue

            if len(name) == 1 and name.lower() in self.SINGLE_LETTER_NAMES:
                if name.lower() not in ('i', 'j', 'k'):
                    self._suggest(
                        'NAMING',
                        f"'{name}' is a single-letter variable name. "
                        f"Use a descriptive name so the code is easier to read."
                    )

            elif name == name.upper() and len(name) > 1 and '_' not in name:
                self._suggest(
                    'NAMING',
                    f"'{name}' looks like a constant (all caps). "
                    f"If it's not a constant, use camelCase or snake_case instead."
                )

            elif len(name) > 20:
                self._suggest(
                    'NAMING',
                    f"'{name}' is very long ({len(name)} chars). "
                    f"Consider a shorter but still meaningful name."
                )

    # -------------------------------------------------------------------------

    def _check_performance_tips(self, ic):
        """
        Performance suggestions based on 3AC patterns.
        """
        # 1. Repeated multiplication by 2 (use left-shift instead)
        mul2_vars = set()
        for instr in ic:
            if instr['op'] == '*' and str(instr['arg2']) == '2':
                var = str(instr['arg1'])
                if var not in mul2_vars:
                    mul2_vars.add(var)
                    self._suggest(
                        'PERFORMANCE',
                        f"'{var} * 2' can be replaced with a "
                        f"left-shift '{var} << 1' — faster on most CPUs."
                    )

        # 2. Division by a power of 2 → right-shift
        import math
        div_power2 = set()
        for instr in ic:
            if instr['op'] == '/' and isinstance(instr['arg2'], int):
                n = instr['arg2']
                if n > 1 and (n & (n - 1)) == 0:
                    bits = int(math.log2(n))
                    var  = str(instr['arg1'])
                    if var not in div_power2:
                        div_power2.add(var)
                        self._suggest(
                            'PERFORMANCE',
                            f"'{var} / {n}' — since {n} is a power "
                            f"of 2 you can use '{var} >> {bits}' instead."
                        )

        # 3. Modulo by power of 2 → bitwise AND
        mod_power2 = set()
        for instr in ic:
            if instr['op'] == '%' and isinstance(instr['arg2'], int):
                n = instr['arg2']
                if n > 1 and (n & (n - 1)) == 0:
                    var = str(instr['arg1'])
                    if var not in mod_power2:
                        mod_power2.add(var)
                        self._suggest(
                            'PERFORMANCE',
                            f"'{var} % {n}' — use "
                            f"'{var} & {n - 1}' (bitwise AND) instead. Same result, faster."
                        )

        # 4. Print inside a loop
        # Build label positions first
        label_pos = {}
        for idx, instr in enumerate(ic):
            if instr['op'] == 'label':
                label_pos[instr['arg1']] = idx
        
        # Find loop ranges: backward jumps (goto to earlier label)
        loop_instrs = []
        for idx, instr in enumerate(ic):
            if instr['op'] == 'goto':
                target_label = instr['arg1']
                if target_label in label_pos:
                    loop_start = label_pos[target_label]
                    if loop_start < idx:  # backward jump = loop
                        # Check for prints in the loop body (between label and goto)
                        for loop_idx in range(loop_start + 1, idx):
                            if ic[loop_idx]['op'] == 'print':
                                loop_instrs.append(ic[loop_idx])
        
        if loop_instrs:
            self._suggest(
                'PERFORMANCE',
                f"print() is called {len(loop_instrs)} time(s) inside "
                f"a loop. I/O operations are slow — consider collecting values first "
                f"and printing once after the loop."
            )

    # -------------------------------------------------------------------------

    def _check_function_call_depth(self, ic):
        """
        Function call depth analysis:
          1. Build a call graph: func_name -> set of functions it calls.
          2. For each function, compute its max call chain length (DFS).
          3. Detect direct recursion (a function that calls itself).
          4. Report a summary of all functions and their call counts,
             plus a warning if any function has a very deep call chain (≥4).

        Detection uses func_start / func_end markers to know which
        function each 'call' instruction belongs to.
        """
        DEEP_THRESHOLD = 4

        # ── 1. Build call graph ──
        call_graph   = {}   # caller -> {callee: count}
        current_func = '__main__'
        call_graph[current_func] = {}

        for instr in ic:
            op = instr['op']
            if op == 'func_start':
                current_func = instr['arg1']
                if current_func not in call_graph:
                    call_graph[current_func] = {}
            elif op == 'func_end':
                current_func = '__main__'
            elif op == 'call':
                callee = instr['arg1']
                call_graph[current_func][callee] = (
                    call_graph[current_func].get(callee, 0) + 1
                )

        # ── 2. Detect direct recursion ──
        recursive_funcs = [
            f for f, callees in call_graph.items()
            if f in callees and f != '__main__'
        ]
        for func in recursive_funcs:
            count = call_graph[func][func]
            self._suggest(
                'CALL DEPTH',
                f"Function '{func}' calls itself "
                f"{count} time(s). Make sure there is a proper base "
                f"case to prevent a stack overflow."
            )

        # ── 3. Compute max call chain depth (DFS with cycle guard) ──
        def max_depth(func, visited):
            if func not in call_graph or func in visited:
                return 0
            visited.add(func)
            callees = call_graph[func]
            if not callees:
                visited.discard(func)
                return 1
            d = 1 + max((max_depth(c, visited) for c in callees), default=0)
            visited.discard(func)
            return d

        # ── 4. Build the summary report ──
        all_funcs  = [f for f in call_graph if f != '__main__']
        total_calls = sum(
            sum(v.values()) for v in call_graph.values()
        )

        if all_funcs:
            func_list = ', '.join(f"'{f}'" for f in sorted(all_funcs))
            self._suggest(
                'CALL DEPTH',
                f"{len(all_funcs)} function(s) defined "
                f"({func_list}). Total call-site(s): {total_calls}. "
                f"Call breakdown: "
                + '; '.join(
                    f"'{caller}' calls "
                    + ', '.join(
                        f"'{c}' x{n}" for c, n in sorted(callees.items())
                    )
                    for caller, callees in sorted(call_graph.items())
                    if callees
                ) + '.'
            )

            # deep chain warning
            for func in all_funcs:
                depth = max_depth(func, set())
                if depth >= DEEP_THRESHOLD:
                    self._suggest(
                        'CALL DEPTH',
                        f"'{func}' has a call chain depth of "
                        f"{depth} level(s). Chains longer than {DEEP_THRESHOLD - 1} "
                        f"can make debugging and stack-tracing difficult."
                    )
        else:
            self._suggest(
                'CALL DEPTH',
                "No user-defined functions found. "
                "All logic is in the main body."
            )

    # =========================================================================
    # SCORING
    # =========================================================================

    def _compute_score(self):
        """
        Start at 100 and deduct points based on findings.

        Deductions:
          🔴 Errors       → -15 each
          🟡 Warnings     → -7  each
          🟢 Suggestions  → -2  each
          Unused vars     → -3  each
        """
        self.score  = 100
        self.score -= len(self.errors)      * 15
        self.score -= len(self.warnings)    * 7
        self.score -= len(self.suggestions) * 2
        self.score -= len(self.unused_vars) * 3
        self.score  = max(0, self.score)    # floor at 0

        if   self.score >= 90: self.grade = 'A'
        elif self.score >= 80: self.grade = 'B'
        elif self.score >= 70: self.grade = 'C'
        elif self.score >= 55: self.grade = 'D'
        else:                  self.grade = 'F'

    # =========================================================================
    # REPORT BUILDER
    # =========================================================================

    def _build_report(self):
        W  = 56          # box width
        lines = []

        def box_line(content='', fill='─', side='│'):
            if content == '':
                return f"├{'─' * W}┤"
            padded = f" {content}"
            padded = padded.ljust(W)
            return f"{side}{padded}{side}"


        # ── Score Card ────────────────────────────────────────────────────────
        grade_bar = self._score_bar(self.score)
        grade_emoji = {'A': '🏆', 'B': '🥈', 'C': '🥉', 'D': '⚠️', 'F': '❌'}.get(self.grade, '')
        lines.append(f"  OVERALL QUALITY SCORE")
        lines.append(f"  {'─' * 40}")
        lines.append(f"  Score : {self.score:>3}/100   {grade_bar}")
        lines.append(f"  Grade : {grade_emoji}  {self.grade}")
        lines.append("")

        # deduction table
        lines.append(f"  Deduction Breakdown:")
        lines.append(f"  {'Item':<32} {'Count':>5}   {'Points Lost':>10}")
        lines.append(f"  {'─' * 52}")
        lines.append(f"  {'🔴 Errors':<32} {len(self.errors):>5}   {len(self.errors)*15:>10}")
        lines.append(f"  {'🟡 Warnings':<32} {len(self.warnings):>5}   {len(self.warnings)*7:>10}")
        lines.append(f"  {'🟢 Suggestions':<32} {len(self.suggestions):>5}   {len(self.suggestions)*2:>10}")
        lines.append(f"  {'📦 Unused Variables':<32} {len(self.unused_vars):>5}   {len(self.unused_vars)*3:>10}")
        lines.append("")

        # ── Variable Summary ──────────────────────────────────────────────────
        total = len(self.var_tracker)
        used  = total - len(self.unused_vars)
        lines.append(f"  VARIABLE SUMMARY")
        lines.append(f"  {'─' * 40}")
        lines.append(f"  Total declared : {total}")
        lines.append(f"  In use         : {used}")
        lines.append(f"  Unused         : {len(self.unused_vars)}")
        lines.append("")

        if self.var_tracker:
            header = f"  {'Variable':<16} {'Type':<10} {'Reads':>6} {'Writes':>7}  Status"
            lines.append(header)
            lines.append(f"  {'─' * 52}")
            for var, info in sorted(self.var_tracker.items()):
                status = '✓ USED' if info['used'] else '✗ UNUSED'
                lines.append(
                    f"  {var:<16} {info['type']:<10} "
                    f"{info['times_read']:>6} {info['times_written']:>7}  {status}"
                )
            lines.append("")

        # ── 🔴 Errors ─────────────────────────────────────────────────────────
        lines.append(f"{'━' * (W + 2)}")
        lines.append(f"  🔴 ERRORS  ({len(self.errors)} found)  [-15 pts each]")
        lines.append(f"{'━' * (W + 2)}")
        if self.errors:
            for i, err in enumerate(self.errors, 1):
                lines.append(f"  [{i}] {err}")
                lines.append("")
        else:
            lines.append("  ✅ No errors detected. Great work!")
            lines.append("")

        # ── 🟡 Warnings ───────────────────────────────────────────────────────
        lines.append(f"{'━' * (W + 2)}")
        lines.append(f"  🟡 WARNINGS  ({len(self.warnings)} found)  [-7 pts each]")
        lines.append(f"{'━' * (W + 2)}")
        if self.warnings:
            for i, w in enumerate(self.warnings, 1):
                lines.append(f"  [{i}] {w}")
                lines.append("")
        else:
            lines.append("  ✅ No warnings. Nicely done!")
            lines.append("")

        # ── 🟢 Suggestions ────────────────────────────────────────────────────
        lines.append(f"{'━' * (W + 2)}")
        lines.append(f"  🟢 SUGGESTIONS  ({len(self.suggestions)} found)  [-2 pts each]")
        lines.append(f"{'━' * (W + 2)}")
        if self.suggestions:
            # category labels with icons
            cat_icons = {
                'NAMING':      'NAMING',
                'PERFORMANCE': 'PERFORMANCE',
                'CALL DEPTH':  'CALL DEPTH',
            }
            # group by category, preserving insertion order
            from collections import OrderedDict
            grouped = OrderedDict()
            for cat, msg in self.suggestions:
                grouped.setdefault(cat, []).append(msg)

            global_idx = 1
            for cat, msgs in grouped.items():
                label = cat_icons.get(cat, f'💡 {cat}')
                lines.append(f"  {'─' * 50}")
                lines.append(f"  {label}")
                lines.append(f"  {'─' * 50}")
                for msg in msgs:
                    lines.append(f"  [{global_idx}] {msg}")
                    lines.append("")
                    global_idx += 1
        else:
            lines.append("  ✅ Code follows best practices. Excellent!")
            lines.append("")

        # ── ⚙️  Internal checker diagnostics (shown only if something failed) ──
        if self._internal_warnings:
            lines.append(f"{'━' * (W + 2)}")
            lines.append(f"  ⚙️  CHECKER DIAGNOSTICS  ({len(self._internal_warnings)} issue(s))")
            lines.append(f"{'━' * (W + 2)}")
            lines.append("  One or more checks were skipped due to unexpected errors.")
            lines.append("  The rest of the report is still valid.")
            lines.append("")
            for i, w in enumerate(self._internal_warnings, 1):
                lines.append(f"  [{i}] {w}")
            lines.append("")

        # ── Footer ────────────────────────────────────────────────────────────
        lines.append(f"{'─' * (W + 2)}")
        total_issues = len(self.errors) + len(self.warnings) + len(self.suggestions)
        if total_issues == 0:
            lines.append(f"  🎉 Perfect code! Zero issues found.")
        elif self.grade in ('A', 'B'):
            lines.append(f"  👍 Good code! Fix {total_issues} issue(s) to reach perfection.")
        else:
            lines.append(f"  🔧 {total_issues} issue(s) found. Review errors first, then warnings.")
        lines.append(f"{'─' * (W + 2)}")
        lines.append("")

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Helper: ASCII score bar
    # -------------------------------------------------------------------------
    @staticmethod
    def _score_bar(score, width=20):
        filled = round(score / 100 * width)
        bar    = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"


# ---------------------------------------------------------------------------
# Backward-compatibility alias — gui.py imports SimpleCodeChecker
# ---------------------------------------------------------------------------
SimpleCodeChecker = CodeQualityChecker