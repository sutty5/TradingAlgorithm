import modal

app = modal.App("hello-world")

@app.function()
def square(x):
    print(f"Squaring {x} in the cloud!")
    return x**2

@app.local_entrypoint()
def main():
    print("Running on Modal...")
    result = square.remote(42)
    print(f"Result: {result}")
