from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .schemas import LayoutCreate, LayoutUpdate, BulkUpdate
from .service import list_screens, list_layouts, create_layout, get_layout, update_layout, bulk_update, fixture

app = FastAPI(title='BookMyShow Manager Layout API')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000','http://127.0.0.1:3000'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

@app.get('/health')
def health(): return {'status':'ok'}

@app.get('/api/screens')
def screens(): return list_screens()

@app.get('/api/layouts')
def layouts(): return list_layouts()

@app.post('/api/layouts')
def create(payload: LayoutCreate): return create_layout(payload)

@app.get('/api/layouts/{layout_id}')
def read(layout_id: str): return get_layout(layout_id)

@app.put('/api/layouts/{layout_id}')
def update(layout_id: str, payload: LayoutUpdate): return update_layout(layout_id, payload)

@app.post('/api/layouts/{layout_id}/bulk-update')
def bulk(layout_id: str, payload: BulkUpdate): return bulk_update(layout_id, payload)

@app.get('/api/layouts/{layout_id}/fixture')
def get_fixture(layout_id: str): return fixture(layout_id)
