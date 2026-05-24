"""
=============================================================================
CSE 430 - Compiler Design Lab Project
PHASE 1: LEXICAL ANALYZER
=============================================================================
Job: Reads source code and breaks it into small tokens
Example: "int x = 5;" -> [INT, ID(x), ASSIGN, NUMBER(5), SEMICOLON]
=============================================================================
"""

import ply.lex as lex

# Global error list - collects errors from the Lexer
errors_list = []


class Lexer:
    # Reserved words - these cannot be used as variable names
    reserved = {
        'if':     'IF',
        'else':   'ELSE',
        'while':  'WHILE',
        'for':    'FOR',
        'int':    'INT',
        'float':  'FLOAT',
        'return': 'RETURN',
        'print':  'PRINT',
        'void':   'VOID',
        'func':   'FUNC',
    }

    # List of all token names
    tokens = [
        'ID',
        'NUMBER',
        'FLOAT_NUM',
        'PLUS',
        'MINUS',
        'TIMES',
        'DIVIDE',
        'MODULO',
        'ASSIGN',
        'EQ',
        'NE',
        'LT',
        'LE',
        'GT',
        'GE',
        'LPAREN',
        'RPAREN',
        'LBRACE',
        'RBRACE',
        'SEMICOLON',
        'COMMA',
    ] + list(reserved.values())

    # Simple token rules
    t_PLUS      = r'\+'
    t_MINUS     = r'-'
    t_TIMES     = r'\*'
    t_MODULO    = r'%'
    t_ASSIGN    = r'='
    t_EQ        = r'=='
    t_NE        = r'!='
    t_LT        = r'<'
    t_LE        = r'<='
    t_GT        = r'>'
    t_GE        = r'>='
    t_LPAREN    = r'\('
    t_RPAREN    = r'\)'
    t_LBRACE    = r'\{'
    t_RBRACE    = r'\}'
    t_SEMICOLON = r';'
    t_COMMA     = r','

    # Ignore spaces and tabs
    t_ignore = ' \t'

    def t_COMMENT_MULTI(self, t):
        r'/\*(.|\n)*?\*/'
        t.lexer.lineno += t.value.count('\n')
        pass

    def t_COMMENT_SINGLE(self, t):
        r'//.*'
        pass

    def t_DIVIDE(self, t):
        r'/'
        return t

    def t_FLOAT_NUM(self, t):
        r'\d+\.\d+'
        t.value = float(t.value)
        return t

    def t_NUMBER(self, t):
        r'\d+'
        t.value = int(t.value)
        return t

    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z_0-9]*'
        t.type = self.reserved.get(t.value, 'ID')
        return t

    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    def t_error(self, t):
        errors_list.append(
            f"Lexical Error: Unrecognized character '{t.value[0]}' (Line {t.lineno})"
        )
        t.lexer.skip(1)


def build_lexer():
    """Build and return the PLY lexer object"""
    return lex.lex(module=Lexer())
