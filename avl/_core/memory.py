# Copyright 2024 Apheleia
#
# Description:
# Apheleia Verification Library Memory Model

import bincopy
import pandas as pd
import warnings


class Memory:

    def __init__(self, width : int = 32) -> None:
        """
        Initialize the memory model.

        :param width: Width of the memory in bits (default is 32).
        :type width: int
        :raises ValueError: If width is not a positive integer.
        """
        if width <= 0 or width % 8 != 0:
            raise ValueError("Width must be a positive integer and a multiple of 8.")

        self.width = width
        self.nbytes = width // 8
        self.ranges = []
        self.memory = {}
        self.endianness = 'little'
        self.init_fn = lambda address : 0

    def _align_address_(self, address: int) -> int:
        """
        Align the address to the memory width.

        :param address: Address to align.
        :type address: int
        :return: Aligned address.
        :rtype: int
        """
        return address & ~(self.nbytes - 1)

    def _check_address_(self, address: int) -> None:
        """
        Check if the address is valid.

        :param address: Address to check.
        :type address: int
        :raises ValueError: If address is not a positive integer.
        """
        for r in self.ranges:
            if address >= r[0] and address < r[1]:
                return True

        self.miss(address)
        return False

    def _get_byte_(self, address: int) -> int:
        """
        Get the byte at the specified address.

        :param address: Address to get the byte from.
        :type address: int
        :return: Byte value at the specified address.
        :rtype: int
        :raises KeyError: If address is not in memory.
        """
        if address not in self.memory:
            self.memory[address] = self.init_fn(address)
        return self.memory[address]

    def _get_offset_(self, address: int) -> int:
        """
        Get offset of address relative to memory width

        :param address: Address to get offset from.
        :type address: int
        :return: Offset.
        :rtype: int
        """
        return address & (self.nbytes - 1)

    def _gen_strobe_(self, offset: int, nbytes: int) -> int:
        """
        Generate the byte enables for nbytes at a given offset

        :param offset: Offset in bytes
        :type offset: int
        :param nbytes: Number of bytes
        :type nbytes: int
        :return: Strobe
        :rtype: int
        """
        if nbytes == 0:
            return 0

        # base mask
        mask = (1 << nbytes) - 1

        # normalize offset to be within bounds
        offset %= self.nbytes

        # adjust for endianness
        if self.endianness == "big":
            # For big endian, reverse the offset direction
            # Python's modulo already handles negatives correctly, but we'll be explicit
            offset = ((self.nbytes - offset - nbytes) % self.nbytes + self.nbytes) % self.nbytes

        # rotate mask within self.nbytes (to handle wrapping)
        mask = ((mask << offset) | (mask >> (self.nbytes - offset))) & ((1 << self.nbytes) - 1)

        return mask

    def set_init_fn(self, fn : callable) -> None:
        """
        Set the initialization policy for the memory

        Defined as a lambda function that takes an address and returns a value.

        :param fn: Function to initialize memory at a given address.
        :type fn: callable
        :raises ValueError: If fn is not callable.
        :example:
            memory.set_init_fn(lambda address: 0)
        """
        self.init_fn = fn

    def set_endianness(self, endianness: str) -> None:
        """
        Set the endianness of the memory (little / big).

        :param endianness: Endianness, can be 'little' or 'big'.
        :type endianness: str
        :raises ValueError: If endianness is not 'little' or 'big'.
        """
        if endianness not in ['little', 'big']:
            raise ValueError("Endianness must be either 'little' or 'big'.")
        self.endianness = endianness

    def add_range(self, start: int, end: int) -> None:
        """
        Add a memory range.

        :param start: Start address of the memory range.
        :type start: int
        :param end: End address of the memory range.
        :type end: int
        :raises ValueError: If start address is not less than end address.
        """
        if start >= end:
            raise ValueError("Start address must be less than end address.")
        self.ranges.append((start, end))

    def miss(self, address : int) -> None:
        """
        Action to be taken when a memory miss occurs.
        This method raises a ValueError indicating that the address was not found in memory.
        Expect user to override this method to implement custom behavior.

        :param address: Address that caused the miss.
        :type address: int
        :raises ValueError: Always raised to indicate a memory miss.
        """
        raise KeyError(f"Miss at {address}")

    def read(self, address: int, num_bytes : int = None, rotated : bool = False) -> int:
        """
        Read a value from the memory at the specified address.

        Calls miss() if the address is not found in memory.

        Rotate setting determines if the data should be rotated within the memory line
        Non-rotated data will be returns num_bytes from bit0 of the return data
        Rotated data will be returned from the offset within the memory line. i.e.
        a LE 4B read from address 0x1 on a 4B memory where each byte contains its address
        reads 0x03020104

        :param address: Address to read from.
        :type address: int
        :param num_bytes: Number of bytes to read
        :type num_bytes: int
        :param rotated: Rotate data based on offset
        :type rotated: bool
        :return: Value at the specified address.
        :rtype: int
        """

        # Offset in line and aligned address
        offset = self._get_offset_(address)

        if num_bytes is None:
            num_bytes = self.nbytes

        self._check_address_(address)
        self._check_address_(address + num_bytes - 1)

        data = [0] * self.nbytes
        for i in range(num_bytes):
            if rotated:
                idx = (offset + i) % self.nbytes
            else:
                idx = i
            data[idx] = self._get_byte_(address + i)

        return int.from_bytes(data, self.endianness)

    def write(self, address: int, value: int, num_bytes : int = None, strobe : int = None, rotated : bool = False) -> None:
        """
        Write a value to the memory at the specified address.

        Calls miss() if the address is not found in memory.

        Rotated setting determines if the data is rotated within the memory line
        Non-rotated data will write num_bytes from bit0 to the memory
        Rotated data will write from the offset within the memory line.i.e.
        a LE 4B write of 0x03020100 to address 0x1 on a 4B memory writes:
            - mem[1] = 0x01
            - mem[2] = 0x02
            - mem[3] = 0x03
            - mem[4] = 0x00

        :param address: Address to write to.
        :type address: int
        :param value: Value to write.
        :type value: int
        :param num_bytes: Number of bytes to write (default is width // 8).
        :type num_bytes: int, optional
        :param strobe: Strobe signal
        :type strobe: int, optional
        :param rotated: Rotate data and strobe based on offset
        :type rotated: bool
        """

        # Offset in line
        offset = self._get_offset_(address)

        # Check params
        if (num_bytes is not None) and (strobe is not None):
            if num_bytes != self.nbytes:
                warnings.warn(f"num_bytes != memory width for write with strobe - overriding to memory width",
                              UserWarning,
                              stacklevel=2)
                num_bytes = self.nbytes

        if num_bytes is None:
            num_bytes = self.nbytes

        if strobe is None:
            strobe = self._gen_strobe_(offset, num_bytes)

        # Check address range
        self._check_address_(address)
        self._check_address_(address + num_bytes - 1)

        # Mask data
        value &= (1 << self.width) - 1

        # Convert data to bytes, do endianness conversion and pad to memory width
        data = list(value.to_bytes(num_bytes, self.endianness))
        data.extend([0] * max(0, self.nbytes - len(data)))

        if not rotated:
            data = data[-offset:] + data[:-offset]

        # Convert strobe to little endian list of bits
        byte_en = [(strobe >> i) & 0x1 for i in range(self.nbytes)]
        if self.endianness != "little":
            byte_en.reverse()

        for i in range(num_bytes):
            idx = (offset + i)%self.nbytes
            if byte_en[idx]:
                self.memory[address + i] = data[idx]

    def export_to_file(self, filename: str, fmt : str = None) -> None:
        """
        Export memory contents to a file.

        If fmt is not specified, it will be inferred from the file extension.

        :param filename: Path to the file where memory contents will be saved.
        :type filename: str
        :param fmt: Format of the file, can be 'vhex' or 'vbin'.
        :type fmt: str, optional
        :raises ValueError: If format is not supported.
        """

        def exists(address: int):
            """
            Pad the whole memory width
            """
            exists = False
            for i in range(address, address + self.nbytes):
                if i in self.memory:
                    exists = True
                    break

            self.read(self._align_address_(address))
            return exists

        def verilog(filename: str, fmt : str) -> None:
            """
            Export memory contents to a verilog hex file.
            """

            with open(filename, 'w') as f:
                for r in self.ranges:
                    new_address = True
                    for a in range(r[0], r[1], self.nbytes):
                        if exists(a):
                            if new_address:
                                f.write(f"@{a:04x}\n")
                                new_address = False

                            if fmt == "vhex":
                                f.write(f"{self.read(a, self.nbytes):0{self.width // 4}x}\n")
                            elif fmt == "vbin":
                                f.write(f"{self.read(a, self.nbytes):0{self.width}b}\n")
                        else:
                            new_address = True

        def pandas(filename: str, fmt : str) -> None:
            """
            Export memory contents to a pandas DataFrame and save to file.
            """
            df = pd.DataFrame(list(self.memory.items()), columns=["addr", "data"])

            if fmt == "csv":
                df.to_csv(filename, index=False)
            elif fmt == "json":
                df.to_json(filename, orient='records', lines=True)
            else:
                raise ValueError(f"Unsupported file format: {fmt}")

        def bcopy(filename: str, fmt : str) -> None:
            """
            Export memory contents using bincopy.
            """
            bf = bincopy.BinFile()
            for a,d in self.memory.items():
                bf[a] = d

            if fmt in ["ihex", "hex", "ihx"]:
                with open(filename, 'w') as f:
                    f.write(bf.as_ihex())
            elif fmt == "srec":
                with open(filename, 'w') as f:
                    f.write(bf.as_srec())
            elif fmt == "ti-txt":
                with open(filename, 'w') as f:
                    f.write(bf.as_ti_txt())
            elif fmt == "vmem":
                with open(filename, 'w') as f:
                    f.write(bf.as_verilog_vmem())
            else:
                raise ValueError(f"Unsupported file format: {fmt}")

        # Default format from file extension
        if fmt is None:
            fmt = filename.split('.')[-1]

        if fmt in ["vhex", "vbin"]:
            verilog(filename, fmt=fmt)
        elif fmt in ["csv", "json"]:
            pandas(filename, fmt=fmt)
        else:
            try:
                bcopy(filename, fmt=fmt)
            except Exception as e:
                raise ValueError(f"Unsupported file format: {fmt}") from e

    def import_from_file(self, filename: str, fmt : str = None) -> None:
        """
        Load memory contents from a file.

        If fmt is not specified, it will be inferred from the file extension.

        :param filename: Path to the file containing memory contents.
        :type filename: str
        :raises FileNotFoundError: If the file does not exist.
        """
        def verilog(filename: str, fmt : str) -> None:
            """
            Load memory contents from a verilog hex file.
            """
            addr = self.ranges[0][0] if self.ranges else 0

            with open(filename) as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        continue

                    # Comments (//, ;, #)
                    for sep in ('//', ';', '#'):
                        if sep in line:
                            line = line.split(sep, 1)[0]
                    line = line.strip()
                    if not line:
                        continue

                    # New base address
                    if line.startswith('@'):
                        try:
                            addr = int(line[1:], 16)
                        except Exception as e:
                            raise ValueError(f"Invalid address marker: {line!r}") from e
                        continue

                    # Tokens separated by whitespace
                    t = line.replace(" ", "")
                    if t.startswith('0x') or t.startswith('0b'):
                        t = t[2:]

                    if fmt == "vhex":
                        bytes = int(t, 16).to_bytes(len(t) // 2, self.endianness)
                        for i in range(len(bytes)):
                            self.memory[addr+i] = bytes[i]
                    elif fmt == "vbin":
                        bytes = int(t, 2).to_bytes(len(t) // 8, self.endianness)
                        for i in range(len(bytes)):
                            self.memory[addr+i] = bytes[i]
                    else:
                        raise ValueError(f"Unsupported file format: {fmt}")
                    addr += self.width // 8

        def pandas(filename: str, fmt : str) -> None:
            """
            Export memory contents to a pandas DataFrame and save to file.
            """
            if fmt == "csv":
                df = pd.read_csv(filename)
            elif fmt == "json":
                df = pd.read_json(filename, orient='records', lines=True)
            else:
                raise ValueError(f"Unsupported file format: {fmt}")

            self.memory = dict(zip(df["addr"], df["data"], strict=False))

        def bcopy(filename: str, fmt : str) -> None:
            """
            Import memory contents using bincopy.
            """
            bf = bincopy.BinFile(filename)

            for start_address, data in bf.segments:
                for offset, byte_val in enumerate(data):
                    addr = start_address + offset
                    self.memory[addr] = byte_val

        # Default format from file extension
        if fmt is None:
            fmt = filename.split('.')[-1]

        if fmt in ["vhex", "vbin"]:
            verilog(filename, fmt=fmt)
        elif fmt in ["csv", "json"]:
            pandas(filename, fmt=fmt)
        else:
            try:
                bcopy(filename, fmt=fmt)
            except Exception as e:
                raise ValueError(f"Unsupported file format: {fmt}") from e

__all__ = ["Memory"]
