from .agent import Agent
from .bool import Bool
from .component import Component
from .coverage import Coverage
from .coverbin import Coverbin
from .covercross import Covercross
from .covergroup import Covergroup
from .coverpoint import Coverpoint
from .driver import Driver
from .enum import Enum
from .env import Env
from .factory import Factory
from .fifo import Fifo
from .float import Double, Float, Fp16, Fp32, Fp64, Half
from .int import Byte, Int, Int8, Int16, Int32, Int64
from .list import List, Queue
from .log import Log
from .logic import Logic
from .memory import Memory
from .model import Model
from .monitor import Monitor
from .object import Object
from .phase import Phase
from .phase_manager import PhaseManager
from .port import Port
from .scoreboard import Scoreboard
from .scoreboard_indexed import IndexedScoreboard
from .sequence import Sequence
from .sequence_item import SequenceItem
from .sequencer import Sequencer
from .struct import Struct
from .trace import Trace
from .transaction import Transaction
from .uint import Uint, Uint8, Uint16, Uint32, Uint64
from .visualization import Visualization

# Enable logging
Log._override_cocotb_logging()

# Add default phases
PhaseManager.add_phase("RUN", None, top_down=False)
PhaseManager.add_phase("REPORT", PhaseManager.get_phase("RUN"), top_down=False)

# Add version
__version__: str = "0.4.1"

__all__ = [
    "__version__",
    "Log",
    "List",
    "Queue",
    "Fifo",
    "Port",
    "Phase",
    "Phase_Manager",
    "Object",
    "Transaction",
    "Component",
    "Driver",
    "Sequencer",
    "Monitor",
    "Model",
    "Scoreboard",
    "IndexedScoreboard",
    "Agent",
    "Env",
    "SequenceItem",
    "Sequence",
    "Logic",
    "Bool",
    "Int",
    "Int8",
    "Byte",
    "Int16",
    "Int32",
    "Int64",
    "Uint",
    "Uint8",
    "Uint16",
    "Uint32",
    "Uint64",
    "Fp16",
    "Half",
    "Fp32",
    "Float",
    "Fp64",
    "Double",
    "Enum",
    "Coverbin",
    "Coverpoint",
    "Covercross",
    "Covergroup",
    "Coverage",
    "Visualization",
    "Factory",
    "Trace",
    "Memory",
    "Struct",
]
