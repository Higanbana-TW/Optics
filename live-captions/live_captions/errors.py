"""User-facing failures. Message text is Traditional Chinese."""


class CaptionsError(RuntimeError):
    pass


class AudioUnavailable(CaptionsError):
    pass


class ConfigError(CaptionsError):
    pass
