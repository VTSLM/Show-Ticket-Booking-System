from dotenv import load_dotenv
load_dotenv()  # loads .env before anything else

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import bookings

app = FastAPI(title="TicketFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bookings.router, prefix="/bookings", tags=["Bookings"])

@app.get("/")
def root():
    return {"status": "TicketFlow API is running"}
