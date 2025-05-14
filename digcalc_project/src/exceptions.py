class NoScaleError(RuntimeError):
    """Raised when a tracing operation requires a calibrated ProjectScale but none is set.""" 