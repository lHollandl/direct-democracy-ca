from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Direct Democracy Cali API", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
