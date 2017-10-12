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

import sigrokdecode as srd
from functools import reduce
from .tables import addr_mode_len_map, instr_table, AddrMode
import string

class Ann:
    DATA, FETCH, OP1, OP2, MEMRD, MEMWR, INSTR, ADDR = range(8)

class Row:
    DATABUS, INSTRUCTIONS, ADDRESS = range(3)

class Pin:
    D0, D7 = 0, 7
    RNW, SYNC, RDYN, IRQN, NMIN, RSTN, PHI2 = range(8, 15)
    A0, A15 = 15, 30

class Cycle:
    FETCH, OP1, OP2, MEMRD, MEMWR = range(5)

cycle_to_ann_map = {
    Cycle.FETCH: Ann.FETCH,
    Cycle.OP1:   Ann.OP1,
    Cycle.OP2:   Ann.OP2,
    Cycle.MEMRD: Ann.MEMRD,
    Cycle.MEMWR: Ann.MEMWR,
}

cycle_to_name_map = {
    Cycle.FETCH: 'Fetch',
    Cycle.OP1:   'Op1',
    Cycle.OP2:   'Op2',
    Cycle.MEMRD: 'Mem Rd',
    Cycle.MEMWR: 'Mem Wr',
}

def signed_byte(byte):
    return byte if byte < 128 else byte - 256

def reduce_bus(bus):
    if 0xFF in bus:
        return None # unassigned bus channels
    else:
        return reduce(lambda a, b: (a << 1) | b, reversed(bus))

class Decoder(srd.Decoder):
    api_version = 3
    id       = 'mos6502'
    name     = 'MOS6502'
    longname = 'Mostek 6502 CPU'
    desc     = 'Mostek 6502 microprocessor disassembly.'
    license  = 'gplv3+'
    inputs   = ['logic']
    outputs  = ['mos6502']
    channels = tuple({
            'id': 'd%d' % i,
            'name': 'D%d' % i,
            'desc': 'Data bus line %d' % i
            } for i in range(8)
    ) + (
        {'id': 'rnw', 'name': 'RNW', 'desc': 'Memory read or write'},
        {'id': 'sync', 'name': 'SYNC', 'desc': 'Sync - opcode fetch'},
    )
    optional_channels = (
#        {'id': 'rdy',  'name': 'RDY',  'desc': 'Ready, allows for wait states'},
#        {'id': 'irq',  'name': 'IRQN', 'desc': 'Maskable interrupt'},
#        {'id': 'nmi',  'name': 'NMIN', 'desc': 'Non-maskable interrupt'},
#        {'id': 'rst',  'name': 'RSTN', 'desc': 'Reset'},
#        {'id': 'phi2', 'name': 'PHI2', 'desc': 'Phi2 clock, falling edge active'},
#    ) + tuple({
#        'id': 'a%d' % i,
#        'name': 'A%d' % i,
#        'desc': 'Address bus line %d' % i
#        } for i in range(16)
    )
    annotations = (
        ('data',   'Data bus'),
        ('fetch',  'Fetch opcode'),
        ('op1',    'Operand 1'),
        ('op2',    'Operand 2'),
        ('memrd',  'Memory Read'),
        ('memwr',  'Memory Write'),
        ('instr',  'Instruction'),
    )
    annotation_rows = (
        ('databus', 'Data bus', (Ann.DATA,)),
        ('cycle', 'Cycle', (Ann.FETCH, Ann.OP1, Ann.OP2, Ann.MEMRD, Ann.MEMWR)),
        ('instructions', 'Instructions', (Ann.INSTR,)),
#        ('addrbus', 'Address bus', (Ann.ADDR,)),
    )

#    def __init__(self):

    def start(self):
        self.out_ann    = self.register(srd.OUTPUT_ANN)
        self.ann_data   = None

    def decode(self):
        last_fetch = -1
        opcount = 0
        cycle = Cycle.MEMRD
        mnemonic = '???'
        opcode = 0
        op1 = 0
        op2 = 0
        write_count = 0
        pc = -1
        next_pc = -1

        while True:
            # TODO: Come up with more appropriate self.wait() conditions.
            pins = self.wait()

            bus_data = reduce_bus(pins[Pin.D0:Pin.D7+1])
            #print('bus data = ' + str(bus_data))
            self.put(self.samplenum, self.samplenum + 1, self.out_ann, [Ann.DATA, [format(bus_data, '02x')]])

            # TODO, add warnings if RNW not as expected

            if pins[Pin.SYNC] == 1:

                if (last_fetch > 0):
                    if write_count == 3 and opcode != 0:
                        # An interrupt
                        self.put(last_fetch, self.samplenum, self.out_ann, [Ann.INSTR, [format(pc, '04x') + ': ' + 'INT!']])
                    else:
                        self.put(last_fetch, self.samplenum, self.out_ann, [Ann.INSTR, [format(pc, '04x') + ': ' + fmt.format(mnemonic, op1, op2)]])

                # Look for control flow changes and update the PC
                if opcode == 0x40 or opcode == 0x00 or opcode == 0x6c or opcode == 0x7c or write_count == 3:
                    # RTI, BRK, INTR, JMP (ind), JMP (ind, X)
                    pc = (next_pc >> 8) & 0xffff
                elif opcode == 0x20 or opcode == 0x4c:
                    # JSR abs, JMP abs
                    pc = op2 << 8 | op1
                elif (opcode & 0x1f) == 0x10 and self.samplenum - last_fetch != 2:
                    # BXX: op1 if taken
                    pc += signed_byte(op1) + 2
                elif opcode == 0x60:
                    # RTS
                    pc = (next_pc + 1) & 0xffff
                else:
                    # Otherwise, increment pc by length of instuction
                    pc += len

                last_fetch = self.samplenum

                cycle    = Cycle.FETCH
                opcode   = bus_data
                instr    = instr_table[opcode]
                mnemonic = instr[0]
                mode     = instr[1]
                len      = addr_mode_len_map[mode][0]
                fmt      = addr_mode_len_map[mode][1]
                opcount  = len - 1
                write_count = 0
                next_pc = 0

            elif pins[Pin.RNW] == 0:
                cycle = Cycle.MEMWR
                write_count += 1

            elif cycle == Cycle.FETCH and opcount > 0:
                cycle = Cycle.OP1
                opcount -= 1
                op1 = bus_data;

            elif cycle == Cycle.OP1 and opcount > 0:
                if (opcode == 0x20): # JSR is <opcode> <op1> <dummp stack rd> <stack wr> <stack wr> <op2>
                    cycle = Cycle.MEMRD
                else:
                    cycle = Cycle.OP2
                    opcount -= 1
                    op2 = bus_data

            else:
                if (opcode == 0x20): # JSR, see above
                    cycle = Cycle.OP2
                    opcount -= 1
                    op2 = bus_data
                else:
                    cycle = Cycle.MEMRD
                    next_pc = (next_pc >> 8) | (bus_data << 16)

            self.put(self.samplenum, self.samplenum + 1, self.out_ann, [cycle_to_ann_map[cycle], [cycle_to_name_map[cycle]]])
