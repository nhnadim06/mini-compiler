"""
=============================================================================
CSE 430 - Compiler Design Lab Project
PHASE 6: GUI (Graphical User Interface)
=============================================================================
Job: Creates a window where:
  - Code can be written in an editor
  - Code is compiled using the Compile button
  - Each phase's output is shown in a separate tab
=============================================================================
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import ply.lex as lex

from lexer import Lexer, errors_list as lexer_errors
from parser import Parser
from code_generator import Intel8086CodeGenerator
from timeline import SimpleCodeChecker


SAMPLE_CODE = """\
// =========================================
// MINI COMPILER QUALITY ANALYZER TEST #2
// =========================================

// ---------- Variable Declaration ----------
int a;
int b;
int result;
int temp;
int counter;

// ---------- Assignments ----------
a = 10;
b = 20;

// ---------- Overwritten Value ----------
temp = 5;
temp = 15;

// ---------- Arithmetic ----------
result = a + b;
print(result);

// ---------- Duplicate Code ----------
result = a + b;
print(result);

result = a + b;
print(result);

// ---------- Infinite Loop ----------
counter = 0;

while(counter < 5) {
    print(counter);
}

// ---------- Deep Nested Conditions ----------
if(a > 0) {
    if(b > 0) {
        if(result > 0) {
            print(result);
        }
    }
}

// ---------- Division By Zero ----------
result = a / 0;

// ---------- Performance Test ----------
result = a * 2;
result = a / 4;
result = a % 8;

// ---------- Function Test ----------
func int add() {
    int sum;
    sum = a + b;
    print(sum);
    return sum;
}

add(a, b);

// ---------- Recursion Test ----------
func int recurse(int n) {
    if(n > 0) {
        recurse(n - 1);
    }
    return 0;
}

recurse(2);
print(1);
"""


class CompilerGUI:
    def __init__(self, root):
        self.root          = root
        self.root.title("Mini Compiler By Nadim")
        self.root.geometry("1100x700")
        self.root.configure(bg='white')

        self.asm_generator = Intel8086CodeGenerator()
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # Title bar
        title_frame = tk.Frame(self.root, bg="#634CAF", pady=8)
        title_frame.pack(fill=tk.X)
        tk.Label(
            title_frame,
            text=" CSE 430 - Mini Compiler   |   University of Asia Pacific\n"
                 " Submitted to: Md. Shaiful Islam Ph.D. | Assistant Professor, CSE Department\n"
                 " Developed by: Nazmul Hoosain Nadim  | ID: 22101203",
            font=('Courier New', 12, 'bold'),
            bg='#634CAF', fg='white',
            justify=tk.CENTER
        ).pack()

        # Main content area
        main = tk.Frame(self.root, bg='white')
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left panel: Code Editor
        left = tk.Frame(main, bg='white')
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            left, text="Source Code Editor",
            font=('Courier New', 12, 'bold'),
            bg='white', fg='#333333'
        ).pack(anchor='w')

        self.input_text = scrolledtext.ScrolledText(
            left,
            font=('Courier New', 11),
            bg='white', fg='#000000',
            insertbackground='black',
            height=18, width=50,
            relief=tk.SOLID, borderwidth=1
        )
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=3)
        self.input_text.insert('1.0', SAMPLE_CODE)

        # Buttons
        btn_frame = tk.Frame(left, bg='white')
        btn_frame.pack(pady=5)

        tk.Button(
            btn_frame, text="⚡ Compile",
            command=self._compile,
            font=('Courier New', 10, 'bold'),
            bg="#4CAF50", fg='#634CAF',
            padx=15, pady=5, relief=tk.RAISED, cursor='hand2'
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="🗑 Clear",
            command=self._clear,
            font=('Courier New', 10),
            bg='#f44336', fg='#634CAF',
            padx=15, pady=5, relief=tk.RAISED, cursor='hand2'
        ).pack(side=tk.LEFT, padx=5)

        # Right panel: Output Tabs
        right = tk.Frame(main, bg='white')
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        tk.Label(
            right, text="Compiler Output",
            font=('Courier New', 12, 'bold'),
            bg='white', fg='#333333'
        ).pack(anchor='w')

        # Notebook styling
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='white', borderwidth=1)
        style.configure(
            'TNotebook.Tab',
            background='#e0e0e0', foreground='#000000',
            padding=[8, 4], font=('Courier New', 11)
        )
        style.map(
            'TNotebook.Tab',
            background=[('selected', '#634CAF')],
            foreground=[('selected', 'white')]
        )

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create one tab per phase
        tabs = [
            ("Tokens",       'txt_tokens'),
            ("Symbol Table", 'txt_symbols'),
            ("3AC Code",     'txt_tac'),
            ("Assembly",     'txt_assembly'),
            ("Diagnostics",  'txt_diagnostics'),
            ("Quality Report",   'txt_lifetime'),
        ]
        for tab_name, attr_name in tabs:
            frame  = tk.Frame(self.notebook, bg='white')
            widget = scrolledtext.ScrolledText(
                frame,
                font=('Courier New', 12),
                bg='white', fg='#000000',
                insertbackground='black',
                height=20,
                relief=tk.SOLID, borderwidth=1
            )
            widget.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            self.notebook.add(frame, text=tab_name)
            setattr(self, attr_name, widget)

    # ------------------------------------------------------------------
    # Compile Action
    # ------------------------------------------------------------------

    def _compile(self):
        """Runs all compiler phases when the Compile button is pressed"""
        import lexer as lexer_module
        lexer_module.errors_list.clear()

        raw_code = self.input_text.get('1.0', tk.END)

        # Clear all output panels
        for attr in ['txt_tokens', 'txt_symbols', 'txt_tac', 'txt_assembly', 'txt_diagnostics', 'txt_lifetime']:
            getattr(self, attr).delete('1.0', tk.END)

        # ---- PHASE 1: Lexical Analysis ----
        lexer_obj = lex.lex(module=Lexer())
        lexer_obj.input(raw_code)

        token_output  = f"{'TOKEN TYPE':<20} {'VALUE':<20} {'LINE'}\n"
        token_output += "-" * 50 + "\n"

        while True:
            tok = lexer_obj.token()
            if not tok:
                break
            token_output += f"{tok.type:<20} {str(tok.value):<20} {tok.lineno}\n"

        self.txt_tokens.insert('1.0', token_output)

        # ---- PHASE 2, 3, 4: Parse + Semantic + 3AC ----
        parser_obj = Parser()
        parser_obj.build()
        parser_obj.parse(raw_code)

        # Symbol Table output
        sym_output = f"{'VARIABLE':<20} {'TYPE':<15} {'SCOPE'}\n"
        sym_output += "-" * 50 + "\n"
        symbols    = sorted(parser_obj.symbol_table.get_all(), key=lambda s: s['scope'])
        for s in symbols:
            sym_output += f"{s['name']:<20} {s['type']:<15} {s['scope']}\n"
        self.txt_symbols.insert('1.0', sym_output)

        # 3AC output
        tac_output  = "Three Address Code (Intermediate Representation):\n"
        tac_output += "=" * 50 + "\n\n"
        for idx, instr in enumerate(parser_obj.intermediate_code, 1):
            op, a1, a2, res = instr['op'], instr['arg1'], instr['arg2'], instr['result']
            if op == '=':
                line = f"{res} = {a1}"
            elif op in ['+', '-', '*', '/', '%']:
                line = f"{res} = {a1} {op} {a2}"
            elif op in ['<', '<=', '>', '>=', '==', '!=']:
                line = f"{res} = {a1} {op} {a2}   (condition check)"
            elif op == 'label':
                line = f"\n{a1}:   ← Label"
            elif op == 'goto':
                line = f"GOTO {a1}"
            elif op == 'if_false':
                line = f"IF {a1} == false  →  GOTO {a2}"
            elif op == 'print':
                line = f"PRINT {a1}"
            elif op == 'func_start':
                line = f"\n--- Function '{a1}' Start ---"
            elif op == 'func_end':
                line = f"--- Function '{a1}' End ---\n"
            elif op == 'param':
                line = f"PARAM {a1}   (function argument)"
            elif op == 'call':
                line = f"{res} = CALL {a1} ({a2} arguments)"
            elif op == 'return':
                line = f"RETURN {a1 if a1 is not None else ''}"
            else:
                line = f"{res} = {a1} {op} {a2}"
            tac_output += f"({idx:>3})  {line}\n"
        self.txt_tac.insert('1.0', tac_output)

        # ---- PHASE 5: Assembly Code ----
        asm_lines = self.asm_generator.generate(parser_obj.intermediate_code)
        self.txt_assembly.insert('1.0', "\n".join(asm_lines))

        # ---- PHASE 7: Beginner Code Check ----
        analyzer = SimpleCodeChecker()
        analysis_report = analyzer.analyze(parser_obj, raw_code)
        self.txt_lifetime.insert('1.0', analysis_report)

        # ---- Diagnostics ----
        all_errors = lexer_module.errors_list + parser_obj.errors

        if all_errors:
            diag  = "⚠️  COMPILATION FAILED\n"
            diag += "=" * 45 + "\n\n"
            for i, err in enumerate(all_errors, 1):
                diag += f"[{i}]  {err}\n"
            self.txt_diagnostics.insert('1.0', diag)
            self.notebook.select(4)
            messagebox.showerror(
                "Compilation Error",
                f"{len(all_errors)} error(s) found.\nCheck the Diagnostics tab."
            )
        else:
            diag  = "✅  COMPILATION SUCCESSFUL\n"
            diag += "=" * 45 + "\n\n"
            diag += "Phase 1 - Lexical Analysis    : ✓ Passed\n"
            diag += "Phase 2 - Symbol Table         : ✓ Passed\n"
            diag += "Phase 3 - Syntax Analysis      : ✓ Passed\n"
            diag += "Phase 4 - Semantic Analysis    : ✓ Passed\n"
            diag += "Phase 5 - Intermediate Code    : ✓ Passed\n"
            diag += "Phase 6 - Code Generation      : ✓ Passed\n"
            diag += "Phase 7 - Easy Code Check      : ✓ Passed\n"
            diag += "\n" + "=" * 45 + "\n"
            diag += "🎉 Source code compiled successfully!\n"
            diag += f"   - Tokens generated     : {token_output.count(chr(10)) - 2}\n"
            diag += f"   - Symbols in table     : {len(symbols)}\n"
            diag += f"   - 3AC instructions     : {len(parser_obj.intermediate_code)}\n"
            diag += f"   - Assembly lines       : {len(asm_lines)}\n"
            self.txt_diagnostics.insert('1.0', diag)
            messagebox.showinfo("Success", "✅ Compilation Successful!\nAll phases completed without errors.")

    # ------------------------------------------------------------------
    # Clear Action
    # ------------------------------------------------------------------

    def _clear(self):
        """Clear all input and output fields"""
        self.input_text.delete('1.0', tk.END)
        for attr in ['txt_tokens', 'txt_symbols', 'txt_tac', 'txt_assembly', 'txt_diagnostics']:
            getattr(self, attr).delete('1.0', tk.END)