-- 001_test_data.sql
-- Run after 001_initial_schema.sql.
-- Replace DEV Firebase UIDs with real values when authentication is connected.

insert into roles(code,name) values
('customer','Customer'),('manager','Manager'),('admin','Administrator')
on conflict(code) do nothing;

insert into users(firebase_uid,name,email,phone) values
('DEV_FIREBASE_UID_CUSTOMER','Demo Customer','customer@example.com','9999999999'),
('DEV_FIREBASE_UID_MANAGER','Demo Manager','manager@example.com','9999999998')
on conflict(firebase_uid) do nothing;

insert into user_roles(user_id,role_id)
select u.id,r.id from users u cross join roles r
where u.email='customer@example.com' and r.code='customer'
on conflict do nothing;

insert into user_roles(user_id,role_id)
select u.id,r.id from users u cross join roles r
where u.email='manager@example.com' and r.code='manager'
on conflict do nothing;

insert into venues(name,address,city,state,pincode)
values('Demo Cinema','123 Demo Road','Ahmedabad','Gujarat','380001')
on conflict do nothing;

insert into screens(venue_id,name,capacity)
select id,'Screen 1',20 from venues where name='Demo Cinema'
on conflict do nothing;

insert into seats(screen_id,row_label,seat_number,seat_type)
select s.id,r.row_label,n.seat_number,
       case when r.row_label='A' then 'premium'::seat_type else 'standard'::seat_type end
from screens s
cross join (values('A'),('B'),('C'),('D')) r(row_label)
cross join generate_series(1,5) n(seat_number)
where s.name='Screen 1'
on conflict do nothing;

insert into events(title,description,event_type,duration_minutes,language,genre,status)
values('Demo Movie','Development/test event.','movie',120,'English','Drama','published');

insert into shows(event_id,screen_id,start_time,end_time,status)
select e.id,s.id,now()+interval '1 day',now()+interval '1 day 2 hours','scheduled'
from events e cross join screens s
where e.title='Demo Movie' and s.name='Screen 1'
and not exists (
    select 1 from shows x where x.event_id=e.id and x.screen_id=s.id
);

insert into show_seats(show_id,seat_id,price,status)
select sh.id,se.id,
       case when se.seat_type='premium' then 350 else 250 end,
       'available'
from shows sh
join seats se on se.screen_id=sh.screen_id
join events e on e.id=sh.event_id
where e.title='Demo Movie'
on conflict(show_id,seat_id) do nothing;
