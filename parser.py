"""
=============================================================================
CSE 430 - Compiler Design Lab Project
PHASE 3 + 4: PARSER AND SEMANTIC ANALYZER
=============================================================================
"""

import ply.yacc as yacc
from lexer import Lexer, build_lexer
from symbol_table import SymbolTable


class Parser:
    tokens = Lexer.tokens

    precedence = (
        ('left', 'PLUS', 'MINUS'),
        ('left', 'TIMES', 'DIVIDE', 'MODULO'),
    )

    def __init__(self):
        self.symbol_table      = SymbolTable()
        self.intermediate_code = []
        self.temp_count        = 0
        self.label_count       = 0
        self.errors            = []
        self.pending_params    = []  # Store params to register after scope entry
        self._current_lineno   = 1  # tracks source line for emit()

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def emit(self, op, arg1=None, arg2=None, result=None, lineno=None):
        instruction = {
            'op':     op,
            'arg1':   arg1,
            'arg2':   arg2,
            'result': result,
            'lineno': lineno if lineno is not None else self._current_lineno,
        }
        self.intermediate_code.append(instruction)
        return result

    # ==================================================================
    # GRAMMAR RULES
    # ==================================================================

    def p_program(self, p):
        """program : statement_list"""
        p[0] = ('program', p[1])

    def p_statement_list_multiple(self, p):
        """statement_list : statement_list statement"""
        p[0] = p[1] + [p[2]]

    def p_statement_list_single(self, p):
        """statement_list : statement"""
        p[0] = [p[1]]

    def p_statement(self, p):
        """statement : declaration
                     | assignment
                     | print_statement
                     | if_statement
                     | while_statement
                     | for_statement
                     | func_definition
                     | func_call_stmt
                     | block"""
        p[0] = p[1]

    # --- Declaration ---
    def p_declaration_only(self, p):
        """declaration : type ID SEMICOLON"""
        var_type, var_name = p[1], p[2]
        self._current_lineno = p.lineno(2)
        if self.symbol_table.lookup_current_scope(var_name):
            self.errors.append(f"Semantic Error: '{var_name}' already declared in this scope")
        else:
            self.symbol_table.insert(var_name, var_type)
        p[0] = ('declaration', var_type, var_name)

    def p_declaration_init(self, p):
        """declaration : type ID ASSIGN expression SEMICOLON"""
        var_type, var_name, expr = p[1], p[2], p[4]
        self._current_lineno = p.lineno(2)
        if self.symbol_table.lookup_current_scope(var_name):
            self.errors.append(f"Semantic Error: '{var_name}' already declared in this scope")
        else:
            self.symbol_table.insert(var_name, var_type, expr)
            self.emit('=', expr, None, var_name, lineno=p.lineno(2))
        p[0] = ('declaration_init', var_type, var_name, expr)

    def p_type(self, p):
        """type : INT
               | FLOAT
               | VOID"""
        p[0] = p[1]

    # --- Assignment ---
    def p_assignment(self, p):
        """assignment : ID ASSIGN expression SEMICOLON"""
        var_name, expr = p[1], p[3]
        self._current_lineno = p.lineno(1)
        if not self.symbol_table.lookup(var_name):
            self.errors.append(f"Semantic Error: Variable '{var_name}' has not been declared")
        self.emit('=', expr, None, var_name, lineno=p.lineno(1))
        p[0] = ('assignment', var_name, expr)

    # --- Print ---
    def p_print_statement(self, p):
        """print_statement : PRINT LPAREN expression RPAREN SEMICOLON"""
        self._current_lineno = p.lineno(1)
        self.emit('print', p[3], None, None, lineno=p.lineno(1))
        p[0] = ('print', p[3])

    # --- Block ---
    def p_block(self, p):
        """block : LBRACE scope_entry statement_list RBRACE"""
        self.symbol_table.exit_scope()
        p[0] = ('block', p[3])

    def p_block_empty(self, p):
        """block : LBRACE scope_entry RBRACE"""
        self.symbol_table.exit_scope()
        p[0] = ('block', [])

    def p_scope_entry(self, p):
        """scope_entry :"""
        self.symbol_table.enter_scope()

    # --- IF ---
    def p_if_only(self, p):
        """if_statement : IF LPAREN condition RPAREN block"""
        cond_temp, false_label = p[3]
        self._current_lineno = p.lineno(1)
        self.emit('label', false_label, None, None, lineno=p.lineno(1))
        p[0] = ('if', p[3])

    def p_if_else(self, p):
        """if_statement : IF LPAREN condition RPAREN block else_marker block"""
        end_label = p[6]
        self._current_lineno = p.lineno(1)
        self.emit('label', end_label, None, None, lineno=p.lineno(1))
        p[0] = ('if_else', p[3])

    def p_else_marker(self, p):
        """else_marker : ELSE"""
        end_label   = self.new_label()
        false_label = None
        for instr in reversed(self.intermediate_code):
            if instr['op'] == 'if_false':
                false_label = instr['arg2']
                break
        self._current_lineno = p.lineno(1)
        self.emit('goto', end_label, None, None, lineno=p.lineno(1))
        if false_label:
            self.emit('label', false_label, None, None, lineno=p.lineno(1))
        p[0] = end_label

    # --- WHILE ---
    def p_while_start(self, p):
        """while_start : WHILE"""
        start_label = self.new_label()
        self._current_lineno = p.lineno(1)
        self.emit('label', start_label, None, None, lineno=p.lineno(1))
        p[0] = start_label

    def p_while_statement(self, p):
        """while_statement : while_start LPAREN condition RPAREN block"""
        start_label            = p[1]
        cond_temp, false_label = p[3]
        self.emit('goto', start_label, None, None, lineno=self._current_lineno)
        self.emit('label', false_label, None, None, lineno=self._current_lineno)
        p[0] = ('while', p[3])

    # --- FOR ---
    def p_for_statement(self, p):
        """for_statement : FOR LPAREN for_init SEMICOLON for_condition SEMICOLON for_update RPAREN block"""
        start_label, cond_temp, false_label = p[5]
        self._current_lineno = p.lineno(1)
        self.emit('goto', start_label, None, None, lineno=p.lineno(1))
        self.emit('label', false_label, None, None, lineno=p.lineno(1))
        p[0] = ('for', p[5])

    def p_for_init_decl(self, p):
        """for_init : type ID ASSIGN expression"""
        var_type, var_name, expr = p[1], p[2], p[4]
        self._current_lineno = p.lineno(2)
        if not self.symbol_table.lookup_current_scope(var_name):
            self.symbol_table.insert(var_name, var_type, expr)
        self.emit('=', expr, None, var_name, lineno=p.lineno(2))
        p[0] = ('for_init', var_name)

    def p_for_init_assign(self, p):
        """for_init : ID ASSIGN expression"""
        var_name, expr = p[1], p[3]
        self._current_lineno = p.lineno(1)
        if not self.symbol_table.lookup(var_name):
            self.errors.append(f"Semantic Error: Variable '{var_name}' has not been declared")
        self.emit('=', expr, None, var_name, lineno=p.lineno(1))
        p[0] = ('for_init_assign', var_name)

    def p_for_init_empty(self, p):
        """for_init :"""
        p[0] = None

    def p_for_condition_full(self, p):
        """for_condition : for_start_label expression relop expression"""
        start_label = p[1]
        temp        = self.new_temp()
        self.emit(p[3], p[2], p[4], temp)
        false_label = self.new_label()
        self.emit('if_false', temp, false_label, None)
        p[0] = (start_label, temp, false_label)

    def p_for_start_label(self, p):
        """for_start_label :"""
        start_label = self.new_label()
        self.emit('label', start_label, None, None)
        p[0] = start_label

    def p_for_update_assign(self, p):
        """for_update : ID ASSIGN expression"""
        var_name, expr = p[1], p[3]
        self._current_lineno = p.lineno(1)
        self.emit('=', expr, None, var_name, lineno=p.lineno(1))
        p[0] = ('for_update', var_name)

    def p_for_update_empty(self, p):
        """for_update :"""
        p[0] = None

    # --- FUNCTION ---
    def p_func_header(self, p):
        """func_definition : FUNC type func_name_marker LPAREN param_list RPAREN func_body"""
        func_name, return_type, params = p[3], p[2], p[5]
        if not self.symbol_table.lookup(func_name):
            self.symbol_table.insert(func_name, f"func:{return_type}")
        self.emit('func_end', func_name, None, None, lineno=self._current_lineno)
        self.pending_params = []
        p[0] = ('func_def', func_name, params)

    def p_func_name_marker(self, p):
        """func_name_marker : ID"""
        func_name = p[1]
        self._current_lineno = p.lineno(1)
        self.emit('func_start', func_name, None, None, lineno=p.lineno(1))
        self.pending_params = []
        p[0] = func_name

    def p_func_body(self, p):
        """func_body : LBRACE func_scope_entry statement_list RBRACE"""
        self.symbol_table.exit_scope()
        p[0] = ('func_body', p[3])

    def p_func_body_empty(self, p):
        """func_body : LBRACE func_scope_entry RBRACE"""
        self.symbol_table.exit_scope()
        p[0] = ('func_body', [])

    def p_func_scope_entry(self, p):
        """func_scope_entry :"""
        self.symbol_table.enter_scope()
        # Register pending parameters in the new function scope
        for param_type, param_name in self.pending_params:
            self.symbol_table.insert(param_name, param_type)

    def p_param_list_multiple(self, p):
        """param_list : param_list COMMA param"""
        p[0] = p[1] + [p[3]]
        self.pending_params = p[0]  # Store params for later registration

    def p_param_list_single(self, p):
        """param_list : param"""
        p[0] = [p[1]]
        self.pending_params = p[0]  # Store params for later registration

    def p_param_list_empty(self, p):
        """param_list :"""
        p[0] = []
        self.pending_params = []

    def p_param(self, p):
        """param : type ID"""
        p[0] = (p[1], p[2])

    def p_return_statement(self, p):
        """statement : RETURN expression SEMICOLON"""
        self._current_lineno = p.lineno(1)
        self.emit('return', p[2], None, None, lineno=p.lineno(1))
        p[0] = ('return', p[2])

    def p_return_void(self, p):
        """statement : RETURN SEMICOLON"""
        self._current_lineno = p.lineno(1)
        self.emit('return', None, None, None, lineno=p.lineno(1))
        p[0] = ('return_void',)

    # --- Function Call ---
    def p_func_call_stmt(self, p):
        """func_call_stmt : ID LPAREN arg_list RPAREN SEMICOLON"""
        func_name, args = p[1], p[3]
        self._current_lineno = p.lineno(1)
        for arg in args:
            self.emit('param', arg, None, None, lineno=p.lineno(1))
        temp = self.new_temp()
        self.emit('call', func_name, len(args), temp, lineno=p.lineno(1))
        p[0] = ('func_call_stmt', func_name, args)

    def p_factor_func_call(self, p):
        """factor : ID LPAREN arg_list RPAREN"""
        func_name, args = p[1], p[3]
        self._current_lineno = p.lineno(1)
        for arg in args:
            self.emit('param', arg, None, None, lineno=p.lineno(1))
        temp = self.new_temp()
        self.emit('call', func_name, len(args), temp, lineno=p.lineno(1))
        p[0] = temp

    def p_arg_list_multiple(self, p):
        """arg_list : arg_list COMMA expression"""
        p[0] = p[1] + [p[3]]

    def p_arg_list_single(self, p):
        """arg_list : expression"""
        p[0] = [p[1]]

    def p_arg_list_empty(self, p):
        """arg_list :"""
        p[0] = []

    # --- Condition ---
    def p_condition(self, p):
        """condition : expression relop expression"""
        temp = self.new_temp()
        self.emit(p[2], p[1], p[3], temp, lineno=self._current_lineno)
        false_label = self.new_label()
        self.emit('if_false', temp, false_label, None, lineno=self._current_lineno)
        p[0] = (temp, false_label)

    def p_relop(self, p):
        """relop : LT
                 | LE
                 | GT
                 | GE
                 | EQ
                 | NE"""
        p[0] = p[1]

    # --- Expression ---
    def p_expression_binop(self, p):
        """expression : expression PLUS term
                      | expression MINUS term"""
        temp = self.new_temp()
        self.emit(p[2], p[1], p[3], temp, lineno=self._current_lineno)
        p[0] = temp

    def p_expression_term(self, p):
        """expression : term"""
        p[0] = p[1]

    def p_term_binop(self, p):
        """term : term TIMES factor
               | term DIVIDE factor
               | term MODULO factor"""
        temp = self.new_temp()
        self.emit(p[2], p[1], p[3], temp, lineno=self._current_lineno)
        p[0] = temp

    def p_term_factor(self, p):
        """term : factor"""
        p[0] = p[1]

    def p_factor_number(self, p):
        """factor : NUMBER
                 | FLOAT_NUM"""
        p[0] = p[1]

    def p_factor_id(self, p):
        """factor : ID"""
        if not self.symbol_table.lookup(p[1]):
            self.errors.append(f"Semantic Error: Variable '{p[1]}' has not been declared")
        p[0] = p[1]

    def p_factor_paren(self, p):
        """factor : LPAREN expression RPAREN"""
        p[0] = p[2]

    def p_error(self, p):
        if p:
            self.errors.append(f"Syntax Error: Unexpected token '{p.value}' at Line {p.lineno}")
        else:
            self.errors.append("Syntax Error: Unexpected end of file")

    # --- Build & Parse ---
    def build(self):
        self.parser = yacc.yacc(module=self, debug=False, write_tables=False)

    def parse(self, code):
        lexer_obj = build_lexer()
        self.parser.parse(code, lexer=lexer_obj)