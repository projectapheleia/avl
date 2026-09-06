// Copyright 2026 Apheleia
//
// Description:
// Apheleia Verification Library (AVL) comparison benchmark - the workload.
//
// Sixteen classes, each declaring the same representative set of variables -
// four unsigned logic vectors and two signed integers - under the same eleven
// constraints, and differing in the constants those constraints are written
// with. Every flavour of the benchmark randomizes the same sixteen classes:
// these are the SystemVerilog ones, ../cocotb/classes_avl.py holds the AVL ones
// and ../cocotb/classes_pyuvm.py the pyvsc ones.
//
// The constraints are written once, in item_base, against non-rand members that
// each class sets in its constructor - the way a testbench parameterizes one
// item type rather than writing the same constraint out sixteen times. The
// solver sees those members as the constants they are.
//
// | constraint    | category                       | what it says                                    |
// |---------------|--------------------------------|-------------------------------------------------|
// | c_addr        | arithmetic                     | addr lies in this class's 16 MB window          |
// | c_align       | arithmetic, modulo             | addr is aligned to 4, 8 or 16                   |
// | c_page        | bitwise, shift                 | addr >> 24 is this class's page                 |
// | c_len         | arithmetic range               | 1 <= len <= lmax                                |
// | c_kind        | list                           | kind is one of four values                      |
// | c_mask        | bitwise, and                   | bits of mask held at zero                       |
// | c_mask_kind   | bitwise, xor, across fields    | the low nibble of mask is tied to kind          |
// | c_delta       | signed arithmetic              | -dmax <= delta <= dmax, and not zero            |
// | c_level       | signed arithmetic              | -vmax <= level <= vmax                          |
// | c_sum         | signed arithmetic, two fields  | delta + level >= 0                              |
// | c_kind0       | implication                    | the first kind implies a single beat            |
//
// `include`d by comparison_bench.sv, inside the module, so that run_item() can
// reach the module's checksum and count.

localparam int unsigned BENCH_CLASSES = 16;

class item_base;

    rand bit [31:0]        addr;
    rand bit [15:0]        len;
    rand bit [7:0]         mask;
    rand bit [7:0]         kind;
    rand bit signed [15:0] delta;
    rand bit signed [15:0] level;

    // What this class is written with, set by its constructor. Not rand, so the
    // solver sees them as constants.
    bit [31:0]        low, high, page;
    int unsigned      align;
    bit [15:0]        lmax;
    bit [7:0]         kind0, kind1, kind2, kind3;
    bit [7:0]         clear, xr;
    bit signed [15:0] dmax, vmax;

    constraint c_addr      { addr >= low; addr <= high; }
    constraint c_align     { addr % align == 32'd0; }
    constraint c_page      { (addr >> 24) == page; }
    constraint c_len       { len >= 16'd1; len <= lmax; }
    constraint c_kind      { kind inside {kind0, kind1, kind2, kind3}; }
    constraint c_mask      { (mask & clear) == 8'h00; }
    constraint c_mask_kind { ((mask ^ kind) & 8'h0f) == xr; }
    constraint c_delta     { delta >= -dmax; delta <= dmax; delta != 16'sd0; }
    constraint c_level     { level >= -vmax; level <= vmax; }
    constraint c_sum       { (delta + level) >= 16'sd0; }
    constraint c_kind0     { (kind == kind0) -> (len == 16'd1); }

    // Every item is checked against all eleven constraints, in every flavour,
    // so that a flavour drawing an illegal value fails rather than being
    // reported as fast.
    function void check();
        if (!(addr >= low && addr <= high))
            $fatal(1, "c_addr violated : addr=%08x", addr);
        if ((addr % align) != 32'd0)
            $fatal(1, "c_align violated : addr=%08x", addr);
        if ((addr >> 24) != page)
            $fatal(1, "c_page violated : addr=%08x", addr);
        if (!(len >= 16'd1 && len <= lmax))
            $fatal(1, "c_len violated : len=%0d", len);
        if (!(kind inside {kind0, kind1, kind2, kind3}))
            $fatal(1, "c_kind violated : kind=%0d", kind);
        if ((mask & clear) != 8'h00)
            $fatal(1, "c_mask violated : mask=%02x", mask);
        if (((mask ^ kind) & 8'h0f) != xr)
            $fatal(1, "c_mask_kind violated : mask=%02x kind=%02x", mask, kind);
        if (!(delta >= -dmax && delta <= dmax) || delta == 16'sd0)
            $fatal(1, "c_delta violated : delta=%0d", delta);
        if (!(level >= -vmax && level <= vmax))
            $fatal(1, "c_level violated : level=%0d", level);
        if ((delta + level) < 16'sd0)
            $fatal(1, "c_sum violated : delta=%0d level=%0d", delta, level);
        if (kind == kind0 && len != 16'd1)
            $fatal(1, "c_kind0 violated : len=%0d", len);
    endfunction

    function longint unsigned sum();
        return 64'(addr) + 64'(len) + 64'(mask) + 64'(kind) + 64'(delta) + 64'(level);
    endfunction

endclass : item_base


// item_0 : page 0x10, aligned to 8, len <= 16, kinds {9, 37, 52, 55}, mask & 0xc0 == 0, nibble 0xe, delta +/-4096, level +/-512
class item_0 extends item_base;
    function new();
        low   = 32'h10000000; high  = 32'h10ffffff; page = 32'h10;
        align = 8; lmax = 16'd16;
        kind0 = 8'd9; kind1 = 8'd37; kind2 = 8'd52; kind3 = 8'd55;
        clear = 8'hc0; xr = 8'h0e;
        dmax  = 16'sd4096; vmax = 16'sd512;
    endfunction
endclass : item_0

// item_1 : page 0x2f, aligned to 4, len <= 1024, kinds {7, 14, 25, 51}, mask & 0xc0 == 0, nibble 0x0, delta +/-4096, level +/-128
class item_1 extends item_base;
    function new();
        low   = 32'h2f000000; high  = 32'h2fffffff; page = 32'h2f;
        align = 4; lmax = 16'd1024;
        kind0 = 8'd7; kind1 = 8'd14; kind2 = 8'd25; kind3 = 8'd51;
        clear = 8'hc0; xr = 8'h00;
        dmax  = 16'sd4096; vmax = 16'sd128;
    endfunction
endclass : item_1

// item_2 : page 0x10, aligned to 8, len <= 16, kinds {15, 38, 47, 52}, mask & 0x10 == 0, nibble 0x0, delta +/-64, level +/-128
class item_2 extends item_base;
    function new();
        low   = 32'h10000000; high  = 32'h10ffffff; page = 32'h10;
        align = 8; lmax = 16'd16;
        kind0 = 8'd15; kind1 = 8'd38; kind2 = 8'd47; kind3 = 8'd52;
        clear = 8'h10; xr = 8'h00;
        dmax  = 16'sd64; vmax = 16'sd128;
    endfunction
endclass : item_2

// item_3 : page 0x10, aligned to 16, len <= 64, kinds {14, 28, 44, 63}, mask & 0xc0 == 0, nibble 0xf, delta +/-256, level +/-128
class item_3 extends item_base;
    function new();
        low   = 32'h10000000; high  = 32'h10ffffff; page = 32'h10;
        align = 16; lmax = 16'd64;
        kind0 = 8'd14; kind1 = 8'd28; kind2 = 8'd44; kind3 = 8'd63;
        clear = 8'hc0; xr = 8'h0f;
        dmax  = 16'sd256; vmax = 16'sd128;
    endfunction
endclass : item_3

// item_4 : page 0x20, aligned to 4, len <= 1024, kinds {15, 30, 44, 49}, mask & 0x10 == 0, nibble 0x5, delta +/-1024, level +/-32
class item_4 extends item_base;
    function new();
        low   = 32'h20000000; high  = 32'h20ffffff; page = 32'h20;
        align = 4; lmax = 16'd1024;
        kind0 = 8'd15; kind1 = 8'd30; kind2 = 8'd44; kind3 = 8'd49;
        clear = 8'h10; xr = 8'h05;
        dmax  = 16'sd1024; vmax = 16'sd32;
    endfunction
endclass : item_4

// item_5 : page 0x40, aligned to 8, len <= 4096, kinds {22, 47, 48, 58}, mask & 0x30 == 0, nibble 0x9, delta +/-1024, level +/-512
class item_5 extends item_base;
    function new();
        low   = 32'h40000000; high  = 32'h40ffffff; page = 32'h40;
        align = 8; lmax = 16'd4096;
        kind0 = 8'd22; kind1 = 8'd47; kind2 = 8'd48; kind3 = 8'd58;
        clear = 8'h30; xr = 8'h09;
        dmax  = 16'sd1024; vmax = 16'sd512;
    endfunction
endclass : item_5

// item_6 : page 0x40, aligned to 8, len <= 4096, kinds {32, 55, 57, 63}, mask & 0x10 == 0, nibble 0xf, delta +/-256, level +/-512
class item_6 extends item_base;
    function new();
        low   = 32'h40000000; high  = 32'h40ffffff; page = 32'h40;
        align = 8; lmax = 16'd4096;
        kind0 = 8'd32; kind1 = 8'd55; kind2 = 8'd57; kind3 = 8'd63;
        clear = 8'h10; xr = 8'h0f;
        dmax  = 16'sd256; vmax = 16'sd512;
    endfunction
endclass : item_6

// item_7 : page 0x11, aligned to 8, len <= 4096, kinds {26, 27, 43, 52}, mask & 0x80 == 0, nibble 0x2, delta +/-4096, level +/-512
class item_7 extends item_base;
    function new();
        low   = 32'h11000000; high  = 32'h11ffffff; page = 32'h11;
        align = 8; lmax = 16'd4096;
        kind0 = 8'd26; kind1 = 8'd27; kind2 = 8'd43; kind3 = 8'd52;
        clear = 8'h80; xr = 8'h02;
        dmax  = 16'sd4096; vmax = 16'sd512;
    endfunction
endclass : item_7

// item_8 : page 0x40, aligned to 8, len <= 256, kinds {7, 11, 33, 50}, mask & 0xc0 == 0, nibble 0x0, delta +/-4096, level +/-32
class item_8 extends item_base;
    function new();
        low   = 32'h40000000; high  = 32'h40ffffff; page = 32'h40;
        align = 8; lmax = 16'd256;
        kind0 = 8'd7; kind1 = 8'd11; kind2 = 8'd33; kind3 = 8'd50;
        clear = 8'hc0; xr = 8'h00;
        dmax  = 16'sd4096; vmax = 16'sd32;
    endfunction
endclass : item_8

// item_9 : page 0x40, aligned to 16, len <= 4096, kinds {20, 46, 55, 63}, mask & 0xc0 == 0, nibble 0x5, delta +/-256, level +/-512
class item_9 extends item_base;
    function new();
        low   = 32'h40000000; high  = 32'h40ffffff; page = 32'h40;
        align = 16; lmax = 16'd4096;
        kind0 = 8'd20; kind1 = 8'd46; kind2 = 8'd55; kind3 = 8'd63;
        clear = 8'hc0; xr = 8'h05;
        dmax  = 16'sd256; vmax = 16'sd512;
    endfunction
endclass : item_9

// item_10 : page 0x11, aligned to 16, len <= 4096, kinds {1, 15, 50, 63}, mask & 0x30 == 0, nibble 0xc, delta +/-1024, level +/-512
class item_10 extends item_base;
    function new();
        low   = 32'h11000000; high  = 32'h11ffffff; page = 32'h11;
        align = 16; lmax = 16'd4096;
        kind0 = 8'd1; kind1 = 8'd15; kind2 = 8'd50; kind3 = 8'd63;
        clear = 8'h30; xr = 8'h0c;
        dmax  = 16'sd1024; vmax = 16'sd512;
    endfunction
endclass : item_10

// item_11 : page 0x40, aligned to 16, len <= 16, kinds {18, 23, 30, 59}, mask & 0xc0 == 0, nibble 0x4, delta +/-256, level +/-128
class item_11 extends item_base;
    function new();
        low   = 32'h40000000; high  = 32'h40ffffff; page = 32'h40;
        align = 16; lmax = 16'd16;
        kind0 = 8'd18; kind1 = 8'd23; kind2 = 8'd30; kind3 = 8'd59;
        clear = 8'hc0; xr = 8'h04;
        dmax  = 16'sd256; vmax = 16'sd128;
    endfunction
endclass : item_11

// item_12 : page 0x20, aligned to 16, len <= 4096, kinds {4, 31, 56, 61}, mask & 0x30 == 0, nibble 0xd, delta +/-4096, level +/-128
class item_12 extends item_base;
    function new();
        low   = 32'h20000000; high  = 32'h20ffffff; page = 32'h20;
        align = 16; lmax = 16'd4096;
        kind0 = 8'd4; kind1 = 8'd31; kind2 = 8'd56; kind3 = 8'd61;
        clear = 8'h30; xr = 8'h0d;
        dmax  = 16'sd4096; vmax = 16'sd128;
    endfunction
endclass : item_12

// item_13 : page 0x40, aligned to 16, len <= 4096, kinds {1, 23, 27, 35}, mask & 0x80 == 0, nibble 0xe, delta +/-64, level +/-32
class item_13 extends item_base;
    function new();
        low   = 32'h40000000; high  = 32'h40ffffff; page = 32'h40;
        align = 16; lmax = 16'd4096;
        kind0 = 8'd1; kind1 = 8'd23; kind2 = 8'd27; kind3 = 8'd35;
        clear = 8'h80; xr = 8'h0e;
        dmax  = 16'sd64; vmax = 16'sd32;
    endfunction
endclass : item_13

// item_14 : page 0x11, aligned to 4, len <= 4096, kinds {12, 36, 38, 41}, mask & 0x80 == 0, nibble 0x1, delta +/-64, level +/-32
class item_14 extends item_base;
    function new();
        low   = 32'h11000000; high  = 32'h11ffffff; page = 32'h11;
        align = 4; lmax = 16'd4096;
        kind0 = 8'd12; kind1 = 8'd36; kind2 = 8'd38; kind3 = 8'd41;
        clear = 8'h80; xr = 8'h01;
        dmax  = 16'sd64; vmax = 16'sd32;
    endfunction
endclass : item_14

// item_15 : page 0x20, aligned to 4, len <= 256, kinds {1, 2, 29, 56}, mask & 0x10 == 0, nibble 0x5, delta +/-1024, level +/-128
class item_15 extends item_base;
    function new();
        low   = 32'h20000000; high  = 32'h20ffffff; page = 32'h20;
        align = 4; lmax = 16'd256;
        kind0 = 8'd1; kind1 = 8'd2; kind2 = 8'd29; kind3 = 8'd56;
        clear = 8'h10; xr = 8'h05;
        dmax  = 16'sd1024; vmax = 16'sd128;
    endfunction
endclass : item_15

// ---------------------------------------------------------------------------
// One item of one class per call, the classes taken in turn. A fresh item every
// time, the way a testbench builds a fresh sequence item per transaction rather
// than reusing one - which would let a solver amortize work across draws.
// ---------------------------------------------------------------------------

task automatic run_item(int unsigned idx);
    item_base it;

    case (idx)
         0: begin item_0 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_0");
                it = i; end
         1: begin item_1 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_1");
                it = i; end
         2: begin item_2 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_2");
                it = i; end
         3: begin item_3 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_3");
                it = i; end
         4: begin item_4 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_4");
                it = i; end
         5: begin item_5 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_5");
                it = i; end
         6: begin item_6 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_6");
                it = i; end
         7: begin item_7 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_7");
                it = i; end
         8: begin item_8 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_8");
                it = i; end
         9: begin item_9 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_9");
                it = i; end
        10: begin item_10 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_10");
                it = i; end
        11: begin item_11 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_11");
                it = i; end
        12: begin item_12 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_12");
                it = i; end
        13: begin item_13 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_13");
                it = i; end
        14: begin item_14 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_14");
                it = i; end
        15: begin item_15 i = new();
                if (i.randomize() == 0) $fatal(1, "randomization failed : item_15");
                it = i; end
        default: $fatal(1, "no such class : %0d", idx);
    endcase

    it.check();
    checksum += it.sum();
    count    += 1;
endtask
