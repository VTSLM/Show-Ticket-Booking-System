# Class Diagram: Events, Shows, Venues, and Seats

## 1. Description and Purpose
This diagram models the physical and scheduled entities governing venues, screens, events, shows, and seat configurations. It highlights the critical distinction between physical seats (`seats`) tied to a screen, and show-specific seat instances (`show_seats`) that carry dynamic state, price locks, and reservations for a scheduled show.

## 2. Class Diagram
```mermaid
classDiagram
    class Venue {
        +UUID id
        +String name
        +String address
        +String city
        +String state
        +String pincode
        +Decimal latitude
        +Decimal longitude
        +String verification_status
        +UUID manager_id
        +DateTime created_at
        +DateTime updated_at
    }

    class Screen {
        +UUID id
        +UUID venue_id
        +String name
        +Integer capacity
        +String layout_type
        +String stage_position
        +JSONB layout_config
        +DateTime created_at
    }

    class Seat {
        +UUID id
        +UUID screen_id
        +String row_label
        +Integer seat_number
        +SeatType seat_type
        +Integer x_pos
        +Integer y_pos
        +String section_name
    }

    class Event {
        +UUID id
        +String title
        +String description
        +EventType event_type
        +Integer duration_minutes
        +String language
        +String genre
        +String poster_url
        +EventStatus status
        +Text terms_and_conditions
        +UUID created_by
        +DateTime created_at
        +DateTime updated_at
    }

    class Show {
        +UUID id
        +UUID event_id
        +UUID screen_id
        +DateTime start_time
        +DateTime end_time
        +ShowStatus status
        +Decimal base_price
        +Boolean dynamic_pricing
        +Text terms_and_conditions
        +DateTime created_at
        +DateTime updated_at
    }

    class ShowSeat {
        +UUID id
        +UUID show_id
        +UUID seat_id
        +Decimal price
        +Decimal locked_price
        +ShowSeatStatus status
        +DateTime locked_until
        +UUID locked_by
        +isAvailable() bool
        +isLockExpired() bool
    }

    class ShowZone {
        +UUID id
        +UUID show_id
        +String name
        +String zone_type
        +Integer total_capacity
        +Integer booked_count
        +Integer locked_count
        +Decimal price
        +String color_hex
        +Integer display_order
        +JSONB polygon_coords
        +availableCapacity() int
    }

    class SeatType {
        <<enumeration>>
        standard
        premium
        accessible
    }

    class EventType {
        <<enumeration>>
        movie
        concert
        theatre
        other
    }

    class ShowStatus {
        <<enumeration>>
        scheduled
        cancelled
        completed
    }

    class ShowSeatStatus {
        <<enumeration>>
        available
        locked
        booked
        reserved
    }

    %% Relationships
    Venue "1" *-- "1..*" Screen : contains (cascade delete)
    Screen "1" *-- "1..*" Seat : configures (cascade delete)
    Seat "1" --> "1" SeatType : typed as

    Event "1" --> "1" EventType : categorised as
    Event "1" -- "0..*" Show : scheduled as (delete restrict)
    Screen "1" -- "0..*" Show : hosts (delete restrict)
    Show "1" --> "1" ShowStatus : has status

    Show "1" *-- "*" ShowSeat : allocates
    Seat "1" -- "*" ShowSeat : instantiates for show (delete restrict)
    ShowSeat "1" --> "1" ShowSeatStatus : has status

    Show "1" *-- "*" ShowZone : partitions standing areas
```

## 3. Relationship Explanations & Multiplicities
- **`Venue *-- Screen` (Composition `1` to `1..*`):** A screen cannot exist outside a venue. Deleting a venue cascades to delete all screens.
- **`Screen *-- Seat` (Composition `1` to `1..*`):** Physical seats are bound to a specific screen layout (`screen_id REFERENCES screens(id) ON DELETE CASCADE`).
- **`Event -- Show` & `Screen -- Show` (Association `1` to `*`):** A show links an event to a screen at a specific time. Foreign keys use `ON DELETE RESTRICT` to preserve historical booking records.
- **`Show *-- ShowSeat` (Composition `1` to `*`):** Each scheduled show generates show-specific seat records that track dynamic price locks and availability (`show_id REFERENCES shows(id) ON DELETE CASCADE`).
- **`Seat -- ShowSeat` (Association `1` to `*`):** Points to the physical seat metadata (`seat_id REFERENCES seats(id) ON DELETE RESTRICT`).

## 4. Source Traceability
- Tables: `venues`, `screens`, `seats`, `events`, `shows`, `show_seats`, `show_zones`.
- Migrations: `0001_initial_schema.sql`, `0012_multi_venue_layouts.sql`, `0018_dynamic_seat_pricing.sql`, `0019_show_details_layout_and_terms.sql`, `0022_align_with_live_schema.sql`.
- Backend Routers: `backend/routers/manager.py`, `backend/routers/browse.py`, `backend/routers/seats.py`.
- Backend Services: `backend/services/dynamic_pricing.py`, `backend/services/terms_service.py`.
