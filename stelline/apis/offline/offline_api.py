from flask import jsonify
from stelline.database.db_connection import get_rds_connection

def offlin_api():
    conn = get_rds_connection()
    with conn.cursor() as cursor:
        try:
            cursor.execute("SELECT * FROM offline")
            data = cursor.fetchall()
            return jsonify(data), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        finally:
            conn.close()