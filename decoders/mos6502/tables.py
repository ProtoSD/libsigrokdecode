##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2017 David Banks <dave@hoglet.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##


# Emulation TODO list
# - Seperate 6502/65C02 modes
# - Decimal mode
# - Overflow flag in ADC/SBC
# - Reduce uncertainty where possible (e.g. where just one of A and C is undefined)

'''
  6502 Addressing Modes

  Map of Addressing Mode to Instruction Length

  Instruction tuple: (string, addressing mode)
'''

# Instructions without a prefix

class AddrMode:
    IMP, IMPA, BRA, IMM, ZP, ZPX, ZPY, INDX, INDY, IND, ABS, ABSX, ABSY, IND16, IND1X, ZPR = range(16)

addr_mode_len_map = {
    AddrMode.IMP:   ( 1, '{0}'                     ),
    AddrMode.IMPA:  ( 1, '{0} A'                   ),
    AddrMode.BRA:   ( 2, '{0} {3}'                 ),
    AddrMode.IMM:   ( 2, '{0} #{1:02X}'            ),
    AddrMode.ZP:    ( 2, '{0} {1:02X}'             ),
    AddrMode.ZPX:   ( 2, '{0} {1:02X},X'           ),
    AddrMode.ZPY:   ( 2, '{0} {1:02X},Y'           ),
    AddrMode.INDX:  ( 2, '{0} ({1:02X},X)'         ),
    AddrMode.INDY:  ( 2, '{0} ({1:02X}),Y'         ),
    AddrMode.IND:   ( 2, '{0} ({1:02X})'           ),
    AddrMode.ABS:   ( 3, '{0} {2:02X}{1:02X}'      ),
    AddrMode.ABSX:  ( 3, '{0} {2:02X}{1:02X},X'    ),
    AddrMode.ABSY:  ( 3, '{0} {2:02X}{1:02X},Y'    ),
    AddrMode.IND16: ( 3, '{0} ({2:02X}{1:02X})'    ),
    AddrMode.IND1X: ( 3, '{0} ({2:02X}{1:02X},X)'  ),
    AddrMode.ZPR:   ( 3, '{0} {1:02X},{3}'         ),
}

class Emulator:
    # 6502 registers: -1 means unknown
    A = -1
    X = -1
    Y = -1
    S = -1
    # 6502 flags: -1 means unknown
    N = -1
    V = -1
    D = -1
    I = -1
    Z = -1
    C = -1
    # indicate state prediction failed
    failflag = 0

    def get_state(self):
        As = '??' if self.A < 0 else format(self.A, '02X')
        Xs = '??' if self.X < 0 else format(self.X, '02X')
        Ys = '??' if self.Y < 0 else format(self.Y, '02X')
        Ss = '??' if self.S < 0 else format(self.S, '02X')
        Ns = '?'  if self.N < 0 else format(self.N, '01X')
        Vs = '?'  if self.V < 0 else format(self.V, '01X')
        Ds = '?'  if self.D < 0 else format(self.D, '01X')
        Is = '?'  if self.I < 0 else format(self.I, '01X')
        Zs = '?'  if self.Z < 0 else format(self.Z, '01X')
        Cs = '?'  if self.C < 0 else format(self.C, '01X')
        ff = ' prediction failed' if self.failflag else ''
        self.failflag = 0
        return 'A=' + As + ' X=' + Xs + ' Y=' + Ys + ' SP=' + Ss + ' N=' + Ns + ' V=' + Vs + ' D=' + Ds + ' I=' + Is + ' Z=' + Zs + ' C=' + Cs + ff

    def set_NZ_unknown(self):
        self.N = -1
        self.Z = -1

    def set_NZC_unknown(self):
        self.N = -1
        self.Z = -1
        self.C = -1

    def interrupt(self, operand):
        if self.S >= 0:
            self.S = (self.S - 3) & 255
        self.check_NVDIZC(operand)
        self.set_NVDIZC(operand)
        self.I = 1
        self.D = 0 # TODO: 65C02 only

    def set_NZ(self, value):
        self.N = int(value & 128 > 0)
        self.Z = int(value == 0)

    def check_NVDIZC(self, operand):
        if self.N >= 0:
            if self.N != (operand >> 7) & 1:
                failflag = 1
        if self.V >= 0:
            if self.V != (operand >> 6) & 1:
                failflag = 1
        if self.D >= 0:
            if self.D != (operand >> 3) & 1:
                failflag = 1
        if self.I >= 0:
            if self.I != (operand >> 2) & 1:
                failflag = 1
        if self.Z >= 0:
            if self.Z != (operand >> 1) & 1:
                failflag = 1
        if self.C >= 0:
            if self.C != (operand >> 0) & 1:
                failflag = 1

    def set_NVDIZC(self, operand):
        self.N = (operand >> 7) & 1
        self.V = (operand >> 6) & 1
        self.D = (operand >> 3) & 1
        self.I = (operand >> 2) & 1
        self.Z = (operand >> 1) & 1
        self.C = (operand >> 0) & 1

    def op_ADC(self, operand):
        # TODO: Decimal mode
        # TODO: Overflow flag
        if self.A >= 0 and self.C >= 0:
            tmp = self.A + operand + self.C
            self.C = (tmp >> 8) & 1
            self.A = tmp & 255
            self.set_NZ(self.A)
        else:
            self.A = -1
            self.set_NZC_unknown()

    def op_AND(self, operand):
        if self.A >= 0:
            self.A = self.A & operand
            self.set_NZ(self.A)
        else:
            self.set_NZ_unknown()

    def op_ASLA(self, operand):
        if self.A >= 0:
            self.C = (self.A >> 7) & 1
            self.A = (self.A << 1) & 255
            self.set_NZ(self.A)
        else:
            self.set_NZC_unknown()

    def op_ASL(self, operand):
        self.C = (operand >> 7) & 1
        tmp = (operand << 1) & 255
        self.set_NZ(tmp)

    def op_BRK(self, operand):
        self.interrupt(operand)

    def op_BIT_IMM(self, operand):
        if self.A >= 0:
            self.Z = int(self.A & operand == 0)
        else:
            self.Z = -1

    def op_BIT(self, operand):
        self.N = (operand >> 7) & 1
        self.V = (operand >> 6) & 1
        if self.A >= 0:
            self.Z = int(self.A & operand == 0)
        else:
            self.Z = -1

    def op_CLC(self, operand):
        self.C = 0

    def op_CLD(self, operand):
        self.D = 0

    def op_CLI(self, operand):
        self.I = 0

    def op_CLV(self, operand):
        self.V = 0

    def op_CMP(self, operand):
        if self.A >= 0:
            tmp = self.A - operand
            self.C = int(tmp >= 0)
            self.set_NZ(tmp)

    def op_CPX(self, operand):
        if self.X >= 0:
            tmp = self.X - operand
            self.C = int(tmp >= 0)
            self.set_NZ(tmp)

    def op_CPY(self, operand):
        if self.Y >= 0:
            tmp = self.Y - operand
            self.C = int(tmp >= 0)
            self.set_NZ(tmp)

    def op_DECA(self, operand):
        if self.A >= 0:
            self.A = (self.A - 1) & 255
            self.set_NZ(self.A)
        else:
            self.set_NZ_unknown()

    def op_DEC(self, operand):
        tmp = (operand - 1) & 255
        self.set_NZ(tmp)

    def op_DEX(self, operand):
        if self.X >= 0:
            self.X = (self.X - 1) & 255
            self.set_NZ(self.X)
        else:
            self.set_NZ_unknown()

    def op_DEY(self, operand):
        if self.Y >= 0:
            self.Y = (self.Y - 1) & 255
            self.set_NZ(self.Y)
        else:
            self.set_NZ_unknown()

    def op_EOR(self, operand):
        if self.A >= 0:
            self.A = self.A ^ operand
            self.set_NZ(self.A)
        else:
            self.set_NZ_unknown()

    def op_INCA(self, operand):
        if self.A >= 0:
            self.A = (self.A + 1) & 255
            self.set_NZ(self.A)
        else:
            self.set_NZ_unknown()

    def op_INC(self, operand):
        tmp = (operand + 1) & 255
        self.set_NZ(tmp)

    def op_INX(self, operand):
        if self.X >= 0:
            self.X = (self.X + 1) & 255
            self.set_NZ(self.X)
        else:
            self.set_NZ_unknown()

    def op_INY(self, operand):
        if self.Y >= 0:
            self.Y = (self.Y + 1) & 255
            self.set_NZ(self.Y)
        else:
            self.set_NZ_unknown()

    def op_JSR(self, operand):
        if self.S >= 0:
            self.S = (self.S - 2) & 255

    def op_LDA(self, operand):
        self.A = operand
        self.set_NZ(self.A)

    def op_LDX(self, operand):
        self.X = operand
        self.set_NZ(self.X)

    def op_LDY(self, operand):
        self.Y = operand
        self.set_NZ(self.Y)

    def op_LSRA(self, operand):
        if self.A >= 0:
            self.C = self.A & 1
            self.A = self.A >> 1
            self.set_NZ(self.A)
        else:
            self.set_NZC_unknown()

    def op_LSR(self, operand):
        self.C = operand & 1
        tmp = operand >> 1
        self.set_NZ(tmp)

    def op_ORA(self, operand):
        if self.A >= 0:
            self.A = self.A | operand
            self.set_NZ(self.A)
        else:
            self.set_NZ_unknown()

    def op_PHA(self, operand):
        if self.S >= 0:
            self.S = (self.S - 1) & 255
        self.op_STA(operand)

    def op_PHP(self, operand):
        if self.S >= 0:
            self.S = (self.S - 1) & 255
        self.check_NVDIZC(operand)
        self.set_NVDIZC(operand)

    def op_PHX(self, operand):
        if self.S >= 0:
            self.S = (self.S - 1) & 255
        self.op_STX(operand)

    def op_PHY(self, operand):
        if self.S >= 0:
            self.S = (self.S - 1) & 255
        self.op_STY(operand)

    def op_PLA(self, operand):
        self.A = operand
        self.set_NZ(self.A)
        if self.S >= 0:
            self.S = (self.S + 1) & 255

    def op_PLP(self, operand):
        self.set_NVDIZC(operand)
        if self.S >= 0:
            self.S = (self.S + 1) & 255

    def op_PLX(self, operand):
        self.X = operand
        self.set_NZ(self.X)
        if self.S >= 0:
            self.S = (self.S + 1) & 255

    def op_PLY(self, operand):
        self.Y = operand
        self.set_NZ(self.Y)
        if self.S >= 0:
            self.S = (self.S + 1) & 255

    def op_ROLA(self, operand):
        if self.A >= 0 and self.C >= 0:
            tmp = (self.A << 1) + self.C
            self.C = (tmp >> 8) & 1
            self.A = tmp & 255
            self.set_NZ(self.A)
        else:
            self.A = -1
            self.set_NZC_unknown()

    def op_ROL(self, operand):
        if self.C >= 0:
            tmp = (operand << 1) + self.C
            self.C = (tmp >> 8) & 1
            tmp = tmp & 255
            self.set_NZ(tmp)
        else:
            self.set_NZC_unknown()

    def op_RORA(self, operand):
        if self.A >= 0 and self.C >= 0:
            tmp = (self.A >> 1) + (self.C << 7)
            self.C = self.A & 1
            self.A = tmp
            self.set_NZ(self.A)
        else:
            self.A = -1
            self.set_NZC_unknown()

    def op_ROR(self, operand):
        if self.C >= 0:
            tmp = (operand >> 1) + (self.C << 7)
            self.C = operand & 1
            self.set_NZ(tmp)
        else:
            self.set_NZC_unknown()

    def op_RTS(self, operand):
        if self.S >= 0:
            self.S = (self.S + 2) & 255

    def op_RTI(self, operand):
        self.set_NVDIZC(operand)
        if self.S >= 0:
            self.S = (self.S + 3) & 255

    def op_SBC(self, operand):
        # TODO: Decimal mode
        # TODO: Overflow flag
        if self.A >= 0 and self.C >= 0:
            tmp = self.A - operand - (1 - self.C)
            self.C = 1 - ((tmp >> 8) & 1)
            self.A = tmp & 255
            self.set_NZ(self.A)
        else:
            self.A = -1
            self.set_NZC_unknown()

    def op_SEC(self, operand):
        self.C = 1

    def op_SED(self, operand):
        self.D = 1

    def op_SEI(self, operand):
        self.I = 1

    def op_STA(self, operand):
        if self.A >= 0:
            if operand != self.A:
                self.failflag = 1
        self.A = operand

    def op_STX(self, operand):
        if self.X >= 0:
            if operand != self.X:
                self.failflag = 1
        self.X = operand

    def op_STY(self, operand):
        if self.Y >= 0:
            if operand != self.Y:
                self.failflag = 1
        self.Y = operand

    def op_TAX(self, operand):
        if self.A >= 0:
            self.X = self.A
            self.set_NZ(self.X)
        else:
            self.set_NZ_unknown()

    def op_TAY(self, operand):
        if self.A >= 0:
            self.Y = self.A
            self.set_NZ(self.Y)
        else:
            self.set_NZ_unknown()

    def op_TSB_TRB(self, operand):
        if self.A >= 0:
            self.Z = int(self.A & operand == 0)
        else:
            self.Z = -1

    def op_TSX(self, operand):
        if self.S >= 0:
            self.X = self.S
            self.set_NZ(self.X)
        else:
            self.set_NZ_unknown()

    def op_TXA(self, operand):
        if self.X >= 0:
            self.A = self.X
            self.set_NZ(self.A)
        else:
            self.set_NZ_unknown()


    def op_TXS(self, operand):
        if self.X >= 0:
            self.S = self.X

    def op_TYA(self, operand):
        if self.Y >= 0:
            self.A = self.Y
        else:
            self.set_NZ_unknown()

em = Emulator()

instr_table = {
    0x00: ( 'BRK',  AddrMode.IMM   , 1, em.op_BRK),
    0x01: ( 'ORA',  AddrMode.INDX  , 0, em.op_ORA),
    0x02: ( 'NOP',  AddrMode.IMM   , 0, 0),
    0x03: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x04: ( 'TSB',  AddrMode.ZP    , 0, em.op_TSB_TRB),
    0x05: ( 'ORA',  AddrMode.ZP    , 0, em.op_ORA),
    0x06: ( 'ASL',  AddrMode.ZP    , 0, em.op_ASL),
    0x07: ( 'RMB0', AddrMode.ZP    , 0, 0),
    0x08: ( 'PHP',  AddrMode.IMP   , 1, em.op_PHP),
    0x09: ( 'ORA',  AddrMode.IMM   , 0, em.op_ORA),
    0x0A: ( 'ASL',  AddrMode.IMPA  , 0, em.op_ASLA),
    0x0B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x0C: ( 'TSB',  AddrMode.ABS   , 0, em.op_TSB_TRB),
    0x0D: ( 'ORA',  AddrMode.ABS   , 0, em.op_ORA),
    0x0E: ( 'ASL',  AddrMode.ABS   , 0, em.op_ASL),
    0x0F: ( 'BBR0', AddrMode.ZPR   , 0, 0),
    0x10: ( 'BPL',  AddrMode.BRA   , 0, 0),
    0x11: ( 'ORA',  AddrMode.INDY  , 0, em.op_ORA),
    0x12: ( 'ORA',  AddrMode.IND   , 0, em.op_ORA),
    0x13: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x14: ( 'TRB',  AddrMode.ZP    , 0, em.op_TSB_TRB),
    0x15: ( 'ORA',  AddrMode.ZPX   , 0, em.op_ORA),
    0x16: ( 'ASL',  AddrMode.ZPX   , 0, em.op_ASL),
    0x17: ( 'RMB1', AddrMode.ZP    , 0, 0),
    0x18: ( 'CLC',  AddrMode.IMP   , 0, em.op_CLC),
    0x19: ( 'ORA',  AddrMode.ABSY  , 0, em.op_ORA),
    0x1A: ( 'INC',  AddrMode.IMPA  , 0, em.op_INCA),
    0x1B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x1C: ( 'TRB',  AddrMode.ABS   , 0, em.op_TSB_TRB),
    0x1D: ( 'ORA',  AddrMode.ABSX  , 0, em.op_ORA),
    0x1E: ( 'ASL',  AddrMode.ABSX  , 0, em.op_ASL),
    0x1F: ( 'BBR1', AddrMode.ZPR   , 0, 0),
    0x20: ( 'JSR',  AddrMode.ABS   , 0, em.op_JSR),
    0x21: ( 'AND',  AddrMode.INDX  , 0, em.op_AND),
    0x22: ( 'NOP',  AddrMode.IMM   , 0, 0),
    0x23: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x24: ( 'BIT',  AddrMode.ZP    , 0, em.op_BIT),
    0x25: ( 'AND',  AddrMode.ZP    , 0, em.op_AND),
    0x26: ( 'ROL',  AddrMode.ZP    , 0, em.op_ROL),
    0x27: ( 'RMB2', AddrMode.ZP    , 0, 0),
    0x28: ( 'PLP',  AddrMode.IMP   , 0, em.op_PLP),
    0x29: ( 'AND',  AddrMode.IMM   , 0, em.op_AND),
    0x2A: ( 'ROL',  AddrMode.IMPA  , 0, em.op_ROLA),
    0x2B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x2C: ( 'BIT',  AddrMode.ABS   , 0, em.op_BIT),
    0x2D: ( 'AND',  AddrMode.ABS   , 0, em.op_AND),
    0x2E: ( 'ROL',  AddrMode.ABS   , 0, em.op_ROL),
    0x2F: ( 'BBR2', AddrMode.ZPR   , 0, 0),
    0x30: ( 'BMI',  AddrMode.BRA   , 0, 0),
    0x31: ( 'AND',  AddrMode.INDY  , 0, em.op_AND),
    0x32: ( 'AND',  AddrMode.IND   , 0, em.op_AND),
    0x33: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x34: ( 'BIT',  AddrMode.ZPX   , 0, em.op_BIT),
    0x35: ( 'AND',  AddrMode.ZPX   , 0, em.op_AND),
    0x36: ( 'ROL',  AddrMode.ZPX   , 0, em.op_ROL),
    0x37: ( 'RMB3', AddrMode.ZP    , 0, 0),
    0x38: ( 'SEC',  AddrMode.IMP   , 0, em.op_SEC),
    0x39: ( 'AND',  AddrMode.ABSY  , 0, em.op_AND),
    0x3A: ( 'DEC',  AddrMode.IMPA  , 0, em.op_DECA),
    0x3B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x3C: ( 'BIT',  AddrMode.ABSX  , 0, em.op_BIT),
    0x3D: ( 'AND',  AddrMode.ABSX  , 0, em.op_AND),
    0x3E: ( 'ROL',  AddrMode.ABSX  , 0, em.op_ROL),
    0x3F: ( 'BBR3', AddrMode.ZPR   , 0, 0),
    0x40: ( 'RTI',  AddrMode.IMP   , 0, em.op_RTI),
    0x41: ( 'EOR',  AddrMode.INDX  , 0, em.op_EOR),
    0x42: ( 'NOP',  AddrMode.IMM   , 0, 0),
    0x43: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x44: ( 'NOP',  AddrMode.ZP    , 0, 0),
    0x45: ( 'EOR',  AddrMode.ZP    , 0, em.op_EOR),
    0x46: ( 'LSR',  AddrMode.ZP    , 0, em.op_LSR),
    0x47: ( 'RMB4', AddrMode.ZP    , 0, 0),
    0x48: ( 'PHA',  AddrMode.IMP   , 1, em.op_PHA),
    0x49: ( 'EOR',  AddrMode.IMM   , 0, em.op_EOR),
    0x4A: ( 'LSR',  AddrMode.IMPA  , 0, em.op_LSRA),
    0x4B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x4C: ( 'JMP',  AddrMode.ABS   , 0, 0),
    0x4D: ( 'EOR',  AddrMode.ABS   , 0, em.op_EOR),
    0x4E: ( 'LSR',  AddrMode.ABS   , 0, em.op_LSR),
    0x4F: ( 'BBR4', AddrMode.ZPR   , 0, 0),
    0x50: ( 'BVC',  AddrMode.BRA   , 0, 0),
    0x51: ( 'EOR',  AddrMode.INDY  , 0, em.op_EOR),
    0x52: ( 'EOR',  AddrMode.IND   , 0, em.op_EOR),
    0x53: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x54: ( 'NOP',  AddrMode.ZPX   , 0, 0),
    0x55: ( 'EOR',  AddrMode.ZPX   , 0, em.op_EOR),
    0x56: ( 'LSR',  AddrMode.ZPX   , 0, em.op_LSR),
    0x57: ( 'RMB5', AddrMode.ZP    , 0, 0),
    0x58: ( 'CLI',  AddrMode.IMP   , 0, em.op_CLI),
    0x59: ( 'EOR',  AddrMode.ABSY  , 0, em.op_EOR),
    0x5A: ( 'PHY',  AddrMode.IMP   , 1, em.op_PHY),
    0x5B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x5C: ( 'NOP',  AddrMode.ABS   , 0, 0),
    0x5D: ( 'EOR',  AddrMode.ABSX  , 0, em.op_EOR),
    0x5E: ( 'LSR',  AddrMode.ABSX  , 0, em.op_LSR),
    0x5F: ( 'BBR5', AddrMode.ZPR   , 0, 0),
    0x60: ( 'RTS',  AddrMode.IMP   , 0, em.op_RTS),
    0x61: ( 'ADC',  AddrMode.INDX  , 0, em.op_ADC),
    0x62: ( 'NOP',  AddrMode.IMM   , 0, 0),
    0x63: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x64: ( 'STZ',  AddrMode.ZP    , 1, 0),
    0x65: ( 'ADC',  AddrMode.ZP    , 0, em.op_ADC),
    0x66: ( 'ROR',  AddrMode.ZP    , 0, em.op_ROR),
    0x67: ( 'RMB6', AddrMode.ZP    , 0, 0),
    0x68: ( 'PLA',  AddrMode.IMP   , 0, em.op_PLA),
    0x69: ( 'ADC',  AddrMode.IMM   , 0, em.op_ADC),
    0x6A: ( 'ROR',  AddrMode.IMPA  , 0, em.op_RORA),
    0x6B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x6C: ( 'JMP',  AddrMode.IND16 , 0, 0),
    0x6D: ( 'ADC',  AddrMode.ABS   , 0, em.op_ADC),
    0x6E: ( 'ROR',  AddrMode.ABS   , 0, em.op_ROR),
    0x6F: ( 'BBR6', AddrMode.ZPR   , 0, 0),
    0x70: ( 'BVS',  AddrMode.BRA   , 0, 0),
    0x71: ( 'ADC',  AddrMode.INDY  , 0, em.op_ADC),
    0x72: ( 'ADC',  AddrMode.IND   , 0, em.op_ADC),
    0x73: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x74: ( 'STZ',  AddrMode.ZPX   , 1, 0),
    0x75: ( 'ADC',  AddrMode.ZPX   , 0, em.op_ADC),
    0x76: ( 'ROR',  AddrMode.ZPX   , 0, em.op_ROR),
    0x77: ( 'RMB7', AddrMode.ZP    , 0, 0),
    0x78: ( 'SEI',  AddrMode.IMP   , 0, em.op_SEI),
    0x79: ( 'ADC',  AddrMode.ABSY  , 0, em.op_ADC),
    0x7A: ( 'PLY',  AddrMode.IMP   , 0, em.op_PLY),
    0x7B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x7C: ( 'JMP',  AddrMode.IND1X , 0, 0),
    0x7D: ( 'ADC',  AddrMode.ABSX  , 0, em.op_ADC),
    0x7E: ( 'ROR',  AddrMode.ABSX  , 0, em.op_ROR),
    0x7F: ( 'BBR7', AddrMode.ZPR   , 0, 0),
    0x80: ( 'BRA',  AddrMode.BRA   , 0, 0),
    0x81: ( 'STA',  AddrMode.INDX  , 1, em.op_STA),
    0x82: ( 'NOP',  AddrMode.IMM   , 0, 0),
    0x83: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x84: ( 'STY',  AddrMode.ZP    , 1, em.op_STY),
    0x85: ( 'STA',  AddrMode.ZP    , 1, em.op_STA),
    0x86: ( 'STX',  AddrMode.ZP    , 1, em.op_STX),
    0x87: ( 'SMB0', AddrMode.ZP    , 0, 0),
    0x88: ( 'DEY',  AddrMode.IMP   , 0, em.op_DEY),
    0x89: ( 'BIT',  AddrMode.IMM   , 0, em.op_BIT_IMM),
    0x8A: ( 'TXA',  AddrMode.IMP   , 0, em.op_TXA),
    0x8B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x8C: ( 'STY',  AddrMode.ABS   , 1, em.op_STY),
    0x8D: ( 'STA',  AddrMode.ABS   , 1, em.op_STA),
    0x8E: ( 'STX',  AddrMode.ABS   , 1, em.op_STX),
    0x8F: ( 'BBS0', AddrMode.ZPR   , 0, 0),
    0x90: ( 'BCC',  AddrMode.BRA   , 0, 0),
    0x91: ( 'STA',  AddrMode.INDY  , 1, em.op_STA),
    0x92: ( 'STA',  AddrMode.IND   , 1, em.op_STA),
    0x93: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x94: ( 'STY',  AddrMode.ZPX   , 1, em.op_STY),
    0x95: ( 'STA',  AddrMode.ZPX   , 1, em.op_STA),
    0x96: ( 'STX',  AddrMode.ZPY   , 1, em.op_STX),
    0x97: ( 'SMB1', AddrMode.ZP    , 0, 0),
    0x98: ( 'TYA',  AddrMode.IMP   , 0, em.op_TYA),
    0x99: ( 'STA',  AddrMode.ABSY  , 1, em.op_STA),
    0x9A: ( 'TXS',  AddrMode.IMP   , 0, em.op_TXS),
    0x9B: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0x9C: ( 'STZ',  AddrMode.ABS   , 1, 0),
    0x9D: ( 'STA',  AddrMode.ABSX  , 1, em.op_STA),
    0x9E: ( 'STZ',  AddrMode.ABSX  , 1, 0),
    0x9F: ( 'BBS1', AddrMode.ZPR   , 0, 0),
    0xA0: ( 'LDY',  AddrMode.IMM   , 0, em.op_LDY),
    0xA1: ( 'LDA',  AddrMode.INDX  , 0, em.op_LDA),
    0xA2: ( 'LDX',  AddrMode.IMM   , 0, em.op_LDX),
    0xA3: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xA4: ( 'LDY',  AddrMode.ZP    , 0, em.op_LDY),
    0xA5: ( 'LDA',  AddrMode.ZP    , 0, em.op_LDA),
    0xA6: ( 'LDX',  AddrMode.ZP    , 0, em.op_LDX),
    0xA7: ( 'SMB2', AddrMode.ZP    , 0, 0),
    0xA8: ( 'TAY',  AddrMode.IMP   , 0, em.op_TAY),
    0xA9: ( 'LDA',  AddrMode.IMM   , 0, em.op_LDA),
    0xAA: ( 'TAX',  AddrMode.IMP   , 0, em.op_TAX),
    0xAB: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xAC: ( 'LDY',  AddrMode.ABS   , 0, em.op_LDY),
    0xAD: ( 'LDA',  AddrMode.ABS   , 0, em.op_LDA),
    0xAE: ( 'LDX',  AddrMode.ABS   , 0, em.op_LDX),
    0xAF: ( 'BBS2', AddrMode.ZPR   , 0, 0),
    0xB0: ( 'BCS',  AddrMode.BRA   , 0, 0),
    0xB1: ( 'LDA',  AddrMode.INDY  , 0, em.op_LDA),
    0xB2: ( 'LDA',  AddrMode.IND   , 0, em.op_LDA),
    0xB3: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xB4: ( 'LDY',  AddrMode.ZPX   , 0, em.op_LDY),
    0xB5: ( 'LDA',  AddrMode.ZPX   , 0, em.op_LDA),
    0xB6: ( 'LDX',  AddrMode.ZPY   , 0, em.op_LDX),
    0xB7: ( 'SMB3', AddrMode.ZP    , 0, 0),
    0xB8: ( 'CLV',  AddrMode.IMP   , 0, em.op_CLV),
    0xB9: ( 'LDA',  AddrMode.ABSY  , 0, em.op_LDA),
    0xBA: ( 'TSX',  AddrMode.IMP   , 0, em.op_TSX),
    0xBB: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xBC: ( 'LDY',  AddrMode.ABSX  , 0, em.op_LDY),
    0xBD: ( 'LDA',  AddrMode.ABSX  , 0, em.op_LDA),
    0xBE: ( 'LDX',  AddrMode.ABSY  , 0, em.op_LDX),
    0xBF: ( 'BBS3', AddrMode.ZPR   , 0, 0),
    0xC0: ( 'CPY',  AddrMode.IMM   , 0, em.op_CPY),
    0xC1: ( 'CMP',  AddrMode.INDX  , 0, em.op_CMP),
    0xC2: ( 'NOP',  AddrMode.IMM   , 0, 0),
    0xC3: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xC4: ( 'CPY',  AddrMode.ZP    , 0, em.op_CPY),
    0xC5: ( 'CMP',  AddrMode.ZP    , 0, em.op_CMP),
    0xC6: ( 'DEC',  AddrMode.ZP    , 0, em.op_DEC),
    0xC7: ( 'SMB4', AddrMode.ZP    , 0, 0),
    0xC8: ( 'INY',  AddrMode.IMP   , 0, em.op_INY),
    0xC9: ( 'CMP',  AddrMode.IMM   , 0, em.op_CMP),
    0xCA: ( 'DEX',  AddrMode.IMP   , 0, em.op_DEX),
    0xCB: ( 'WAI',  AddrMode.IMP   , 0, 0),
    0xCC: ( 'CPY',  AddrMode.ABS   , 0, em.op_CPY),
    0xCD: ( 'CMP',  AddrMode.ABS   , 0, em.op_CMP),
    0xCE: ( 'DEC',  AddrMode.ABS   , 0, em.op_DEC),
    0xCF: ( 'BBS4', AddrMode.ZPR   , 0, 0),
    0xD0: ( 'BNE',  AddrMode.BRA   , 0, 0),
    0xD1: ( 'CMP',  AddrMode.INDY  , 0, em.op_CMP),
    0xD2: ( 'CMP',  AddrMode.IND   , 0, em.op_CMP),
    0xD3: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xD4: ( 'NOP',  AddrMode.ZPX   , 0, 0),
    0xD5: ( 'CMP',  AddrMode.ZPX   , 0, em.op_CMP),
    0xD6: ( 'DEC',  AddrMode.ZPX   , 0, em.op_DEC),
    0xD7: ( 'SMB5', AddrMode.ZP    , 0, 0),
    0xD8: ( 'CLD',  AddrMode.IMP   , 0, em.op_CLD),
    0xD9: ( 'CMP',  AddrMode.ABSY  , 0, em.op_CMP),
    0xDA: ( 'PHX',  AddrMode.IMP   , 1, em.op_PHX),
    0xDB: ( 'STP',  AddrMode.IMP   , 0, 0),
    0xDC: ( 'NOP',  AddrMode.ABS   , 0, 0),
    0xDD: ( 'CMP',  AddrMode.ABSX  , 0, em.op_CMP),
    0xDE: ( 'DEC',  AddrMode.ABSX  , 0, em.op_DEC),
    0xDF: ( 'BBS5', AddrMode.ZPR   , 0, 0),
    0xE0: ( 'CPX',  AddrMode.IMM   , 0, em.op_CPX),
    0xE1: ( 'SBC',  AddrMode.INDX  , 0, em.op_SBC),
    0xE2: ( 'NOP',  AddrMode.IMM   , 0, 0),
    0xE3: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xE4: ( 'CPX',  AddrMode.ZP    , 0, em.op_CPX),
    0xE5: ( 'SBC',  AddrMode.ZP    , 0, em.op_SBC),
    0xE6: ( 'INC',  AddrMode.ZP    , 0, em.op_INC),
    0xE7: ( 'SMB6', AddrMode.ZP    , 0, 0),
    0xE8: ( 'INX',  AddrMode.IMP   , 0, em.op_INX),
    0xE9: ( 'SBC',  AddrMode.IMM   , 0, em.op_SBC),
    0xEA: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xEB: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xEC: ( 'CPX',  AddrMode.ABS   , 0, em.op_CPX),
    0xED: ( 'SBC',  AddrMode.ABS   , 0, em.op_SBC),
    0xEE: ( 'INC',  AddrMode.ABS   , 0, em.op_INC),
    0xEF: ( 'BBS6', AddrMode.ZPR   , 0, 0),
    0xF0: ( 'BEQ',  AddrMode.BRA   , 0, 0),
    0xF1: ( 'SBC',  AddrMode.INDY  , 0, em.op_SBC),
    0xF2: ( 'SBC',  AddrMode.IND   , 0, em.op_SBC),
    0xF3: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xF4: ( 'NOP',  AddrMode.ZPX   , 0, 0),
    0xF5: ( 'SBC',  AddrMode.ZPX   , 0, em.op_SBC),
    0xF6: ( 'INC',  AddrMode.ZPX   , 0, em.op_INC),
    0xF7: ( 'SMB7', AddrMode.ZP    , 0, 0),
    0xF8: ( 'SED',  AddrMode.IMP   , 0, em.op_SED),
    0xF9: ( 'SBC',  AddrMode.ABSY  , 0, em.op_SBC),
    0xFA: ( 'PLX',  AddrMode.IMP   , 0, em.op_PLX),
    0xFB: ( 'NOP',  AddrMode.IMP   , 0, 0),
    0xFC: ( 'NOP',  AddrMode.ABS   , 0, 0),
    0xFD: ( 'SBC',  AddrMode.ABSX  , 0, em.op_SBC),
    0xFE: ( 'INC',  AddrMode.ABSX  , 0, em.op_INC),
    0xFF: ( 'BBS7', AddrMode.ZPR   , 0, 0),
}
