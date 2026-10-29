from fastapi import HTTPException
from .db import supabase


def rows(result):
    return result.data or []


def list_screens():
    result = supabase.table('screens').select('id,name').order('name').execute()
    return [{'id': str(r['id']), 'name': r['name']} for r in rows(result)]




def list_layouts():
    result = supabase.table('layouts').select('id,screen_id,screen_name,rows,columns,approved_capacity,status,updated_at').order('updated_at', desc=True).execute()
    return result.data or []


def get_layout(layout_id: str):
    result = supabase.table('layouts').select('*').eq('id', layout_id).single().execute()
    if not result.data:
        raise HTTPException(404, 'Layout not found')
    seats = supabase.table('layout_seats').select('*').eq('layout_id', layout_id).order('row_index').order('col_index').execute()
    layout = result.data
    layout['seats'] = rows(seats)
    return layout


def validate(layout, seats):
    if not seats:
        raise HTTPException(400, 'Layout must contain at least one seat')
    sellable = [s for s in seats if s['status'] != 'blocked']
    if not sellable:
        raise HTTPException(400, 'Layout must contain at least one sellable seat')
    if len(sellable) > layout['approved_capacity']:
        raise HTTPException(400, f"Sellable seats ({len(sellable)}) exceed approved capacity ({layout['approved_capacity']})")
    for s in sellable:
        if not s.get('category'):
            raise HTTPException(400, f"{s['label']} has no category")
        if s.get('price') is None:
            raise HTTPException(400, f"{s['label']} has no price")


def create_layout(payload):
    aisle = set(payload.aisle_columns)
    if any(c < 0 or c >= payload.columns for c in aisle):
        raise HTTPException(400, 'Aisle column is outside the layout width')
    layout_result = supabase.table('layouts').insert({
        'screen_id': str(payload.screen_id) if payload.screen_id else None,
        'screen_name': payload.screen_name,
        'rows': payload.rows,
        'columns': payload.columns,
        'approved_capacity': payload.approved_capacity,
        'status': 'draft',
    }).execute()
    if not rows(layout_result):
        raise HTTPException(500, 'Could not create layout')
    layout_id = layout_result.data[0]['id']
    seats = []
    for r in range(payload.rows):
        row_label = chr(65+r) if r < 26 else f'R{r+1}'
        for c in range(payload.columns):
            if c in aisle:
                continue
            seats.append({'layout_id': layout_id, 'row_index': r, 'col_index': c,
                          'label': f'{row_label}{c+1}', 'category': None,
                          'price': None, 'status': 'available'})
    for i in range(0, len(seats), 500):
        supabase.table('layout_seats').insert(seats[i:i+500]).execute()
    return get_layout(str(layout_id))


def bulk_update(layout_id, payload):
    layout = get_layout(layout_id)

    valid = {str(s['id']) for s in layout['seats']}
    ids = [str(x) for x in payload.seat_ids]

    # Make sure all selected seats belong to this layout
    if any(x not in valid for x in ids):
        raise HTTPException(
            status_code=400,
            detail='One or more seats do not belong to this layout'
        )

    patch = {}

    if payload.category is not None:
        patch['category'] = payload.category

    if payload.price is not None:
        # Convert Decimal → float before sending to Supabase
        patch['price'] = float(payload.price)

    if payload.status is not None:
        if payload.status not in ('available', 'blocked'):
            raise HTTPException(
                status_code=400,
                detail='Invalid seat status'
            )

        patch['status'] = payload.status

    if not patch:
        raise HTTPException(
            status_code=400,
            detail='No changes supplied'
        )

    # Update every selected seat
    for seat_id in ids:
        result = (
            supabase
            .table('layout_seats')
            .update(patch)
            .eq('id', seat_id)
            .eq('layout_id', layout_id)
            .execute()
        )

    return get_layout(layout_id)


def update_layout(layout_id, payload):
    layout = get_layout(layout_id)
    valid = {str(s['id']) for s in layout['seats']}
    incoming = []
    for s in payload.seats:
        d = s.model_dump(mode='json')
        if d['id'] not in valid:
            raise HTTPException(400, f"Seat {d['id']} does not belong to this layout")
        incoming.append(d)
    validate({'approved_capacity': payload.approved_capacity}, incoming)
    supabase.table('layouts').update({
        'screen_name': payload.screen_name,
        'approved_capacity': payload.approved_capacity,
        'status': payload.status,
    }).eq('id', layout_id).execute()
    for s in incoming:
        sid = s.pop('id')
        supabase.table('layout_seats').update(s).eq('id', sid).eq('layout_id', layout_id).execute()
    return get_layout(layout_id)


def fixture(layout_id):
    layout = get_layout(layout_id)
    return {'layout': {k: layout[k] for k in ('id','screen_id','screen_name','rows','columns')},
            'seats': [{'id': s['id'], 'row': s['row_index'], 'col': s['col_index'],
                       'label': s['label'], 'category': s['category'], 'price': s['price'],
                       'status': s['status']} for s in layout['seats']]}
