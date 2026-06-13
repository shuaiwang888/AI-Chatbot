"""ai-chatbot backend application."""
__version__ = "0.1.0"

# Monkey patch transformers to bypass torch.load safety check on old PyTorch versions (macOS x86_64)
try:
    import transformers.utils.import_utils
    transformers.utils.import_utils.check_torch_load_is_safe = lambda *args, **kwargs: None
    transformers.utils.import_utils.is_torch_mps_available = lambda *args, **kwargs: False
except ImportError:
    pass

try:
    import transformers.modeling_utils
    transformers.modeling_utils.check_torch_load_is_safe = lambda *args, **kwargs: None
except ImportError:
    pass

# Force CPU device for PyTorch MPS on Intel Macs to prevent NotImplementedError
try:
    import torch
    torch.backends.mps.is_available = lambda: False
    torch.backends.mps.is_built = lambda: False
    if hasattr(torch, "mps"):
        torch.mps.is_available = lambda: False
except ImportError:
    pass

# Force CPU device for accelerate to avoid MPS auto mapping
try:
    import accelerate.utils
    accelerate.utils.is_mps_available = lambda *args, **kwargs: False
except ImportError:
    pass

try:
    import accelerate.utils.imports
    accelerate.utils.imports.is_mps_available = lambda *args, **kwargs: False
except ImportError:
    pass

# Force CPU device for Docling to prevent early MPS detection during import
try:
    import docling.utils.accelerator_utils
    docling.utils.accelerator_utils.decide_device = lambda *args, **kwargs: "cpu"
except ImportError:
    pass
