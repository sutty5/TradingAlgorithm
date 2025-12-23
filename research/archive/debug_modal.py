
import modal
try:
    print(f"Modal Version: {modal.__version__}")
    print(f"Mount attribute: {modal.Mount}")
    print("Success: modal.Mount exists")
except AttributeError as e:
    print(f"Error accessing modal.Mount: {e}")
    # Inspect content
    print(f"Dir(modal): {dir(modal)}")

try:
    from modal import Mount
    print("Success: from modal import Mount works")
except ImportError as e:
    print(f"ImportError: {e}")
