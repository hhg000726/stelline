import pymysql

from stelline.config import *

def get_rds_connection():
   return pymysql.connect(
       host=RDS_HOST,
       user=RDS_USER,
       password=RDS_PASSWORD,
       database=RDS_DB,
       charset="utf8",
       cursorclass=pymysql.cursors.DictCursor,
   )