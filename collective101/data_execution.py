"""Bounded SELECT-only SQLite execution over explicitly supplied in-memory data."""
import json,re,sqlite3,time

def execute_sql(query,tables):
    if not isinstance(query,str) or not query.strip() or len(query)>20000:raise ValueError('SQL query exceeds bounds')
    if not isinstance(tables,dict) or not tables or len(tables)>8 or len(json.dumps(tables,allow_nan=False))>60000:
        raise ValueError('Supply at most eight bounded data tables')
    identifier=lambda name:isinstance(name,str) and bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,39}',name))
    db=sqlite3.connect(':memory:')
    try:
        db.execute('PRAGMA temp_store=MEMORY')
        for limit,value in [(sqlite3.SQLITE_LIMIT_LENGTH,100000),(sqlite3.SQLITE_LIMIT_SQL_LENGTH,20000),
                            (sqlite3.SQLITE_LIMIT_COLUMN,64),(sqlite3.SQLITE_LIMIT_EXPR_DEPTH,50),
                            (sqlite3.SQLITE_LIMIT_COMPOUND_SELECT,8),(sqlite3.SQLITE_LIMIT_VDBE_OP,50000)]:db.setlimit(limit,value)
        total=0
        for name,rows in tables.items():
            if not identifier(name) or name.lower().startswith('sqlite_') or not isinstance(rows,list) or not rows:
                raise ValueError('Tables need valid names and at least one row')
            if not isinstance(rows[0],dict):raise ValueError('Rows must be objects')
            columns=list(rows[0]);total+=len(rows)
            if total>1000 or not columns or len(columns)>32 or any(not identifier(c) for c in columns):raise ValueError('Data table limits exceeded')
            db.execute('CREATE TABLE "'+name+'" ('+','.join('"'+c+'"' for c in columns)+')')
            values=[]
            for row in rows:
                if not isinstance(row,dict) or set(row)!=set(columns) or any(v is not None and type(v) not in (str,int,float,bool) for v in row.values()):
                    raise ValueError('Rows must have matching primitive columns')
                values.append(tuple(row[c] for c in columns))
            db.executemany('INSERT INTO "'+name+'" VALUES('+','.join('?' for _ in columns)+')',values)
        db.commit()
        functions={'count','sum','avg','min','max','total','abs','lower','upper','length','coalesce','round','substr','trim','ifnull','nullif'}
        def authorize(action,a,b,database,trigger):
            if action==sqlite3.SQLITE_SELECT:return sqlite3.SQLITE_OK
            if action==sqlite3.SQLITE_READ and a in tables and database=='main':return sqlite3.SQLITE_OK
            if action==sqlite3.SQLITE_FUNCTION and (b or '').lower() in functions:return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        db.set_authorizer(authorize)
        start=time.monotonic();ticks=0
        def stop():
            nonlocal ticks
            ticks+=1
            return int(ticks>100 or time.monotonic()-start>.25)
        db.set_progress_handler(stop,1000)
        cursor=db.execute(query);rows=cursor.fetchmany(201)
        if len(rows)>200 or len(json.dumps(rows,allow_nan=False))>64000:raise ValueError('Query result exceeds bounds')
        return {'status':'ok','engine':'SQLite / in-memory read-only','columns':[c[0] for c in cursor.description],
            'rows':[list(r) for r in rows],'limits':{'rows':200,'input_rows':1000,'vm_steps':100000,'file_access':False}}
    except (sqlite3.Error,MemoryError,OverflowError):
        return {'status':'failed','engine':'SQLite / in-memory read-only','error':'Query denied, invalid, or exceeded execution bounds; no host database was accessed'}
    finally:db.close()
