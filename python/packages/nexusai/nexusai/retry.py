from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    enabled: bool = True
    max_attempts: int = 3
    max_elapsed_seconds: float = 15.0
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.max_elapsed_seconds < 0:
            raise ValueError("max_elapsed_seconds cannot be negative")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")
