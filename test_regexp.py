import sys
from sqlalchemy import select, String, or_, and_, orm
from models import Notification

base_query = select(Notification)
base_query = base_query.where(Notification.title.regexp_match('hello', flags='i'))
print(base_query.compile(compile_kwargs={"literal_binds": True}))
