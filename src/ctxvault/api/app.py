from fastapi import FastAPI
from ctxvault.api.routes import ctxvault_router

app = FastAPI()

app.include_router(ctxvault_router)

@app.get("/")
def root():
    return {"message": "Welcome to CtxVault!"}