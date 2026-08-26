class AutoISPError(Exception):
    pass


class ExecutionInterruptedError(AutoISPError):
    pass


class InvalidStepError(AutoISPError):
    pass


class LaunchError(AutoISPError):
    pass
