"""
=============================================================================
CSE 430 - Compiler Design Lab Project
PHASE 5: INTEL 8086 ASSEMBLY CODE GENERATOR
=============================================================================
Job: Converts Intermediate Code (3AC) into Intel 8086 Assembly
8086 is an older but ideal processor for learning
Registers: AX, BX, CX, DX (16-bit)
=============================================================================
"""


class Intel8086CodeGenerator:
    def generate(self, intermediate_code):
        asm = []

        # Program header
        asm.append("; ============================================================")
        asm.append("; Intel 8086 Assembly Code")
        asm.append("; CSE 430 Mini Compiler - Generated Output")
        asm.append("; ============================================================")
        asm.append("")
        asm.append(".MODEL SMALL          ; Small memory model")
        asm.append(".STACK 100H           ; 256 bytes for the stack")
        asm.append("")
        asm.append(".DATA                 ; Data segment")
        asm.append("    PRINT_BUF DB 10 DUP('$')  ; Buffer for print output")
        asm.append("")
        asm.append(".CODE                 ; Code segment")
        asm.append("MAIN PROC")
        asm.append("    MOV AX, @DATA    ; Initialize data segment")
        asm.append("    MOV DS, AX       ; Store data segment address in DS")
        asm.append("")

        for i, instr in enumerate(intermediate_code):
            op, arg1, arg2, result = (
                instr['op'], instr['arg1'], instr['arg2'], instr['result']
            )

            if op == '=':
                asm.append(f"    ; {result} = {arg1}")
                asm.append(f"    MOV AX, {arg1}   ; Load arg1 into AX")
                asm.append(f"    MOV {result}, AX  ; Copy AX into result")

            elif op == '+':
                asm.append(f"    ; {result} = {arg1} + {arg2}")
                asm.append(f"    MOV AX, {arg1}")
                asm.append(f"    ADD AX, {arg2}   ; Add")
                asm.append(f"    MOV {result}, AX")

            elif op == '-':
                asm.append(f"    ; {result} = {arg1} - {arg2}")
                asm.append(f"    MOV AX, {arg1}")
                asm.append(f"    SUB AX, {arg2}   ; Subtract")
                asm.append(f"    MOV {result}, AX")

            elif op == '*':
                asm.append(f"    ; {result} = {arg1} * {arg2}")
                asm.append(f"    MOV AX, {arg1}")
                asm.append(f"    MOV BX, {arg2}")
                asm.append(f"    MUL BX            ; Multiply (AX * BX -> AX)")
                asm.append(f"    MOV {result}, AX")

            elif op == '/':
                asm.append(f"    ; {result} = {arg1} / {arg2}")
                asm.append(f"    MOV AX, {arg1}")
                asm.append(f"    MOV BX, {arg2}")
                asm.append(f"    XOR DX, DX        ; Clear DX before division")
                asm.append(f"    DIV BX            ; Divide (AX / BX -> AX)")
                asm.append(f"    MOV {result}, AX")

            elif op == '%':
                asm.append(f"    ; {result} = {arg1} % {arg2} (remainder)")
                asm.append(f"    MOV AX, {arg1}")
                asm.append(f"    MOV BX, {arg2}")
                asm.append(f"    XOR DX, DX")
                asm.append(f"    DIV BX            ; Remainder in DX")
                asm.append(f"    MOV {result}, DX")

            elif op in ['<', '<=', '>', '>=', '==', '!=']:
                asm.append(f"    ; Compare: {arg1} {op} {arg2}")
                asm.append(f"    MOV AX, {arg1}")
                asm.append(f"    CMP AX, {arg2}   ; Compare (sets flags)")

            elif op == 'if_false':
                prev_op  = intermediate_code[i - 1]['op'] if i > 0 else '=='
                jump_map = {
                    '<':  'JGE',
                    '<=': 'JG',
                    '>':  'JLE',
                    '>=': 'JL',
                    '==': 'JNE',
                    '!=': 'JE',
                }
                jmp = jump_map.get(prev_op, 'JNE')
                asm.append(f"    {jmp} {arg2}    ; condition false -> jump to {arg2}")

            elif op == 'label':
                asm.append(f"\n{arg1}:             ; Jump destination")

            elif op == 'goto':
                asm.append(f"    JMP {arg1}       ; Unconditional jump")

            elif op == 'print':
                asm.append(f"    ; print({arg1})")
                asm.append(f"    MOV AX, {arg1}   ; Load value into AX")
                asm.append(f"    CALL OUTDEC      ; Call output subroutine")

            elif op == 'func_start':
                asm.append(f"\n; --- Function: {arg1} ---")
                asm.append(f"{arg1} PROC           ; Begin function")
                asm.append(f"    PUSH BP          ; Save base pointer")
                asm.append(f"    MOV BP, SP       ; Set up stack frame")

            elif op == 'func_end':
                asm.append(f"    POP BP           ; Restore base pointer")
                asm.append(f"    RET              ; Return to caller")
                asm.append(f"{arg1} ENDP           ; End of function")

            elif op == 'param':
                asm.append(f"    MOV AX, {arg1}   ; Prepare argument")
                asm.append(f"    PUSH AX          ; Push onto stack")

            elif op == 'call':
                asm.append(f"    CALL {arg1}      ; Call function {arg1}")
                if arg2:
                    asm.append(f"    ADD SP, {int(arg2)*2}  ; Stack cleanup ({arg2} args)")
                asm.append(f"    MOV {result}, AX ; Save return value")

            elif op == 'return':
                if arg1 is not None:
                    asm.append(f"    MOV AX, {arg1}   ; Load return value into AX")
                asm.append(f"    POP BP")
                asm.append(f"    RET")

        # Program footer
        asm.append("")
        asm.append("    MOV AH, 4CH      ; DOS exit code")
        asm.append("    INT 21H          ; Notify OS: program ended")
        asm.append("MAIN ENDP")
        asm.append("")
        asm.append("; --- OUTDEC: Print number subroutine ---")
        asm.append("OUTDEC PROC")
        asm.append("    ; Displays the value in AX on screen")
        asm.append("    RET")
        asm.append("OUTDEC ENDP")
        asm.append("")
        asm.append("END MAIN")

        return asm
