"""
=============================================================================
CSE 430 - Compiler Design Lab Project
PHASE 2: SYMBOL TABLE
=============================================================================
Job: Stores information about all declared variables
e.g. name, type (int/float), which scope it belongs to
Scope: global (visible everywhere) or local (only inside {})
=============================================================================
"""


class SymbolTable:
    def __init__(self):
        self.symbols       = {}             # all variable info stored here
        self.scope_stack   = ['global']     # starts with global scope
        self.scope_counter = 0              # counter for new scopes

    def enter_scope(self):
        """Create a new scope when a new block {} begins"""
        self.scope_counter += 1
        new_scope = f"scope_{self.scope_counter}"
        self.scope_stack.append(new_scope)
        return new_scope

    def exit_scope(self):
        """Exit the scope when a block {} ends"""
        if len(self.scope_stack) > 1:
            return self.scope_stack.pop()
        return None

    def current_scope(self):
        """Return the current active scope"""
        return self.scope_stack[-1]

    def insert(self, name, symbol_type, value=None):
        """Insert a new variable into the symbol table"""
        scope = self.current_scope()
        key   = f"{scope}:{name}"
        if key in self.symbols:
            return False  # already exists in this scope
        self.symbols[key] = {
            'name':  name,
            'type':  symbol_type,
            'value': value,
            'scope': scope,
        }
        return True

    def lookup(self, name):
        """Look up a variable - searches from inner scope to outer (scope chain)"""
        for scope in reversed(self.scope_stack):
            key = f"{scope}:{name}"
            if key in self.symbols:
                return self.symbols[key]
        return None

    def lookup_current_scope(self, name):
        """Check if a variable exists only in the current scope"""
        scope = self.current_scope()
        return self.symbols.get(f"{scope}:{name}")

    def get_all(self):
        """Return a list of all variables in the table"""
        return list(self.symbols.values())
