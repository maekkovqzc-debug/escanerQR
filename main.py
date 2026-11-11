from datetime import datetime
import os
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Control de Acceso API")

DATABASE_URL = os.getenv("DB_URL")

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, connect_timeout=15)
    try:
        yield conn
    finally:
        conn.close()

class ValidarQrRequest(BaseModel):
    qr_token: str

@app.post("/api/accesos/verificar")
def verificar_acceso(payload: ValidarQrRequest, db = Depends(get_db)):
    cursor = db.cursor()
    
    query_cliente = """
        SELECT c.id, c.nombre, c.apellido, c.foto_url, c.activo,
            p.fecha_vencimiento
        FROM clientes c
        LEFT JOIN pagos p ON c.id = p.cliente_id
        WHERE c.qr_token = %s
        ORDER BY p.fecha_vencimiento DESC
        LIMIT 1;
    """
    cursor.execute(query_cliente, (payload.qr_token,))
    cliente = cursor.fetchone()
    
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código QR inválido o cliente no encontrado."
        )
    
    hoy = datetime.now().date()
    pago_vigente = False
    
    if cliente["activo"] and cliente["fecha_vencimiento"]:
        if cliente["fecha_vencimiento"] >= hoy:
            pago_vigente = True

    permitido = bool(pago_vigente)
    
    query_insert_acceso = """
        INSERT INTO accesos (cliente_id, fecha_hora, permitido)
        VALUES (%s, NOW(), %s);
    """
    cursor.execute(query_insert_acceso, (cliente["id"], permitido))
    db.commit()
    
    return {
        "permitido": permitido,
        "mensaje": "Acceso concedido" if permitido else "Acceso denegado: Membresía vencida o inactiva",
        "cliente": {
            "nombre": cliente["nombre"],
            "apellido": cliente["apellido"],
            "foto_url": cliente["foto_url"],
            "fecha_vencimiento": str(cliente["fecha_vencimiento"]) if cliente["fecha_vencimiento"] else None
        }
    }
