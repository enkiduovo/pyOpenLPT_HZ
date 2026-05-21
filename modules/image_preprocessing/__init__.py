from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .view import ImagePreprocessingView


def __getattr__(name):
    if name == "ImagePreprocessingView":
        from .view import ImagePreprocessingView

        return ImagePreprocessingView
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
