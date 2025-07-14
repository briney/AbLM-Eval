from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional, Union


@dataclass
class BaseTaskConfig(ABC):
    """Base configuration class for all evaluation tasks.

    This class provides common properties and methods shared across all task configurations.
    """

    # Meta properties - subclasses must override config_type
    config_type: str = field(init=False)

    @property
    @abstractmethod
    def task_dir(self) -> str:
        """Return the task directory name."""
        pass

    @property
    def name(self) -> str:
        """Return a human-readable task name."""
        return (self.task_dir).replace("_", " ").title()

    @property
    @abstractmethod
    def runner(self) -> Callable:
        """Return the task runner function."""
        pass

    # Data processing properties
    sequence_column: Optional[str] = None
    heavy_column: Optional[str] = None
    light_column: Optional[str] = None
    separator: str = "<cls>"

    # Tokenization properties (subclasses can override defaults)
    tokenizer_path: str | None = None
    padding: Union[bool, str] = "max_length"
    max_len: int = 256
    truncate: bool = True
    add_special_tokens: bool = True
    num_proc: int = 128
    # keep_columns: list = field(default_factory=list)

    # Output
    output_dir: str = None
